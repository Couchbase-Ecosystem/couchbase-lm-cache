# SPDX-License-Identifier: Apache-2.0
"""Configuration helpers for the LMCache Couchbase connector."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Any

_PLUGIN_PREFIX = "remote_storage_plugin"
_ENV_PREFIX = "LMCACHE_COUCHBASE_"


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
    kv_timeout_seconds: float = 2.5
    connect_timeout_seconds: float = 10.0
    max_workers: int = 16
    create_primary_index: bool = False

    @classmethod
    def from_env(cls) -> CouchbaseLMCacheConfig:
        """Build configuration from environment variables.

        Raises:
            ValueError: if required variables are absent.
        """

        return cls(
            connection_string=_required_env("CONNSTR"),
            username=_required_env("USERNAME"),
            password=_required_env("PASSWORD"),
            bucket_name=_required_env("BUCKET"),
            scope_name=environ.get(_ENV_PREFIX + "SCOPE", "_default"),
            collection_name=environ.get(_ENV_PREFIX + "COLLECTION", "_default"),
            key_prefix=environ.get(_ENV_PREFIX + "KEY_PREFIX", "lmcache:"),
            ttl_seconds=_as_int(environ.get(_ENV_PREFIX + "TTL_SECONDS")),
            kv_timeout_seconds=_as_float(
                environ.get(_ENV_PREFIX + "KV_TIMEOUT_SECONDS"), 2.5
            ),
            connect_timeout_seconds=_as_float(
                environ.get(_ENV_PREFIX + "CONNECT_TIMEOUT_SECONDS"), 10.0
            ),
            max_workers=_as_int(environ.get(_ENV_PREFIX + "MAX_WORKERS"), 16) or 16,
            create_primary_index=_as_bool(
                environ.get(_ENV_PREFIX + "CREATE_PRIMARY_INDEX"), False
            ),
        )

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

        def get(field: str, env_name: str | None = None, default: Any = None) -> Any:
            specific = f"{_PLUGIN_PREFIX}.{plugin_name}.{field}"
            if specific in extra_config:
                return extra_config[specific]
            plugin_type = plugin_name.split(".", 1)[0]
            generic = f"{_PLUGIN_PREFIX}.{plugin_type}.{field}"
            if generic in extra_config:
                return extra_config[generic]
            env_key = _ENV_PREFIX + (env_name or field).upper()
            return environ.get(env_key, default)

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
                get("kv_timeout_seconds", "KV_TIMEOUT_SECONDS"), 2.5
            ),
            connect_timeout_seconds=_as_float(
                get("connect_timeout_seconds", "CONNECT_TIMEOUT_SECONDS"), 10.0
            ),
            max_workers=_as_int(get("max_workers", "MAX_WORKERS"), 16) or 16,
            create_primary_index=_as_bool(
                get("create_primary_index", "CREATE_PRIMARY_INDEX"), False
            ),
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
            "create_primary_index": self.create_primary_index,
        }


def _required_env(name: str) -> str:
    return _required_value(environ.get(_ENV_PREFIX + name), name)


def _required_value(value: Any, name: str) -> str:
    if value is None or str(value) == "":
        raise ValueError(f"Missing required Couchbase LMCache setting: {name}")
    return str(value)
