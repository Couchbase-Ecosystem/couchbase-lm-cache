# SPDX-License-Identifier: Apache-2.0

import asyncio
from types import SimpleNamespace

from couchbase_lm_cache.connector import CouchbaseConnector


class _MemoryObj:
    def __init__(self, size=16):
        self.buffer = bytearray(size)
        self.byte_array = memoryview(self.buffer)


class _LocalCPUBackend:
    config = SimpleNamespace(extra_config={})
    metadata = object()

    def allocate(self, shapes, dtypes, fmt):
        del shapes, dtypes, fmt
        return _MemoryObj()


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
