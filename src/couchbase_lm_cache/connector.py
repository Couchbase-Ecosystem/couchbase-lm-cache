# SPDX-License-Identifier: Apache-2.0
"""LMCache RemoteConnector implementation backed by Couchbase KV."""

from __future__ import annotations

import asyncio
import builtins
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from couchbase_lm_cache.config import CouchbaseLMCacheConfig
from couchbase_lm_cache.store import CouchbaseKVStore

try:  # pragma: no cover - exercised when installed alongside LMCache
    from lmcache.utils import CacheEngineKey
    from lmcache.v1.memory_management import MemoryObj
    from lmcache.v1.storage_backend.connector.base_connector import RemoteConnector

    _HAS_LMCACHE = True
except Exception:  # pragma: no cover - unit tests run without heavy LMCache deps
    CacheEngineKey = Any  # type: ignore[misc,assignment]
    MemoryObj = Any  # type: ignore[misc,assignment]

    class RemoteConnector:  # type: ignore[no-redef]
        """Fallback base so unit tests can run without LMCache installed."""

        def reshape_partial_chunk(self, memory_obj: Any, bytes_read: int) -> Any:
            del bytes_read
            return memory_obj

    _HAS_LMCACHE = False


class CouchbaseConnector(RemoteConnector):
    """LMCache remote storage connector that stores chunks in Couchbase KV.

    This class is loaded by LMCache with ``remote_storage_plugins`` and implements
    the ``RemoteConnector`` methods expected by ``RemoteBackend``.
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
        self.executor = ThreadPoolExecutor(max_workers=self.cfg.max_workers)

    async def _run_blocking(self, func: Any, *args: Any) -> Any:
        return await self.loop.run_in_executor(self.executor, func, *args)

    async def exists(self, key: CacheEngineKey) -> bool:
        """Return whether Couchbase contains the LMCache key."""

        return bool(await self._run_blocking(self.store.exists, key))

    def exists_sync(self, key: CacheEngineKey) -> bool:
        """Synchronous existence check used by LMCache's optional fast path."""

        return self.store.exists(key)

    async def get(self, key: CacheEngineKey) -> MemoryObj | None:
        """Fetch a chunk from Couchbase into an LMCache ``MemoryObj``."""

        payload = await self._run_blocking(self.store.get_bytes, key)
        if payload is None:
            return None
        memory_obj = self.local_cpu_backend.allocate(
            self.meta_shapes,
            self.meta_dtypes,
            self.meta_fmt,
        )
        if memory_obj is None:
            raise RuntimeError("LMCache local CPU backend could not allocate MemoryObj")
        target = memory_obj.byte_array
        target_view = target if isinstance(target, memoryview) else memoryview(target)
        if len(payload) > len(target_view):
            raise ValueError(
                f"Couchbase payload for {key} has {len(payload)} bytes but "
                f"allocated LMCache buffer has {len(target_view)} bytes"
            )
        target_view[: len(payload)] = payload
        return self.reshape_partial_chunk(memory_obj, len(payload))

    async def put(self, key: CacheEngineKey, memory_obj: MemoryObj) -> None:
        """Persist a chunk in Couchbase."""

        payload = memory_obj.byte_array
        payload_view = (
            payload if isinstance(payload, memoryview) else memoryview(payload)
        )
        await self._run_blocking(self.store.put_bytes, key, bytes(payload_view))

    async def list(self) -> builtins.list[str]:
        """List is intentionally unsupported for the remote connector contract."""

        return []

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

        payloads = []
        for memory_obj in memory_objs:
            payload = memory_obj.byte_array
            payload_view = (
                payload if isinstance(payload, memoryview) else memoryview(payload)
            )
            payloads.append(bytes(payload_view))
        await asyncio.gather(
            *(
                self._run_blocking(self.store.put_bytes, key, payload)
                for key, payload in zip(keys, payloads, strict=True)
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
        """Fetch multiple chunks for prefetch paths."""

        del lookup_id
        results = await self.batched_get(keys)
        return [result for result in results if result is not None]
