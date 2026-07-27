# SPDX-License-Identifier: Apache-2.0

from couchbase_lm_cache.config import CouchbaseLMCacheConfig


def test_config_from_extra_config_prefers_plugin_specific_values(monkeypatch):
    monkeypatch.setenv("LMCACHE_COUCHBASE_PASSWORD", "env-password")
    cfg = CouchbaseLMCacheConfig.from_lmcache_extra_config(
        {
            "remote_storage_plugin.couchbase.connection_string": "couchbase://localhost",
            "remote_storage_plugin.couchbase.username": "Administrator",
            "remote_storage_plugin.couchbase.bucket_name": "lmcache",
            "remote_storage_plugin.couchbase.ttl_seconds": "60",
            "remote_storage_plugin.couchbase.max_workers": "4",
        },
        "couchbase",
    )

    assert cfg.connection_string == "couchbase://localhost"
    assert cfg.username == "Administrator"
    assert cfg.password == "env-password"
    assert cfg.bucket_name == "lmcache"
    assert cfg.ttl_seconds == 60
    assert cfg.max_workers == 4
    assert cfg.redacted()["password"] == "***"


def test_config_supports_named_plugin_instances(monkeypatch):
    monkeypatch.delenv("LMCACHE_COUCHBASE_PASSWORD", raising=False)
    cfg = CouchbaseLMCacheConfig.from_lmcache_extra_config(
        {
            "remote_storage_plugin.couchbase.primary.connection_string": "couchbase://cb",
            "remote_storage_plugin.couchbase.primary.username": "u",
            "remote_storage_plugin.couchbase.primary.password": "p",
            "remote_storage_plugin.couchbase.primary.bucket_name": "b",
            "remote_storage_plugin.couchbase.primary.key_prefix": "primary:",
        },
        "couchbase.primary",
    )

    assert cfg.connection_string == "couchbase://cb"
    assert cfg.bucket_name == "b"
    assert cfg.key_prefix == "primary:"
