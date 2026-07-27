# SPDX-License-Identifier: Apache-2.0
"""Low-level Couchbase KV byte store used by the LMCache connector."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.exceptions import DocumentNotFoundException
from couchbase.options import (
    ClusterOptions,
    ClusterTimeoutOptions,
    GetOptions,
    UpsertOptions,
)
from couchbase.transcoder import RawBinaryTranscoder

from couchbase_lm_cache.config import CouchbaseLMCacheConfig


class CouchbaseKVStore:
    """A binary KV store for LMCache chunk payloads.

    The store uses Couchbase KV operations only. It does not require SQL++
    indexes for normal LMCache reads and writes.
    """

    def __init__(self, config: CouchbaseLMCacheConfig):
        """Create a store and open a Couchbase SDK connection."""

        self.config = config
        timeout_options = ClusterTimeoutOptions(
            kv_timeout=timedelta(seconds=config.kv_timeout_seconds),
            connect_timeout=timedelta(seconds=config.connect_timeout_seconds),
        )
        authenticator = PasswordAuthenticator(config.username, config.password)
        self.cluster = Cluster(
            config.connection_string,
            ClusterOptions(authenticator, timeout_options=timeout_options),
        )
        ready_timeout = timedelta(seconds=config.connect_timeout_seconds)
        if hasattr(self.cluster, "wait_until_ready"):
            self.cluster.wait_until_ready(ready_timeout)
        self.bucket = self.cluster.bucket(config.bucket_name)
        if hasattr(self.bucket, "wait_until_ready"):
            self.bucket.wait_until_ready(ready_timeout)
        self.collection = self.bucket.scope(config.scope_name).collection(
            config.collection_name
        )
        self._transcoder = RawBinaryTranscoder()

    def build_key(self, key: object) -> str:
        """Convert an LMCache key-like object into a Couchbase document key."""

        key_text = key.to_string() if hasattr(key, "to_string") else str(key)
        return self.config.key_prefix + key_text

    def put_bytes(self, key: object, payload: bytes | bytearray | memoryview) -> None:
        """Upsert a raw binary payload into Couchbase."""

        expiry = None
        if self.config.ttl_seconds is not None and self.config.ttl_seconds > 0:
            expiry = timedelta(seconds=self.config.ttl_seconds)
        data = bytes(payload)
        self.collection.upsert(
            self.build_key(key),
            data,
            UpsertOptions(expiry=expiry, transcoder=self._transcoder),
        )

    def get_bytes(self, key: object) -> bytes | None:
        """Fetch raw binary payload bytes, or ``None`` when absent."""

        try:
            result = self.collection.get(
                self.build_key(key), GetOptions(transcoder=self._transcoder)
            )
        except DocumentNotFoundException:
            return None
        content = result.content_as[bytes]
        return bytes(content)

    def exists(self, key: object) -> bool:
        """Return whether a payload exists for the given key."""

        return bool(self.collection.exists(self.build_key(key)).exists)

    def remove(self, key: object) -> bool:
        """Remove a payload and report whether it existed."""

        try:
            self.collection.remove(self.build_key(key))
        except DocumentNotFoundException:
            return False
        return True

    def put_many(self, keys: Iterable[object], payloads: Iterable[bytes]) -> None:
        """Store multiple payloads sequentially.

        Couchbase Python SDK asynchronous bulk APIs vary by SDK family; the
        connector parallelizes calls at the LMCache layer instead of depending on
        a bulk helper that may not exist in every supported SDK version.
        """

        for key, payload in zip(keys, payloads, strict=True):
            self.put_bytes(key, payload)

    def close(self) -> None:
        """Close the SDK cluster connection."""

        self.cluster.close()
