# SPDX-License-Identifier: Apache-2.0
"""Low-level Couchbase KV byte store used by the LMCache connector."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.diagnostics import PingState, ServiceType
from couchbase.exceptions import DocumentNotFoundException
from couchbase.options import (
    ClusterOptions,
    ClusterTimeoutOptions,
    GetOptions,
    PingOptions,
    UpsertOptions,
)
from couchbase.transcoder import (
    FMT_BYTES,
    FMT_JSON,
    Transcoder,
    ValueFormatException,
    get_decode_format,
)

from couchbase_lm_cache.config import CouchbaseLMCacheConfig

# Couchbase Server rejects values above 20 MiB; shard well below that.
COUCHBASE_MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
_MANIFEST_FIELD = "lmcache_shards"


class _ChunkTranscoder(Transcoder):
    """Binary chunks use the binary flag; shard manifests are JSON documents.

    Document flags, not payload bytes, tell the two apart, so an arbitrary KV
    payload can never be mistaken for a manifest.
    """

    def encode_value(self, value: Any) -> tuple[bytes, int]:
        if isinstance(value, dict):
            return json.dumps(value, separators=(",", ":")).encode(), FMT_JSON
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value), FMT_BYTES
        raise ValueFormatException("Only bytes or shard manifests are supported")

    def decode_value(self, value: bytes, flags: int) -> Any:
        fmt = get_decode_format(flags)
        if fmt == FMT_BYTES:
            return bytes(value)
        if fmt == FMT_JSON:
            return json.loads(value)
        raise ValueFormatException(f"Unexpected LMCache document format: {fmt}")


class CouchbaseKVStore:
    """A binary KV store for LMCache chunk payloads.

    The store uses Couchbase KV operations only. It does not require SQL++
    indexes for normal LMCache reads and writes.

    Payloads up to ``shard_size_bytes`` are stored as one binary document.
    Larger payloads, for example a 256-token chunk of an 8B model, are split
    into ``<key>::shard::<n>`` binary documents plus a small JSON manifest at
    ``<key>``. Shards are written before the manifest, so readers never see a
    manifest whose shards were not written yet.
    """

    def __init__(self, config: CouchbaseLMCacheConfig):
        """Create a store and open a Couchbase SDK connection."""

        if not 0 < config.shard_size_bytes <= COUCHBASE_MAX_DOCUMENT_BYTES:
            raise ValueError(
                "shard_size_bytes must be between 1 and "
                f"{COUCHBASE_MAX_DOCUMENT_BYTES}, got {config.shard_size_bytes}"
            )
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
        self._transcoder = _ChunkTranscoder()

    def build_key(self, key: object) -> str:
        """Convert an LMCache key-like object into a Couchbase document key."""

        key_text = key.to_string() if hasattr(key, "to_string") else str(key)
        return self.config.key_prefix + key_text

    @staticmethod
    def shard_key(doc_key: str, index: int) -> str:
        """Return the document key of one shard of a large payload."""

        return f"{doc_key}::shard::{index}"

    def _upsert(self, doc_key: str, value: Any) -> None:
        expiry = None
        if self.config.ttl_seconds is not None and self.config.ttl_seconds > 0:
            expiry = timedelta(seconds=self.config.ttl_seconds)
        self.collection.upsert(
            doc_key, value, UpsertOptions(expiry=expiry, transcoder=self._transcoder)
        )

    def _get(self, doc_key: str) -> Any:
        try:
            result = self.collection.get(
                doc_key, GetOptions(transcoder=self._transcoder)
            )
        except DocumentNotFoundException:
            return None
        return result.value

    def put_bytes(self, key: object, payload: bytes | bytearray | memoryview) -> None:
        """Upsert a raw binary payload into Couchbase, sharding if needed."""

        doc_key = self.build_key(key)
        data = memoryview(payload).cast("B")
        shard_size = self.config.shard_size_bytes
        if len(data) <= shard_size:
            self._upsert(doc_key, bytes(data))
            return
        shard_count = -(-len(data) // shard_size)
        for index in range(shard_count):
            start = index * shard_size
            self._upsert(
                self.shard_key(doc_key, index), bytes(data[start : start + shard_size])
            )
        self._upsert(doc_key, {_MANIFEST_FIELD: shard_count, "bytes": len(data)})

    def get_bytes(self, key: object) -> bytes | None:
        """Fetch raw binary payload bytes, or ``None`` when absent."""

        doc_key = self.build_key(key)
        document = self._get(doc_key)
        if not isinstance(document, dict):
            return document
        parts = []
        for index in range(int(document[_MANIFEST_FIELD])):
            part = self._get(self.shard_key(doc_key, index))
            if not isinstance(part, bytes):
                # A shard expired or was evicted: treat the chunk as a miss.
                return None
            parts.append(part)
        data = b"".join(parts)
        if len(data) != int(document["bytes"]):
            return None
        return data

    def exists(self, key: object) -> bool:
        """Return whether a payload exists for the given key."""

        return bool(self.collection.exists(self.build_key(key)).exists)

    def remove(self, key: object) -> bool:
        """Remove a payload, including any shards, and report whether it existed."""

        return self.remove_measured(key) is not None

    def remove_measured(self, key: object) -> int | None:
        """Remove a payload and its shards; return its size, or ``None`` if absent."""

        doc_key = self.build_key(key)
        document = self._get(doc_key)
        try:
            self.collection.remove(doc_key)
        except DocumentNotFoundException:
            return None
        if not isinstance(document, dict):
            return len(document or b"")
        for index in range(int(document[_MANIFEST_FIELD])):
            with contextlib.suppress(DocumentNotFoundException):
                self.collection.remove(self.shard_key(doc_key, index))
        return int(document["bytes"])

    def put_many(self, keys: Iterable[object], payloads: Iterable[bytes]) -> None:
        """Store multiple payloads sequentially.

        Couchbase Python SDK asynchronous bulk APIs vary by SDK family; the
        connector parallelizes calls at the LMCache layer instead of depending on
        a bulk helper that may not exist in every supported SDK version.
        """

        for key, payload in zip(keys, payloads, strict=True):
            self.put_bytes(key, payload)

    def ping(self) -> bool:
        """Return whether every reachable KV endpoint for the bucket answers."""

        try:
            report = self.bucket.ping(PingOptions(service_types=[ServiceType.KeyValue]))
        except Exception:
            return False
        endpoints = report.endpoints.get(ServiceType.KeyValue, [])
        return bool(endpoints) and all(
            endpoint.state == PingState.OK for endpoint in endpoints
        )

    def close(self) -> None:
        """Close the SDK cluster connection."""

        self.cluster.close()
