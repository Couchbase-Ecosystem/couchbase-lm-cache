# SPDX-License-Identifier: Apache-2.0

import os

import pytest

from couchbase_lm_cache import CouchbaseKVStore, CouchbaseLMCacheConfig


class _Key:
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return self.value


@pytest.mark.live
def test_live_couchbase_roundtrip():
    if os.environ.get("LMCACHE_COUCHBASE_LIVE_TESTS") != "1":
        pytest.skip("set LMCACHE_COUCHBASE_LIVE_TESTS=1 to run live Couchbase test")

    store = CouchbaseKVStore(CouchbaseLMCacheConfig.from_env())
    key = _Key("pytest-live")
    payload = b"live-couchbase-lmcache"
    store.put_bytes(key, payload)
    assert store.exists(key)
    assert store.get_bytes(key) == payload
    assert store.remove(key)
    store.close()
