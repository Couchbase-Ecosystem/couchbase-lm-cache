# SPDX-License-Identifier: Apache-2.0
"""Smoke test the Couchbase byte store without starting vLLM/LMCache."""

from __future__ import annotations

import os

from couchbase_lm_cache import CouchbaseKVStore, CouchbaseLMCacheConfig


class DemoKey:
    def __init__(self, value: str):
        self.value = value

    def to_string(self) -> str:
        return self.value


if __name__ == "__main__":
    cfg = CouchbaseLMCacheConfig.from_env()
    store = CouchbaseKVStore(cfg)
    key = DemoKey("demo-chunk")
    payload = b"lmcache-couchbase-demo"
    store.put_bytes(key, payload)
    round_trip = store.get_bytes(key)
    assert round_trip == payload, round_trip
    assert store.exists(key)
    if os.environ.get("LMCACHE_COUCHBASE_REMOVE_DEMO", "1") == "1":
        store.remove(key)
    store.close()
    print("Couchbase LMCache store smoke test passed")
