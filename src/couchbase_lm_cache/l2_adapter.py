# SPDX-License-Identifier: Apache-2.0
"""Couchbase L2 adapter for LMCache multiprocess (MP) mode.

LMCache MP mode runs LMCache as a standalone ``lmcache server`` next to vLLM
(``LMCacheMPConnector``). Its persistent tier is made of L2 adapters, and this
module plugs Couchbase in as one::

    lmcache server --l1-size-gb 8 --eviction-policy LRU --l2-adapter \\
      '{"type": "plugin", "module_path": "couchbase_lm_cache.l2_adapter",
        "class_name": "CouchbaseL2Adapter", "adapter_params": {"ttl_seconds": 86400}}'

``adapter_params`` accepts the same fields as the in-process connector
(``connection_string``, ``username``, ``password``, ``bucket_name``, ...). Any
field that is not given is read from the ``LMCACHE_COUCHBASE_*`` environment
variables, which keeps credentials off the command line.

Each L2 object is one Couchbase document (sharded above ``shard_size_bytes``)
holding the raw chunk bytes; LMCache MP mode hands the adapter pre-allocated
buffers of the right layout, so no metadata header is stored.
"""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import torch  # noqa: F401  # must be imported before lmcache_native
from lmcache.lmcache_native import Bitmap
from lmcache.logging import init_logger
from lmcache.v1.distributed.api import MemoryLayoutDesc, ObjectKey
from lmcache.v1.distributed.internal_api import L2StoreResult
from lmcache.v1.distributed.l2_adapters.base import L2AdapterInterface, L2TaskId
from lmcache.v1.distributed.l2_adapters.config import L2AdapterConfigBase
from lmcache.v1.memory_management import MemoryObj
from lmcache.v1.platform import create_event_notifier

from couchbase_lm_cache.config import CouchbaseLMCacheConfig
from couchbase_lm_cache.connector import _byte_view
from couchbase_lm_cache.store import CouchbaseKVStore

logger = init_logger(__name__)


def object_key_to_document_key(key: ObjectKey) -> str:
    """Encode an ``ObjectKey`` like LMCache's built-in L2 adapters do.

    ``model@0x<kv_rank>@<object_group_id>@<chunk_hash>[@<cache_salt>]``. The
    ``@`` separator is safe: ``ObjectKey`` rejects it in model names and salts.
    """

    text = (
        f"{key.model_name}@{key.kv_rank:#010x}@{key.object_group_id:x}"
        f"@{key.chunk_hash.hex()}"
    )
    if key.cache_salt:
        text += f"@{key.cache_salt}"
    return text


class CouchbaseL2AdapterConfig(L2AdapterConfigBase):
    """``adapter_params`` for :class:`CouchbaseL2Adapter`."""

    def __init__(self, settings: CouchbaseLMCacheConfig) -> None:
        self.settings = settings

    @classmethod
    def from_dict(cls, d: dict) -> CouchbaseL2AdapterConfig:
        return cls(CouchbaseLMCacheConfig.from_dict(d))

    @classmethod
    def help(cls) -> str:
        return (
            "CouchbaseL2Adapter adapter_params (each falls back to the "
            "LMCACHE_COUCHBASE_* environment variable):\n"
            "- connection_string, username, password, bucket_name (required)\n"
            "- scope_name, collection_name (default _default)\n"
            "- key_prefix (default 'lmcache:'), ttl_seconds (default none)\n"
            "- shard_size_bytes (default 1 MiB), kv_timeout_seconds (default 10)\n"
            "- max_workers (default 32)\n"
        )


class CouchbaseL2Adapter(L2AdapterInterface):
    """LMCache MP-mode L2 adapter that persists KV chunks in Couchbase KV.

    Blocking Couchbase SDK calls run on a thread pool; task bookkeeping runs on
    a private event loop and completions are signalled through event fds, as
    required by ``L2AdapterInterface``.
    """

    def __init__(
        self,
        config: CouchbaseL2AdapterConfig | dict[str, Any],
        **_kwargs: object,
    ) -> None:
        super().__init__()
        if isinstance(config, dict):
            config = CouchbaseL2AdapterConfig.from_dict(config)
        self.cfg = config.settings
        self.store = CouchbaseKVStore(self.cfg)
        self._executor = ThreadPoolExecutor(
            max_workers=self.cfg.max_workers, thread_name_prefix="couchbase-l2"
        )

        self._store_efd = create_event_notifier()
        self._lookup_efd = create_event_notifier()
        self._load_efd = create_event_notifier()

        self._lock = threading.Lock()
        self._next_task_id: L2TaskId = 0
        self._completed_stores: dict[L2TaskId, L2StoreResult] = {}
        self._completed_lookups: dict[L2TaskId, Bitmap] = {}
        self._completed_loads: dict[L2TaskId, Bitmap] = {}

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop, name="couchbase-l2-loop", daemon=True
        )
        self._loop_thread.start()
        logger.info("Couchbase L2 adapter ready: %s", self.cfg.redacted())

    # ---- event fds -----------------------------------------------------

    def get_store_event_fd(self) -> int:
        return self._store_efd.fileno()

    def get_lookup_and_lock_event_fd(self) -> int:
        return self._lookup_efd.fileno()

    def get_load_event_fd(self) -> int:
        return self._load_efd.fileno()

    # ---- store ---------------------------------------------------------

    def submit_store_task(
        self, keys: list[ObjectKey], objects: list[MemoryObj]
    ) -> L2TaskId:
        task_id = self._new_task_id()
        self._submit(self._store(keys, objects, task_id))
        return task_id

    def pop_completed_store_tasks(self) -> dict[L2TaskId, L2StoreResult]:
        with self._lock:
            completed, self._completed_stores = self._completed_stores, {}
        return completed

    # ---- lookup and lock -----------------------------------------------

    def submit_lookup_and_lock_task(
        self,
        keys: list[ObjectKey],
        group_layout_descs: dict[int, MemoryLayoutDesc],
    ) -> L2TaskId:
        del group_layout_descs  # advisory hint; Couchbase stores raw bytes
        task_id = self._new_task_id()
        self._submit(self._lookup(keys, task_id))
        return task_id

    def query_lookup_and_lock_result(self, task_id: L2TaskId) -> Bitmap | None:
        with self._lock:
            return self._completed_lookups.pop(task_id, None)

    def submit_unlock(self, keys: list[ObjectKey]) -> None:
        # No-op: Couchbase documents are not locked. A document that expires
        # between lookup and load simply turns that load into a miss.
        del keys

    # ---- load ----------------------------------------------------------

    def submit_load_task(
        self, keys: list[ObjectKey], objects: list[MemoryObj]
    ) -> L2TaskId:
        task_id = self._new_task_id()
        self._submit(self._load(keys, objects, task_id))
        return task_id

    def query_load_result(self, task_id: L2TaskId) -> Bitmap | None:
        with self._lock:
            return self._completed_loads.pop(task_id, None)

    # ---- eviction, status, close -----------------------------------------

    def delete(self, keys: list[ObjectKey]) -> None:
        if not keys:
            return
        sizes = asyncio.run_coroutine_threadsafe(
            self._map(self._remove_one, keys), self._loop
        ).result(timeout=60)
        deleted = [(k, size) for k, size in zip(keys, sizes, strict=True) if size]
        if deleted:
            self._notify_keys_deleted([k for k, _ in deleted], [s for _, s in deleted])

    def report_status(self) -> dict:
        healthy = self._loop_thread.is_alive() and self.store.ping()
        return {
            "is_healthy": healthy,
            "type": "CouchbaseL2Adapter",
            "bucket": self.cfg.bucket_name,
            "scope": self.cfg.scope_name,
            "collection": self.cfg.collection_name,
            "key_prefix": self.cfg.key_prefix,
            "event_loop_alive": self._loop_thread.is_alive(),
        }

    def close(self) -> None:
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=10)
        self._executor.shutdown(wait=True, cancel_futures=True)
        self.store.close()
        self._store_efd.close()
        self._lookup_efd.close()
        self._load_efd.close()
        logger.info("Couchbase L2 adapter closed")

    # ---- task bodies ---------------------------------------------------

    async def _store(
        self, keys: list[ObjectKey], objects: list[MemoryObj], task_id: L2TaskId
    ) -> None:
        started = time.perf_counter()
        sizes = await self._map(self._store_one, list(zip(keys, objects, strict=True)))
        stored = [(key, size) for key, size in zip(keys, sizes, strict=True) if size]
        if stored:
            self._notify_keys_stored([k for k, _ in stored], [s for _, s in stored])
            logger.info(
                "Couchbase L2 stored %d chunks (%.1f MB) in %.0f ms",
                len(stored),
                sum(size for _, size in stored) / 1e6,
                (time.perf_counter() - started) * 1000,
            )
        ok = all(size is not None for size in sizes)
        with self._lock:
            self._completed_stores[task_id] = L2StoreResult(
                ok, sum(size or 0 for size in sizes)
            )
        self._store_efd.notify()

    async def _lookup(self, keys: list[ObjectKey], task_id: L2TaskId) -> None:
        found = await self._map(self._exists_one, keys)
        bitmap = Bitmap(len(keys))
        for index, exists in enumerate(found):
            if exists:
                bitmap.set(index)
        logger.info("Couchbase L2 lookup: %d of %d chunks found", sum(found), len(keys))
        with self._lock:
            self._completed_lookups[task_id] = bitmap
        self._lookup_efd.notify()

    async def _load(
        self, keys: list[ObjectKey], objects: list[MemoryObj], task_id: L2TaskId
    ) -> None:
        started = time.perf_counter()
        loaded = await self._map(self._load_one, list(zip(keys, objects, strict=True)))
        bitmap = Bitmap(len(keys))
        for index, ok in enumerate(loaded):
            if ok:
                bitmap.set(index)
        hits = [key for key, ok in zip(keys, loaded, strict=True) if ok]
        if hits:
            self._notify_keys_accessed(hits)
            logger.info(
                "Couchbase L2 loaded %d chunks (%.1f MB) in %.0f ms",
                len(hits),
                sum(o.get_size() for o, ok in zip(objects, loaded, strict=True) if ok)
                / 1e6,
                (time.perf_counter() - started) * 1000,
            )
        with self._lock:
            self._completed_loads[task_id] = bitmap
        self._load_efd.notify()

    # ---- per-key blocking work (runs on the executor) --------------------

    def _store_one(self, item: tuple[ObjectKey, MemoryObj]) -> int | None:
        """Return bytes written, 0 if already present, ``None`` on failure."""

        key, memory_obj = item
        doc_key = object_key_to_document_key(key)
        try:
            if self.store.exists(doc_key):
                return 0
            payload = _byte_view(memory_obj)
            self.store.put_bytes(doc_key, payload)
            return len(payload)
        except Exception:
            logger.exception("Couchbase L2 store failed for %s", doc_key)
            return None

    def _exists_one(self, key: ObjectKey) -> bool:
        doc_key = object_key_to_document_key(key)
        try:
            return self.store.exists(doc_key)
        except Exception:
            logger.exception("Couchbase L2 lookup failed for %s", doc_key)
            return False

    def _load_one(self, item: tuple[ObjectKey, MemoryObj]) -> bool:
        key, memory_obj = item
        doc_key = object_key_to_document_key(key)
        try:
            data = self.store.get_bytes(doc_key)
            if data is None:
                return False
            target = _byte_view(memory_obj)
            if len(data) != len(target):
                logger.warning(
                    "Couchbase L2 object %s has %d bytes, expected %d",
                    doc_key,
                    len(data),
                    len(target),
                )
                return False
            target[:] = data
            return True
        except Exception:
            logger.exception("Couchbase L2 load failed for %s", doc_key)
            return False

    def _remove_one(self, key: ObjectKey) -> int | None:
        doc_key = object_key_to_document_key(key)
        try:
            return self.store.remove_measured(doc_key)
        except Exception:
            logger.exception("Couchbase L2 delete failed for %s", doc_key)
            return None

    # ---- helpers -------------------------------------------------------

    async def _map(self, func: Any, items: list) -> list:
        return list(
            await asyncio.gather(
                *(self._loop.run_in_executor(self._executor, func, i) for i in items)
            )
        )

    def _submit(self, coro: Any) -> None:
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _new_task_id(self) -> L2TaskId:
        with self._lock:
            task_id = self._next_task_id
            self._next_task_id += 1
        return task_id

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
