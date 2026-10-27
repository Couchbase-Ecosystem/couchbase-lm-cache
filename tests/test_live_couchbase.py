# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
from types import SimpleNamespace

import pytest

from couchbase_lm_cache import CouchbaseKVStore, CouchbaseLMCacheConfig
from couchbase_lm_cache.connector import _HAS_LMCACHE, CouchbaseConnector

if _HAS_LMCACHE:
    import torch
    from lmcache.v1.config import LMCacheEngineConfig
    from lmcache.v1.metadata import LMCacheMetadata


class _Key:
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return self.value


class _MemoryObj:
    def __init__(self, payload=b"", size=64):
        self.buffer = bytearray(size)
        self.byte_array = memoryview(self.buffer)
        if payload:
            self.byte_array[: len(payload)] = payload


class _LocalCPUBackend:
    if _HAS_LMCACHE:
        config = LMCacheEngineConfig.from_defaults(
            chunk_size=1, extra_config={"save_chunk_meta": False}
        )
        metadata = LMCacheMetadata(
            model_name="live-test",
            world_size=1,
            local_world_size=1,
            worker_id=0,
            local_worker_id=0,
            kv_dtype=torch.float16,
            kv_shape=(1, 2, 1, 1, 4),
            chunk_size=1,
        )
    else:
        config = SimpleNamespace(extra_config={})
        metadata = object()

    def allocate(self, shapes, dtypes, fmt):
        del shapes, dtypes, fmt
        return _MemoryObj(size=64)


def _skip_unless_live_enabled():
    if os.environ.get("LMCACHE_COUCHBASE_LIVE_TESTS") != "1":
        pytest.skip("set LMCACHE_COUCHBASE_LIVE_TESTS=1 to run live Couchbase test")


@pytest.mark.live
def test_live_couchbase_store_roundtrip():
    _skip_unless_live_enabled()

    store = CouchbaseKVStore(CouchbaseLMCacheConfig.from_env())
    key = _Key("pytest-live-store")
    payload = b"live-couchbase-lmcache"
    try:
        store.put_bytes(key, payload)
        assert store.exists(key)
        assert store.get_bytes(key) == payload
        assert store.remove(key)
    finally:
        store.remove(key)
        store.close()


async def _exercise_live_connector():
    cfg = CouchbaseLMCacheConfig.from_env()
    extra_config = {
        "remote_storage_plugin.couchbase.connection_string": cfg.connection_string,
        "remote_storage_plugin.couchbase.username": cfg.username,
        "remote_storage_plugin.couchbase.password": cfg.password,
        "remote_storage_plugin.couchbase.bucket_name": cfg.bucket_name,
        "remote_storage_plugin.couchbase.scope_name": cfg.scope_name,
        "remote_storage_plugin.couchbase.collection_name": cfg.collection_name,
        "remote_storage_plugin.couchbase.key_prefix": cfg.key_prefix,
        "remote_storage_plugin.couchbase.ttl_seconds": cfg.ttl_seconds,
    }
    connector = CouchbaseConnector(
        loop=asyncio.get_running_loop(),
        local_cpu_backend=_LocalCPUBackend(),
        config=SimpleNamespace(extra_config=extra_config),
        plugin_name="couchbase",
    )
    # Raw byte payloads: tensor round trips are covered by
    # test_lmcache_remote_backend.py with real LMCache objects.
    connector.save_chunk_meta = False
    connector.meta_shapes = []
    connector.meta_dtypes = []
    connector.meta_fmt = None
    connector.reshape_partial_chunk = lambda memory_obj, bytes_read: memory_obj
    key = _Key("pytest-live-connector")
    missing = _Key("pytest-live-connector-missing")
    payload = b"connector-live-roundtrip"
    try:
        assert not await connector.exists(missing)
        await connector.put(key, _MemoryObj(payload=payload))
        assert await connector.exists(key)
        assert connector.exists_sync(key)
        got = await connector.get(key)
        assert got is not None
        assert bytes(got.byte_array[: len(payload)]) == payload
        assert connector.batched_contains([key, missing]) == 1
        assert await connector.batched_async_contains("lookup", [key, missing]) == 1
    finally:
        connector.store.remove(key)
        await connector.close()


@pytest.mark.live
def test_live_couchbase_connector_roundtrip():
    _skip_unless_live_enabled()

    asyncio.run(_exercise_live_connector())


@pytest.mark.live
def test_live_couchbase_store_shards_payload_above_document_limit():
    """A 25 MiB chunk exceeds Couchbase's 20 MiB item limit and must be sharded."""

    _skip_unless_live_enabled()

    store = CouchbaseKVStore(CouchbaseLMCacheConfig.from_env())
    key = _Key("pytest-live-sharded")
    payload = os.urandom(25 * 1024 * 1024)
    try:
        store.put_bytes(key, payload)
        assert store.exists(key)
        assert store.exists(_Key("pytest-live-sharded::shard::1"))
        assert store.get_bytes(key) == payload
        assert store.remove(key)
        assert not store.exists(_Key("pytest-live-sharded::shard::0"))
    finally:
        store.remove(key)
        store.close()
