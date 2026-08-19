# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
from types import SimpleNamespace

import pytest

from couchbase_lm_cache import CouchbaseKVStore, CouchbaseLMCacheConfig
from couchbase_lm_cache.connector import CouchbaseConnector


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
    connector.meta_shapes = []
    connector.meta_dtypes = []
    connector.meta_fmt = None
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
