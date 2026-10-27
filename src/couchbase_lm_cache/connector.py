# SPDX-License-Identifier: Apache-2.0
"""LMCache RemoteConnector implementation backed by Couchbase KV."""

from __future__ import annotations

import asyncio
import builtins
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from couchbase_lm_cache.config import CouchbaseLMCacheConfig
from couchbase_lm_cache.store import CouchbaseKVStore

try:  # pragma: no cover - exercised when installed alongside LMCache
    from lmcache.logging import init_logger
    from lmcache.utils import CacheEngineKey
    from lmcache.v1.memory_management import MemoryObj
    from lmcache.v1.protocol import RemoteMetadata
    from lmcache.v1.storage_backend.connector.base_connector import RemoteConnector

    _HAS_LMCACHE = True
except Exception:  # pragma: no cover - unit tests run without heavy LMCache deps
    CacheEngineKey = Any  # type: ignore[misc,assignment]
    MemoryObj = Any  # type: ignore[misc,assignment]
    RemoteMetadata = None  # type: ignore[misc,assignment]

    class RemoteConnector:  # type: ignore[no-redef]
        """Fallback base so unit tests can run without LMCache installed."""

        save_chunk_meta = False
        remote_metadata_bytes = 0

        def reshape_partial_chunk(self, memory_obj: Any, bytes_read: int) -> Any:
            del bytes_read
            return memory_obj

    _HAS_LMCACHE = False
    init_logger = logging.getLogger

logger = init_logger(__name__)


def _byte_view(memory_obj: Any) -> memoryview:
    """Return a flat unsigned-byte view over a ``MemoryObj`` buffer."""

    buffer = memory_obj.byte_array
    view = buffer if isinstance(buffer, memoryview) else memoryview(buffer)
    if view.format != "B":
        view = view.cast("B")
    return view


def _release(memory_obj: Any) -> None:
    release = getattr(memory_obj, "ref_count_down", None)
    if release is not None:
        release()


class CouchbaseConnector(RemoteConnector):
    """LMCache remote storage connector that stores chunks in Couchbase KV.

    This class is loaded by LMCache with ``remote_storage_plugins`` and implements
    the ``RemoteConnector`` methods expected by ``RemoteBackend``.

    Each LMCache chunk is one binary Couchbase document. When LMCache's
    ``save_chunk_meta`` is enabled (the LMCache default), the document starts with
    LMCache's serialized ``RemoteMetadata`` header followed by the chunk bytes, so
    header and payload are always written and expired atomically.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        local_cpu_backend: Any,
        config: Any,
        plugin_name: str | None = None,
    ) -> None:
        """Initialize the connector.

        Args:
            loop: LMCache event loop.
            local_cpu_backend: LMCache local CPU backend used to allocate buffers
                for retrieved objects.
            config: LMCache engine config containing ``extra_config``.
            plugin_name: Name from ``remote_storage_plugins``; defaults to
                ``couchbase``.
        """

        if _HAS_LMCACHE:
            super().__init__(local_cpu_backend.config, local_cpu_backend.metadata)
        self.loop = loop
        self.local_cpu_backend = local_cpu_backend
        self.config = config
        configured_plugins = getattr(config, "remote_storage_plugins", None) or []
        inferred_plugin_name = (
            configured_plugins[0] if len(configured_plugins) == 1 else "couchbase"
        )
        self.plugin_name = plugin_name or inferred_plugin_name
        extra_config = getattr(config, "extra_config", None)
        self.cfg = CouchbaseLMCacheConfig.from_lmcache_extra_config(
            extra_config, self.plugin_name
        )
        self.store = CouchbaseKVStore(self.cfg)
        self.executor = ThreadPoolExecutor(
            max_workers=self.cfg.max_workers, thread_name_prefix="couchbase-lmcache"
        )
        logger.info(
            "Couchbase LMCache connector ready: %s (save_chunk_meta=%s)",
            self.cfg.redacted(),
            self.save_chunk_meta,
        )

    async def _run_blocking(self, func: Any, *args: Any) -> Any:
        return await self.loop.run_in_executor(self.executor, func, *args)

    def _encode(self, memory_obj: MemoryObj) -> bytes:
        payload = _byte_view(memory_obj)
        if not self.save_chunk_meta:
            return bytes(payload)
        header = RemoteMetadata(
            len(payload),
            memory_obj.get_shapes(),
            memory_obj.get_dtypes(),
            memory_obj.get_memory_format(),
        ).serialize()
        return header + bytes(payload)

    def _decode(self, key: CacheEngineKey, document: bytes) -> MemoryObj | None:
        if self.save_chunk_meta:
            header_size = self.remote_metadata_bytes
            if len(document) < header_size:
                raise ValueError(
                    f"Couchbase document for {key} has {len(document)} bytes, "
                    f"shorter than the {header_size}-byte LMCache metadata header"
                )
            metadata = RemoteMetadata.deserialize(document[:header_size])
            payload = memoryview(document)[header_size:]
            if len(payload) != metadata.length:
                raise ValueError(
                    f"Couchbase document for {key} has {len(payload)} payload "
                    f"bytes but its metadata header says {metadata.length}"
                )
            memory_obj = self.local_cpu_backend.allocate(
                metadata.shapes, metadata.dtypes, metadata.fmt
            )
        else:
            payload = memoryview(document)
            memory_obj = self.local_cpu_backend.allocate(
                self.meta_shapes, self.meta_dtypes, self.meta_fmt
            )
        if memory_obj is None:
            logger.warning("LMCache local CPU backend could not allocate MemoryObj")
            return None
        try:
            target = _byte_view(memory_obj)
            if len(payload) > len(target):
                raise ValueError(
                    f"Couchbase payload for {key} has {len(payload)} bytes but "
                    f"allocated LMCache buffer has {len(target)} bytes"
                )
            target[: len(payload)] = payload
            if self.save_chunk_meta:
                return memory_obj
            return self.reshape_partial_chunk(memory_obj, len(payload))
        except Exception:
            _release(memory_obj)
            raise

    async def exists(self, key: CacheEngineKey) -> bool:
        """Return whether Couchbase contains the LMCache key."""

        return bool(await self._run_blocking(self.store.exists, key))

    def exists_sync(self, key: CacheEngineKey) -> bool:
        """Synchronous existence check used by LMCache's optional fast path."""

        return self.store.exists(key)

    async def get(self, key: CacheEngineKey) -> MemoryObj | None:
        """Fetch a chunk from Couchbase into an LMCache ``MemoryObj``."""

        document = await self._run_blocking(self.store.get_bytes, key)
        if document is None:
            return None
        return self._decode(key, document)

    async def put(self, key: CacheEngineKey, memory_obj: MemoryObj) -> None:
        """Persist a chunk in Couchbase."""

        await self._run_blocking(self.store.put_bytes, key, self._encode(memory_obj))

    def remove_sync(self, key: CacheEngineKey) -> bool:
        """Remove a chunk; used by LMCache ``RemoteBackend.remove``."""

        return self.store.remove(key)

    async def list(self) -> builtins.list[str]:
        """List is intentionally unsupported for the remote connector contract."""

        return []

    def support_ping(self) -> bool:
        """Couchbase connectivity can be health-checked."""

        return True

    async def ping(self) -> int:
        """Return 0 when the Couchbase KV service answers, 1 otherwise."""

        return 0 if await self._run_blocking(self.store.ping) else 1

    async def close(self) -> None:
        """Close Couchbase and executor resources."""

        await self._run_blocking(self.store.close)
        self.executor.shutdown(wait=True, cancel_futures=False)

    def support_batched_put(self) -> bool:
        """Couchbase writes are batched through concurrent executor jobs."""

        return True

    async def batched_put(
        self, keys: builtins.list[CacheEngineKey], memory_objs: builtins.list[MemoryObj]
    ) -> None:
        """Persist multiple chunks concurrently."""

        documents = [self._encode(memory_obj) for memory_obj in memory_objs]
        await asyncio.gather(
            *(
                self._run_blocking(self.store.put_bytes, key, document)
                for key, document in zip(keys, documents, strict=True)
            )
        )

    def support_batched_get(self) -> bool:
        """Couchbase reads are batched through concurrent executor jobs."""

        return True

    async def batched_get(
        self, keys: builtins.list[CacheEngineKey]
    ) -> builtins.list[MemoryObj | None]:
        """Fetch multiple chunks concurrently."""

        return list(await asyncio.gather(*(self.get(key) for key in keys)))

    def support_batched_contains(self) -> bool:
        """Enable LMCache prefix-hit counting over multiple keys."""

        return True

    def batched_contains(self, keys: builtins.list[CacheEngineKey]) -> int:
        """Return the number of consecutive existing keys from the start."""

        count = 0
        for key in keys:
            if not self.store.exists(key):
                return count
            count += 1
        return count

    def support_batched_async_contains(self) -> bool:
        """Enable async prefix-hit counting."""

        return True

    async def batched_async_contains(
        self,
        lookup_id: str,
        keys: builtins.list[CacheEngineKey],
        pin: bool = False,
    ) -> int:
        """Return the async number of consecutive existing keys from the start."""

        del lookup_id, pin
        results = await asyncio.gather(
            *(self._run_blocking(self.store.exists, key) for key in keys)
        )
        count = 0
        for exists in results:
            if not exists:
                return count
            count += 1
        return count

    def support_batched_get_non_blocking(self) -> bool:
        """Enable LMCache prefetch reads."""

        return True

    async def batched_get_non_blocking(
        self,
        lookup_id: str,
        keys: builtins.list[CacheEngineKey],
    ) -> builtins.list[MemoryObj]:
        """Fetch the consecutive prefix of chunks for prefetch paths.

        LMCache maps the returned objects positionally onto ``keys``, so results
        stop at the first miss or error and any later objects are released.
        """

        del lookup_id
        results = await asyncio.gather(
            *(self.get(key) for key in keys), return_exceptions=True
        )
        prefix: builtins.list[MemoryObj] = []
        broken = False
        for result in results:
            if result is None or isinstance(result, BaseException):
                if isinstance(result, BaseException):
                    logger.warning("Couchbase prefetch failed: %s", result)
                broken = True
            elif broken:
                _release(result)
            else:
                prefix.append(result)
        return prefix
