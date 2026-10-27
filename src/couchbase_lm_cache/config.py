# SPDX-License-Identifier: Apache-2.0
"""Configuration helpers for the LMCache Couchbase connector."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from os import environ
from typing import Any

_PLUGIN_PREFIX = "remote_storage_plugin"
_ENV_PREFIX = "LMCACHE_COUCHBASE_"
# Payloads above this size are split across several documents. Couchbase Server
# caps documents at 20 MiB (one 256-token chunk of an 8B model is ~36 MiB), and
# ~1 MiB documents read about twice as fast as 16 MiB ones.
DEFAULT_SHARD_SIZE_BYTES = 1024 * 1024
DEFAULT_MAX_WORKERS = 32
# The SDK default (2.5 s) is tuned for small documents; a 16 MiB shard read
# from disk on a full-eviction bucket can take longer.
DEFAULT_KV_TIMEOUT_SECONDS = 10.0


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    return int(value)


def _as_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class CouchbaseLMCacheConfig:
    """Connection and behavior settings for Couchbase-backed LMCache storage.

    Values can come from LMCache ``extra_config`` keys named
    ``remote_storage_plugin.<plugin_name>.<field>`` or from environment variables
    with the ``LMCACHE_COUCHBASE_`` prefix.
    """

    connection_string: str
    username: str
    password: str
    bucket_name: str
    scope_name: str = "_default"
    collection_name: str = "_default"
    key_prefix: str = "lmcache:"
    ttl_seconds: int | None = None
    kv_timeout_seconds: float = DEFAULT_KV_TIMEOUT_SECONDS
    connect_timeout_seconds: float = 10.0
    max_workers: int = DEFAULT_MAX_WORKERS
    shard_size_bytes: int = DEFAULT_SHARD_SIZE_BYTES

    @classmethod
    def from_env(cls) -> CouchbaseLMCacheConfig:
        """Build configuration from environment variables.

        Raises:
            ValueError: if required variables are absent.
        """

        return cls._build(lambda field: None)

    @classmethod
    def from_lmcache_extra_config(
        cls,
        extra_config: dict[str, Any] | None,
        plugin_name: str = "couchbase",
    ) -> CouchbaseLMCacheConfig:
        """Build configuration from LMCache ``extra_config`` plus env fallback.

        Args:
            extra_config: LMCache ``LMCacheEngineConfig.extra_config`` mapping.
            plugin_name: Remote storage plugin name, for example ``couchbase`` or
                ``couchbase.primary``.

        Raises:
            ValueError: if required connection fields are absent.
        """

        extra_config = extra_config or {}

        def get(field: str) -> Any:
            specific = f"{_PLUGIN_PREFIX}.{plugin_name}.{field}"
            if specific in extra_config:
                return extra_config[specific]
            plugin_type = plugin_name.split(".", 1)[0]
            return extra_config.get(f"{_PLUGIN_PREFIX}.{plugin_type}.{field}")

        return cls._build(get)

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> CouchbaseLMCacheConfig:
        """Build configuration from plain field names plus env fallback.

        Used by the LMCache multiprocess-mode L2 adapter, whose
        ``adapter_params`` use the same field names as ``extra_config``
        without the ``remote_storage_plugin.<name>.`` prefix.

        Raises:
            ValueError: if required connection fields are absent.
        """

        values = values or {}
        return cls._build(values.get)

    @classmethod
    def _build(cls, lookup: Callable[[str], Any]) -> CouchbaseLMCacheConfig:
        def get(field: str, env_name: str | None = None, default: Any = None) -> Any:
            value = lookup(field)
            if value is not None:
                return value
            return environ.get(_ENV_PREFIX + (env_name or field).upper(), default)

        return cls(
            connection_string=_required_value(
                get("connection_string", "CONNSTR"), "connection_string"
            ),
            username=_required_value(get("username"), "username"),
            password=_required_value(get("password"), "password"),
            bucket_name=_required_value(get("bucket_name", "BUCKET"), "bucket_name"),
            scope_name=str(get("scope_name", "SCOPE", "_default")),
            collection_name=str(get("collection_name", "COLLECTION", "_default")),
            key_prefix=str(get("key_prefix", "KEY_PREFIX", "lmcache:")),
            ttl_seconds=_as_int(get("ttl_seconds", "TTL_SECONDS")),
            kv_timeout_seconds=_as_float(
                get("kv_timeout_seconds", "KV_TIMEOUT_SECONDS"),
                DEFAULT_KV_TIMEOUT_SECONDS,
            ),
            connect_timeout_seconds=_as_float(
                get("connect_timeout_seconds", "CONNECT_TIMEOUT_SECONDS"), 10.0
            ),
            max_workers=_as_int(get("max_workers", "MAX_WORKERS"), DEFAULT_MAX_WORKERS)
            or DEFAULT_MAX_WORKERS,
            shard_size_bytes=_as_int(
                get("shard_size_bytes", "SHARD_SIZE_BYTES"), DEFAULT_SHARD_SIZE_BYTES
            )
            or DEFAULT_SHARD_SIZE_BYTES,
        )

    def redacted(self) -> dict[str, Any]:
        """Return a safe dictionary for logging or support output."""

        return {
            "connection_string": self.connection_string,
            "username": self.username,
            "password": "***" if self.password else "",
            "bucket_name": self.bucket_name,
            "scope_name": self.scope_name,
            "collection_name": self.collection_name,
            "key_prefix": self.key_prefix,
            "ttl_seconds": self.ttl_seconds,
            "kv_timeout_seconds": self.kv_timeout_seconds,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "max_workers": self.max_workers,
            "shard_size_bytes": self.shard_size_bytes,
        }


def _required_value(value: Any, name: str) -> str:
    if value is None or str(value) == "":
        raise ValueError(f"Missing required Couchbase LMCache setting: {name}")
    return str(value)
