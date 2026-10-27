# SPDX-License-Identifier: Apache-2.0

import pytest
from couchbase.exceptions import DocumentNotFoundException
from couchbase.transcoder import FMT_BYTES, FMT_JSON

from couchbase_lm_cache.config import CouchbaseLMCacheConfig
from couchbase_lm_cache.store import COUCHBASE_MAX_DOCUMENT_BYTES, CouchbaseKVStore


class _Result:
    def __init__(self, value=b"", exists: bool = True):
        self.value = value
        self.exists = exists


class _FakeCollection:
    def __init__(self):
        self.docs = {}
        self.expiry = {}

    def upsert(self, key, value, opts):
        # Mirror the SDK: encode with the transcoder and keep the document flags.
        self.docs[key] = opts["transcoder"].encode_value(value)
        self.expiry[key] = opts["expiry"]

    def get(self, key, opts):
        if key not in self.docs:
            raise DocumentNotFoundException()
        return _Result(opts["transcoder"].decode_value(*self.docs[key]))

    def exists(self, key):
        return _Result(exists=key in self.docs)

    def remove(self, key):
        if key not in self.docs:
            raise DocumentNotFoundException()
        del self.docs[key]

    def payload(self, key):
        return self.docs[key][0]


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


def _make_store(monkeypatch, **overrides):
    collection = _FakeCollection()
    fake_cluster = _FakeCluster(collection)

    def fake_cluster_factory(*args, **kwargs):
        del args, kwargs
        return fake_cluster

    monkeypatch.setattr("couchbase_lm_cache.store.Cluster", fake_cluster_factory)
    # The fake collection reads options by name, as the SDK's options do.
    monkeypatch.setattr("couchbase_lm_cache.store.UpsertOptions", dict)
    monkeypatch.setattr("couchbase_lm_cache.store.GetOptions", dict)
    cfg = CouchbaseLMCacheConfig(
        connection_string="couchbase://localhost",
        username="Administrator",
        password="password",
        bucket_name="lmcache",
        key_prefix="test:",
        **overrides,
    )
    return CouchbaseKVStore(cfg), collection, fake_cluster


def test_store_binary_roundtrip_with_fake_collection(monkeypatch):
    store, collection, fake_cluster = _make_store(monkeypatch)
    key = _Key()
    store.put_bytes(key, b"payload")

    assert collection.docs["test:abc"] == (b"payload", FMT_BYTES)
    assert store.exists(key)
    assert store.get_bytes(key) == b"payload"
    assert store.remove(key)
    assert not store.exists(key)
    assert not store.remove(key)
    assert store.get_bytes(key) is None
    store.close()
    assert fake_cluster.closed


def test_store_applies_ttl_only_when_positive(monkeypatch):
    store, collection, _ = _make_store(monkeypatch, ttl_seconds=60)
    store.put_bytes(_Key(), b"x")
    assert collection.expiry["test:abc"].total_seconds() == 60

    store, collection, _ = _make_store(monkeypatch, ttl_seconds=0)
    store.put_bytes(_Key(), b"x")
    assert collection.expiry["test:abc"] is None


def test_store_shards_payloads_above_shard_size(monkeypatch):
    store, collection, _ = _make_store(monkeypatch, shard_size_bytes=4)
    key = _Key()
    payload = b"0123456789"

    store.put_bytes(key, payload)

    manifest, flags = collection.docs["test:abc"]
    assert flags == FMT_JSON
    assert b'"lmcache_shards":3' in manifest
    assert [collection.payload(f"test:abc::shard::{i}") for i in range(3)] == [
        b"0123",
        b"4567",
        b"89",
    ]
    assert store.exists(key)
    assert store.get_bytes(key) == payload

    assert store.remove(key)
    assert collection.docs == {}


def test_store_payload_at_shard_size_is_not_sharded(monkeypatch):
    store, collection, _ = _make_store(monkeypatch, shard_size_bytes=4)
    store.put_bytes(_Key(), memoryview(b"0123"))

    assert collection.docs == {"test:abc": (b"0123", FMT_BYTES)}


def test_store_treats_missing_shard_as_miss(monkeypatch):
    store, collection, _ = _make_store(monkeypatch, shard_size_bytes=4)
    key = _Key()
    store.put_bytes(key, b"0123456789")
    del collection.docs["test:abc::shard::1"]

    assert store.get_bytes(key) is None
    assert store.remove(key)
    assert collection.docs == {}


@pytest.mark.parametrize("shard_size", [0, COUCHBASE_MAX_DOCUMENT_BYTES + 1])
def test_store_rejects_invalid_shard_size(monkeypatch, shard_size):
    with pytest.raises(ValueError, match="shard_size_bytes"):
        _make_store(monkeypatch, shard_size_bytes=shard_size)


class _Endpoint:
    def __init__(self, state):
        self.state = state


def test_store_ping_reports_kv_endpoint_health(monkeypatch):
    from couchbase.diagnostics import PingState, ServiceType

    store, _, _ = _make_store(monkeypatch)
    report = type("Report", (), {})()
    store.bucket.ping = lambda opts: report

    report.endpoints = {ServiceType.KeyValue: [_Endpoint(PingState.OK)]}
    assert store.ping()
    report.endpoints = {ServiceType.KeyValue: [_Endpoint(PingState.TIMEOUT)]}
    assert not store.ping()
    report.endpoints = {}
    assert not store.ping()


def test_store_remove_measured_reports_payload_size(monkeypatch):
    store, _, _ = _make_store(monkeypatch, shard_size_bytes=4)

    store.put_bytes(_Key(), b"0123456789")
    assert store.remove_measured(_Key()) == 10
    store.put_bytes(_Key(), b"abc")
    assert store.remove_measured(_Key()) == 3
    assert store.remove_measured(_Key()) is None
