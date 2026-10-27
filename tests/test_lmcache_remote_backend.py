# SPDX-License-Identifier: Apache-2.0
"""Exercise the connector through LMCache's own ``RemoteBackend``.

These tests need a real LMCache install. They load ``CouchbaseConnector`` the
same way vLLM does, through ``remote_storage_plugins`` and LMCache's
``ConnectorManager``, and round-trip real KV-cache tensors including LMCache's
``RemoteMetadata`` chunk header. Each test runs against an in-memory store and,
when ``LMCACHE_COUCHBASE_LIVE_TESTS=1``, against a real Couchbase cluster.
"""

import asyncio
import os
import threading
import uuid

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("lmcache.v1.storage_backend.remote_backend")

from lmcache.utils import CacheEngineKey  # noqa: E402
from lmcache.v1.config import LMCacheEngineConfig  # noqa: E402
from lmcache.v1.memory_allocators.mixed_memory_allocator import (  # noqa: E402
    MixedMemoryAllocator,
)
from lmcache.v1.memory_management import MemoryFormat  # noqa: E402
from lmcache.v1.metadata import LMCacheMetadata  # noqa: E402
from lmcache.v1.storage_backend.local_cpu_backend import (  # noqa: E402
    LocalCPUBackend,
)
from lmcache.v1.storage_backend.remote_backend import RemoteBackend  # noqa: E402

from couchbase_lm_cache import CouchbaseConnector, CouchbaseLMCacheConfig  # noqa: E402

CHUNK_SIZE = 16
NUM_LAYERS = 4
NUM_HEADS = 2
HEAD_DIM = 8
DTYPE = torch.bfloat16


class _MemoryStore:
    """In-memory stand-in for ``CouchbaseKVStore``."""

    docs: dict = {}

    def __init__(self, cfg):
        self.cfg = cfg

    def build_key(self, key):
        return self.cfg.key_prefix + key.to_string()

    def put_bytes(self, key, payload):
        self.docs[self.build_key(key)] = bytes(payload)

    def get_bytes(self, key):
        return self.docs.get(self.build_key(key))

    def exists(self, key):
        return self.build_key(key) in self.docs

    def remove(self, key):
        return self.docs.pop(self.build_key(key), None) is not None

    def ping(self):
        return True

    def close(self):
        pass


def _live_enabled():
    return os.environ.get("LMCACHE_COUCHBASE_LIVE_TESTS") == "1"


@pytest.fixture(
    params=[
        "memory",
        pytest.param("couchbase", marks=pytest.mark.live),
    ]
)
def store_kind(request, monkeypatch):
    if request.param == "memory":
        _MemoryStore.docs = {}
        monkeypatch.setattr(
            "couchbase_lm_cache.connector.CouchbaseKVStore", _MemoryStore
        )
    elif not _live_enabled():
        pytest.skip("set LMCACHE_COUCHBASE_LIVE_TESTS=1 to run live Couchbase test")
    return request.param


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def allocator():
    allocator = MixedMemoryAllocator(256 * 1024 * 1024)
    yield allocator
    allocator.close()


def _metadata():
    return LMCacheMetadata(
        model_name="couchbase-connector-test",
        world_size=1,
        local_world_size=1,
        worker_id=0,
        local_worker_id=0,
        kv_dtype=DTYPE,
        kv_shape=(NUM_LAYERS, 2, CHUNK_SIZE, NUM_HEADS, HEAD_DIM),
        chunk_size=CHUNK_SIZE,
    )


def _engine_config(plugin_name="couchbase", **extra):
    if _live_enabled():
        cb = CouchbaseLMCacheConfig.from_env()
        connection = {
            "connection_string": cb.connection_string,
            "username": cb.username,
            "password": cb.password,
            "bucket_name": cb.bucket_name,
            "scope_name": cb.scope_name,
            "collection_name": cb.collection_name,
        }
    else:
        connection = {
            "connection_string": "couchbase://unused",
            "username": "u",
            "password": "p",
            "bucket_name": "b",
        }
    prefix = f"remote_storage_plugin.{plugin_name}"
    extra_config = {
        f"{prefix}.module_path": "couchbase_lm_cache.connector",
        f"{prefix}.class_name": "CouchbaseConnector",
        f"{prefix}.key_prefix": f"pytest-{uuid.uuid4().hex[:8]}:",
        f"{prefix}.ttl_seconds": 300,
        **{f"{prefix}.{field}": value for field, value in connection.items()},
        **extra,
    }
    return LMCacheEngineConfig.from_defaults(
        chunk_size=CHUNK_SIZE,
        remote_storage_plugins=[plugin_name],
        remote_serde="naive",
        lmcache_instance_id="couchbase-connector-test",
        extra_config=extra_config,
    )


@pytest.fixture
def make_backend(loop, allocator):
    backends = []

    def factory(plugin_name="couchbase", **extra):
        config = _engine_config(plugin_name, **extra)
        metadata = _metadata()
        local_cpu = LocalCPUBackend(config, metadata, memory_allocator=allocator)
        backend = RemoteBackend(
            config=config,
            metadata=metadata,
            loop=loop,
            local_cpu_backend=local_cpu,
            dst_device="cpu",
            plugin_name=plugin_name,
        )
        backends.append(backend)
        return backend, local_cpu

    yield factory
    for backend in backends:
        backend.close()


def _key(chunk_hash):
    return CacheEngineKey(
        model_name="couchbase-connector-test",
        world_size=1,
        worker_id=0,
        chunk_hash=chunk_hash,
        dtype=DTYPE,
    )


def _kv_chunk(local_cpu, num_tokens=CHUNK_SIZE, seed=0):
    shape = torch.Size([2, NUM_LAYERS, num_tokens, NUM_HEADS * HEAD_DIM])
    memory_obj = local_cpu.allocate([shape], [DTYPE], MemoryFormat.KV_2LTD)
    generator = torch.Generator().manual_seed(seed)
    memory_obj.tensor.copy_(torch.randn(shape, generator=generator).to(DTYPE))
    return memory_obj


def _put(backend, key, memory_obj):
    future = backend.submit_put_task(key, memory_obj)
    if future is not None:
        future.result(timeout=10)


def _connector(backend):
    connector = backend.connection._connector
    assert isinstance(connector, CouchbaseConnector)
    return connector


def test_lmcache_loads_couchbase_plugin(store_kind, make_backend):
    backend, _ = make_backend()

    connector = _connector(backend)
    assert connector.plugin_name == "couchbase"
    assert connector.save_chunk_meta
    assert (
        asyncio.run_coroutine_threadsafe(connector.ping(), backend.loop).result(
            timeout=10
        )
        == 0
    )


def test_full_chunk_roundtrip_preserves_tensor(store_kind, make_backend):
    backend, local_cpu = make_backend()
    key = _key(1001)
    original = _kv_chunk(local_cpu, seed=1)
    expected = original.tensor.clone()

    _put(backend, key, original)

    assert backend.contains(key)
    restored = backend.get_blocking(key)
    assert restored is not None
    assert restored.get_shapes() == [expected.shape]
    assert restored.get_dtypes() == [DTYPE]
    assert restored.get_memory_format() == MemoryFormat.KV_2LTD
    assert torch.equal(restored.tensor, expected)
    assert backend.remove(key)
    assert not backend.contains(key)


def test_partial_chunk_roundtrip_uses_stored_shape(store_kind, make_backend):
    backend, local_cpu = make_backend()
    key = _key(1002)
    original = _kv_chunk(local_cpu, num_tokens=5, seed=2)
    expected = original.tensor.clone()

    _put(backend, key, original)

    restored = backend.get_blocking(key)
    assert restored is not None
    assert restored.get_shapes() == [torch.Size([2, NUM_LAYERS, 5, 16])]
    assert torch.equal(restored.tensor, expected)
    backend.remove(key)


def test_raw_mode_without_chunk_metadata(store_kind, make_backend):
    backend, local_cpu = make_backend(save_chunk_meta=False)
    key = _key(1003)
    original = _kv_chunk(local_cpu, seed=3)
    expected = original.tensor.clone()

    _put(backend, key, original)

    assert not _connector(backend).save_chunk_meta
    restored = backend.get_blocking(key)
    assert restored is not None
    assert torch.equal(restored.tensor, expected)
    backend.remove(key)


def test_batched_put_get_and_prefix_contains(store_kind, make_backend):
    backend, local_cpu = make_backend()
    keys = [_key(2000 + i) for i in range(4)]
    originals = [_kv_chunk(local_cpu, seed=10 + i) for i in range(4)]
    expected = [obj.tensor.clone() for obj in originals]

    # LMCache writes batches asynchronously and reports completion per key.
    written = threading.Semaphore(0)
    backend.batched_submit_put_task(
        keys, originals, on_complete_callback=lambda key: written.release()
    )
    for _ in keys:
        assert written.acquire(timeout=10)

    missing = _key(2999)
    assert backend.batched_contains(keys + [missing]) == 4
    assert backend.batched_contains([missing] + keys) == 0
    restored = backend.batched_get_blocking(keys)
    for got, want in zip(restored, expected, strict=True):
        assert got is not None
        assert torch.equal(got.tensor, want)
    for key in keys:
        backend.remove(key)


def test_two_backends_share_chunks_through_store(store_kind, make_backend):
    """A chunk written by one LMCache instance is readable by another."""

    writer, writer_cpu = make_backend()
    key_prefix = _connector(writer).cfg.key_prefix
    reader, _ = make_backend(
        **{"remote_storage_plugin.couchbase.key_prefix": key_prefix}
    )
    key = _key(3001)
    original = _kv_chunk(writer_cpu, seed=4)
    expected = original.tensor.clone()

    _put(writer, key, original)

    restored = reader.get_blocking(key)
    assert restored is not None
    assert torch.equal(restored.tensor, expected)
    writer.remove(key)
