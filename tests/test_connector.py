# SPDX-License-Identifier: Apache-2.0

import asyncio
import ctypes
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


class _CtypesMemoryObj:
    """Mimics LMCache's ``byte_array``: a memoryview of a ``c_ubyte`` array."""

    def __init__(self, size=16):
        self.buffer = (ctypes.c_ubyte * size)()
        self.byte_array = memoryview(self.buffer)


class _LocalCPUBackend:
    def __init__(self, memory_obj_cls=None):
        self.memory_obj_cls = memory_obj_cls or _MemoryObj
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
        return self.memory_obj_cls()


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

    def close(self):
        self.closed = True


class _Key:
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return self.value


async def _exercise_connector(monkeypatch):
    monkeypatch.setattr("couchbase_lm_cache.connector.CouchbaseKVStore", _Store)
    cfg = SimpleNamespace(
        extra_config={
            "remote_storage_plugin.couchbase.connection_string": "couchbase://localhost",
            "remote_storage_plugin.couchbase.username": "Administrator",
            "remote_storage_plugin.couchbase.password": "password",
            "remote_storage_plugin.couchbase.bucket_name": "lmcache",
        }
    )
    connector = CouchbaseConnector(
        loop=asyncio.get_running_loop(),
        local_cpu_backend=_LocalCPUBackend(),
        config=cfg,
        plugin_name="couchbase",
    )
    connector.meta_shapes = []
    connector.meta_dtypes = []
    connector.meta_fmt = None

    key1 = _Key("k1")
    key2 = _Key("k2")
    obj = _MemoryObj()
    obj.byte_array[:5] = b"hello"
    await connector.put(key1, obj)

    assert await connector.exists(key1)
    assert not await connector.exists(key2)
    assert connector.batched_contains([key1, key2]) == 1
    got = await connector.get(key1)
    assert bytes(got.byte_array[:5]) == b"hello"
    await connector.close()
    assert connector.store.closed


def test_connector_put_get_exists(monkeypatch):
    asyncio.run(_exercise_connector(monkeypatch))


async def _exercise_ctypes_buffers(monkeypatch):
    monkeypatch.setattr("couchbase_lm_cache.connector.CouchbaseKVStore", _Store)
    cfg = SimpleNamespace(
        extra_config={
            "remote_storage_plugin.couchbase.connection_string": "couchbase://localhost",
            "remote_storage_plugin.couchbase.username": "Administrator",
            "remote_storage_plugin.couchbase.password": "password",
            "remote_storage_plugin.couchbase.bucket_name": "lmcache",
        }
    )
    connector = CouchbaseConnector(
        loop=asyncio.get_running_loop(),
        local_cpu_backend=_LocalCPUBackend(_CtypesMemoryObj),
        config=cfg,
        plugin_name="couchbase",
    )
    connector.meta_shapes = []
    connector.meta_dtypes = []
    connector.meta_fmt = None

    obj = _CtypesMemoryObj()
    assert obj.byte_array.format == "<B"
    obj.byte_array.cast("B")[:] = b"sixteen-byte-kv!"
    key = _Key("ctypes")
    await connector.put(key, obj)
    await connector.batched_put([_Key("ctypes-batch")], [obj])
    assert connector.store.docs["ctypes"] == b"sixteen-byte-kv!"

    got = await connector.get(key)
    assert bytes(got.byte_array) == b"sixteen-byte-kv!"
    await connector.close()


def test_connector_handles_lmcache_ctypes_buffers(monkeypatch):
    asyncio.run(_exercise_ctypes_buffers(monkeypatch))
