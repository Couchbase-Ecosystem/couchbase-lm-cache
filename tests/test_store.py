# SPDX-License-Identifier: Apache-2.0

from couchbase_lm_cache.config import CouchbaseLMCacheConfig
from couchbase_lm_cache.store import CouchbaseKVStore


class _ContentAs:
    def __init__(self, data: bytes):
        self.data = data

    def __getitem__(self, item):
        assert item is bytes
        return self.data


class _Result:
    def __init__(self, data: bytes = b"", exists: bool = True):
        self.content_as = _ContentAs(data)
        self.exists = exists


class _FakeCollection:
    def __init__(self):
        self.docs = {}

    def upsert(self, key, value, opts):
        del opts
        self.docs[key] = bytes(value)

    def get(self, key, opts):
        del opts
        return _Result(self.docs[key])

    def exists(self, key):
        return _Result(exists=key in self.docs)

    def remove(self, key):
        del self.docs[key]


class _FakeScope:
    def __init__(self, collection):
        self._collection = collection

    def collection(self, name):
        assert name == "_default"
        return self._collection


class _FakeBucket:
    def __init__(self, collection):
        self._collection = collection

    def wait_until_ready(self, timeout):
        assert timeout.total_seconds() > 0

    def scope(self, name):
        assert name == "_default"
        return _FakeScope(self._collection)


class _FakeCluster:
    def __init__(self, collection):
        self.collection = collection
        self.closed = False

    def bucket(self, name):
        assert name == "lmcache"
        return _FakeBucket(self.collection)

    def close(self):
        self.closed = True


class _Key:
    def to_string(self):
        return "abc"


def test_store_binary_roundtrip_with_fake_collection(monkeypatch):
    collection = _FakeCollection()
    fake_cluster = _FakeCluster(collection)

    def fake_cluster_factory(*args, **kwargs):
        del args, kwargs
        return fake_cluster

    monkeypatch.setattr("couchbase_lm_cache.store.Cluster", fake_cluster_factory)
    cfg = CouchbaseLMCacheConfig(
        connection_string="couchbase://localhost",
        username="Administrator",
        password="password",
        bucket_name="lmcache",
        key_prefix="test:",
    )

    store = CouchbaseKVStore(cfg)
    key = _Key()
    store.put_bytes(key, b"payload")

    assert collection.docs["test:abc"] == b"payload"
    assert store.exists(key)
    assert store.get_bytes(key) == b"payload"
    assert store.remove(key)
    assert not store.exists(key)
    store.close()
    assert fake_cluster.closed
