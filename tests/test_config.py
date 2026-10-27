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


def test_config_shard_size_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("LMCACHE_COUCHBASE_SHARD_SIZE_BYTES", raising=False)
    base = {
        "remote_storage_plugin.couchbase.connection_string": "couchbase://cb",
        "remote_storage_plugin.couchbase.username": "u",
        "remote_storage_plugin.couchbase.password": "p",
        "remote_storage_plugin.couchbase.bucket_name": "b",
    }
    cfg = CouchbaseLMCacheConfig.from_lmcache_extra_config(base)
    assert cfg.shard_size_bytes == 1024 * 1024

    cfg = CouchbaseLMCacheConfig.from_lmcache_extra_config(
        {**base, "remote_storage_plugin.couchbase.shard_size_bytes": "1048576"}
    )
    assert cfg.shard_size_bytes == 1048576
    assert cfg.redacted()["shard_size_bytes"] == 1048576


def test_config_requires_connection_settings(monkeypatch):
    for name in ("CONNSTR", "USERNAME", "PASSWORD", "BUCKET"):
        monkeypatch.delenv(f"LMCACHE_COUCHBASE_{name}", raising=False)
    try:
        CouchbaseLMCacheConfig.from_lmcache_extra_config({})
    except ValueError as exc:
        assert "connection_string" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("missing settings were accepted")
