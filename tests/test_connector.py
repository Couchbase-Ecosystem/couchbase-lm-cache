# SPDX-License-Identifier: Apache-2.0

import asyncio
from types import SimpleNamespace

from couchbase_lm_cache.connector import _HAS_LMCACHE, CouchbaseConnector

if _HAS_LMCACHE:
    import torch
    from lmcache.v1.config import LMCacheEngineConfig
    from lmcache.v1.metadata import LMCacheMetadata
else:
    torch = None
    LMCacheEngineConfig = None
    LMCacheMetadata = None


class _MemoryObj:
    def __init__(self, size=16):
        self.buffer = bytearray(size)
        self.byte_array = memoryview(self.buffer)
        self.released = False

    def ref_count_down(self):
        self.released = True


class _LocalCPUBackend:
    def __init__(self, fail_allocation=False):
        self.fail_allocation = fail_allocation
        self.allocated = []
        if _HAS_LMCACHE:
            assert LMCacheEngineConfig is not None
            assert LMCacheMetadata is not None
            assert torch is not None
            self.config = LMCacheEngineConfig(extra_config={})
            self.metadata = LMCacheMetadata(
                model_name="unit-test",
                world_size=1,
                local_world_size=1,
                worker_id=0,
                local_worker_id=0,
                kv_dtype=torch.float16,
                kv_shape=(1, 2, 1, 1, 4),
                chunk_size=1,
            )
        else:
            self.config = SimpleNamespace(extra_config={})
            self.metadata = object()

    def allocate(self, shapes, dtypes, fmt):
        del shapes, dtypes, fmt
        if self.fail_allocation:
            return None
        memory_obj = _MemoryObj()
        self.allocated.append(memory_obj)
        return memory_obj


class _Store:
    def __init__(self, cfg):
        self.cfg = cfg
        self.docs = {}
        self.closed = False

    def put_bytes(self, key, payload):
        self.docs[key.to_string()] = bytes(payload)

    def get_bytes(self, key):
        return self.docs.get(key.to_string())

    def exists(self, key):
        return key.to_string() in self.docs

    def remove(self, key):
        return self.docs.pop(key.to_string(), None) is not None

    def ping(self):
        return True

    def close(self):
        self.closed = True


class _Key:
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return self.value


def _make_connector(monkeypatch, local_cpu_backend=None):
    monkeypatch.setattr("couchbase_lm_cache.connector.CouchbaseKVStore", _Store)
    cfg = SimpleNamespace(
        extra_config={
            "remote_storage_plugin.couchbase.connection_string": "couchbase://localhost",
            "remote_storage_plugin.couchbase.username": "Administrator",
            "remote_storage_plugin.couchbase.password": "password",
            "remote_storage_plugin.couchbase.bucket_name": "lmcache",
            # The fake MemoryObj has no tensor metadata, so store raw bytes.
            "save_chunk_meta": False,
        },
        use_layerwise=False,
    )
    if _HAS_LMCACHE:
        cfg = LMCacheEngineConfig.from_defaults(
            chunk_size=1, extra_config=cfg.extra_config
        )
    connector = CouchbaseConnector(
        loop=asyncio.get_running_loop(),
        local_cpu_backend=local_cpu_backend or _LocalCPUBackend(),
        config=cfg,
        plugin_name="couchbase",
    )
    connector.save_chunk_meta = False
    connector.meta_shapes = []
    connector.meta_dtypes = []
    connector.meta_fmt = None
    # Payloads in these tests are arbitrary bytes, not whole KV tokens.
    connector.reshape_partial_chunk = lambda memory_obj, bytes_read: memory_obj
    return connector


def _obj(payload):
    obj = _MemoryObj()
    obj.byte_array[: len(payload)] = payload
    return obj


def _run(coro_factory):
    def wrapper(monkeypatch):
        asyncio.run(coro_factory(monkeypatch))

    return wrapper


@_run
async def test_connector_put_get_exists(monkeypatch):
    connector = _make_connector(monkeypatch)

    key1 = _Key("k1")
    key2 = _Key("k2")
    await connector.put(key1, _obj(b"hello"))

    assert await connector.exists(key1)
    assert connector.exists_sync(key1)
    assert not await connector.exists(key2)
    assert connector.batched_contains([key1, key2]) == 1
    assert await connector.batched_async_contains("lookup", [key1, key2]) == 1
    got = await connector.get(key1)
    assert bytes(got.byte_array[:5]) == b"hello"
    assert await connector.get(key2) is None
    await connector.close()
    assert connector.store.closed


@_run
async def test_connector_batched_put_and_get(monkeypatch):
    connector = _make_connector(monkeypatch)
    keys = [_Key(f"k{i}") for i in range(4)]

    await connector.batched_put(keys, [_obj(f"v{i}".encode()) for i in range(4)])
    results = await connector.batched_get(keys + [_Key("missing")])

    assert [bytes(r.byte_array[:2]) for r in results[:4]] == [
        b"v0",
        b"v1",
        b"v2",
        b"v3",
    ]
    assert results[4] is None
    assert connector.batched_contains(keys) == 4
    await connector.close()


@_run
async def test_batched_get_non_blocking_returns_only_consecutive_prefix(monkeypatch):
    backend = _LocalCPUBackend()
    connector = _make_connector(monkeypatch, backend)
    k0, gap, k2 = _Key("k0"), _Key("gap"), _Key("k2")
    await connector.put(k0, _obj(b"a"))
    await connector.put(k2, _obj(b"c"))

    results = await connector.batched_get_non_blocking("lookup", [k0, gap, k2])

    # LMCache maps results onto keys by position: k2 must not fill gap's slot.
    assert len(results) == 1
    assert bytes(results[0].byte_array[:1]) == b"a"
    assert not results[0].released
    fetched_after_gap = [o for o in backend.allocated if o is not results[0]]
    assert len(fetched_after_gap) == 1
    assert fetched_after_gap[0].released
    await connector.close()


@_run
async def test_get_returns_none_when_allocation_fails(monkeypatch):
    connector = _make_connector(monkeypatch, _LocalCPUBackend(fail_allocation=True))
    key = _Key("k")
    connector.store.docs["k"] = b"payload"

    assert await connector.get(key) is None
    await connector.close()


@_run
async def test_get_rejects_and_releases_oversized_payload(monkeypatch):
    backend = _LocalCPUBackend()
    connector = _make_connector(monkeypatch, backend)
    key = _Key("k")
    connector.store.docs["k"] = b"x" * 64

    try:
        await connector.get(key)
    except ValueError as exc:
        assert "64 bytes" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("oversized payload was accepted")
    assert backend.allocated[0].released
    await connector.close()


@_run
async def test_remove_sync_and_ping(monkeypatch):
    connector = _make_connector(monkeypatch)
    key = _Key("k")
    await connector.put(key, _obj(b"v"))

    assert connector.support_ping()
    assert await connector.ping() == 0
    assert connector.remove_sync(key)
    assert not connector.remove_sync(key)
    assert not await connector.exists(key)
    await connector.close()


def test_plugin_name_inferred_from_single_configured_plugin(monkeypatch):
    async def scenario(monkeypatch):
        monkeypatch.setattr("couchbase_lm_cache.connector.CouchbaseKVStore", _Store)
        cfg = SimpleNamespace(
            remote_storage_plugins=["couchbase.primary"],
            use_layerwise=False,
            extra_config={
                "remote_storage_plugin.couchbase.primary.connection_string": "cb://a",
                "remote_storage_plugin.couchbase.primary.username": "u",
                "remote_storage_plugin.couchbase.primary.password": "p",
                "remote_storage_plugin.couchbase.primary.bucket_name": "b",
                "save_chunk_meta": False,
            },
        )
        if _HAS_LMCACHE:
            cfg = LMCacheEngineConfig.from_defaults(
                chunk_size=1,
                remote_storage_plugins=cfg.remote_storage_plugins,
                extra_config=cfg.extra_config,
            )
        # LMCache's DynamicConnectorAdapter does not pass plugin_name.
        connector = CouchbaseConnector(
            loop=asyncio.get_running_loop(),
            local_cpu_backend=_LocalCPUBackend(),
            config=cfg,
        )
        assert connector.plugin_name == "couchbase.primary"
        assert connector.cfg.connection_string == "cb://a"
        await connector.close()

    asyncio.run(scenario(monkeypatch))
