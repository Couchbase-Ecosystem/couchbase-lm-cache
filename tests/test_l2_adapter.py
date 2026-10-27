# SPDX-License-Identifier: Apache-2.0
"""Exercise the LMCache MP-mode Couchbase L2 adapter.

The adapter is created through LMCache's own plugin registry, exactly as
``lmcache server --l2-adapter '{"type": "plugin", ...}'`` does. Each test runs
against an in-memory store and, when ``LMCACHE_COUCHBASE_LIVE_TESTS=1``, against
a real Couchbase cluster.
"""

import contextlib
import json
import os
import select
import uuid

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("lmcache.v1.distributed.l2_adapters.plugin_l2_adapter")

from lmcache.v1.distributed.api import MemoryLayoutDesc, ObjectKey  # noqa: E402
from lmcache.v1.distributed.l2_adapters.config import (  # noqa: E402
    add_l2_adapters_args,
    parse_args_to_l2_adapters_config,
)
from lmcache.v1.distributed.l2_adapters.factory import (  # noqa: E402
    create_l2_adapter_from_registry,
)
from lmcache.v1.memory_management import (  # noqa: E402
    MemoryObjMetadata,
    TensorMemoryObj,
)
from lmcache.v1.platform import consume_fd  # noqa: E402

from couchbase_lm_cache.l2_adapter import (  # noqa: E402
    CouchbaseL2Adapter,
    object_key_to_document_key,
)

_NO_LAYOUT = MemoryLayoutDesc(shapes=[], dtypes=[])


class _MemoryStore:
    """In-memory stand-in for ``CouchbaseKVStore``."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.docs = {}
        self.closed = False

    def build_key(self, key):
        return self.cfg.key_prefix + str(key)

    def put_bytes(self, key, payload):
        self.docs[self.build_key(key)] = bytes(memoryview(payload).cast("B"))

    def get_bytes(self, key):
        return self.docs.get(self.build_key(key))

    def exists(self, key):
        return self.build_key(key) in self.docs

    def remove_measured(self, key):
        payload = self.docs.pop(self.build_key(key), None)
        return None if payload is None else len(payload)

    def ping(self):
        return True

    def close(self):
        self.closed = True


def _live_enabled():
    return os.environ.get("LMCACHE_COUCHBASE_LIVE_TESTS") == "1"


def _adapter_spec(**params):
    adapter_params = {"key_prefix": f"pytest-l2-{uuid.uuid4().hex[:8]}:", **params}
    if not _live_enabled():
        adapter_params.update(
            connection_string="couchbase://unused",
            username="u",
            password="p",
            bucket_name="b",
        )
    return {
        "type": "plugin",
        "module_path": "couchbase_lm_cache.l2_adapter",
        "class_name": "CouchbaseL2Adapter",
        "adapter_params": adapter_params,
    }


@pytest.fixture(params=["memory", pytest.param("couchbase", marks=pytest.mark.live)])
def store_kind(request, monkeypatch):
    if request.param == "memory":
        monkeypatch.setattr(
            "couchbase_lm_cache.l2_adapter.CouchbaseKVStore", _MemoryStore
        )
    elif not _live_enabled():
        pytest.skip("set LMCACHE_COUCHBASE_LIVE_TESTS=1 to run live Couchbase test")
    return request.param


@pytest.fixture
def make_adapter(store_kind):
    adapters = []

    def factory(**params):
        import argparse

        parser = argparse.ArgumentParser()
        add_l2_adapters_args(parser)
        args = parser.parse_args(["--l2-adapter", json.dumps(_adapter_spec(**params))])
        (config,) = parse_args_to_l2_adapters_config(args).adapters
        adapter = create_l2_adapter_from_registry(config)
        adapters.append(adapter)
        return adapter

    yield factory
    for adapter in adapters:
        adapter.close()


def _key(tag, model="Qwen/Qwen3-0.6B", salt=""):
    return ObjectKey(
        chunk_hash=tag.to_bytes(8, "big"),
        model_name=model,
        kv_rank=0,
        cache_salt=salt,
    )


def _tensor_obj(tensor):
    meta = MemoryObjMetadata(
        shape=tensor.shape,
        dtype=tensor.dtype,
        address=tensor.data_ptr(),
        phy_size=tensor.nelement() * tensor.element_size(),
        ref_count=1,
    )
    return TensorMemoryObj(raw_data=tensor, metadata=meta, parent_allocator=None)


def _chunk(seed, numel=4096):
    generator = torch.Generator().manual_seed(seed)
    return _tensor_obj(torch.randn(numel, generator=generator).to(torch.bfloat16))


def _empty_like(memory_obj):
    return _tensor_obj(torch.zeros_like(memory_obj.raw_data))


def _wait(fd, timeout=30.0):
    poll = select.poll()
    poll.register(fd, select.POLLIN)
    assert poll.poll(timeout * 1000), "adapter did not signal completion"
    with contextlib.suppress(BlockingIOError):
        consume_fd(fd)


def _store(adapter, keys, objects):
    task_id = adapter.submit_store_task(keys, objects)
    results = {}
    while task_id not in results:
        _wait(adapter.get_store_event_fd())
        results.update(adapter.pop_completed_store_tasks())
    return results[task_id]


def _lookup(adapter, keys):
    task_id = adapter.submit_lookup_and_lock_task(keys, {0: _NO_LAYOUT})
    while (bitmap := adapter.query_lookup_and_lock_result(task_id)) is None:
        _wait(adapter.get_lookup_and_lock_event_fd())
    adapter.submit_unlock(keys)
    return [bool(bitmap.test(i)) for i in range(len(keys))]


def _load(adapter, keys, buffers):
    task_id = adapter.submit_load_task(keys, buffers)
    while (bitmap := adapter.query_load_result(task_id)) is None:
        _wait(adapter.get_load_event_fd())
    return [bool(bitmap.test(i)) for i in range(len(keys))]


def test_document_key_matches_lmcache_adapter_convention():
    assert (
        object_key_to_document_key(_key(255))
        == "Qwen/Qwen3-0.6B@0x00000000@0@00000000000000ff"
    )
    assert object_key_to_document_key(_key(1, salt="tenant-a")).endswith("@tenant-a")


def test_registry_creates_couchbase_adapter(make_adapter):
    adapter = make_adapter()

    assert isinstance(adapter, CouchbaseL2Adapter)
    fds = {
        adapter.get_store_event_fd(),
        adapter.get_lookup_and_lock_event_fd(),
        adapter.get_load_event_fd(),
    }
    assert len(fds) == 3
    assert adapter.report_status()["is_healthy"]


def test_store_lookup_and_load_roundtrip(make_adapter):
    adapter = make_adapter()
    keys = [_key(i) for i in range(4)]
    chunks = [_chunk(seed=i) for i in range(4)]

    result = _store(adapter, keys, chunks)

    assert result.is_successful()
    assert result.bytes_transferred() == sum(c.get_size() for c in chunks)
    missing = _key(999)
    assert _lookup(adapter, keys + [missing]) == [True] * 4 + [False]
    buffers = [_empty_like(c) for c in chunks] + [_empty_like(chunks[0])]
    assert _load(adapter, keys + [missing], buffers) == [True] * 4 + [False]
    for buffer, chunk in zip(buffers, chunks, strict=False):
        assert torch.equal(buffer.raw_data, chunk.raw_data)
    adapter.delete(keys)
    assert _lookup(adapter, keys) == [False] * 4


def test_store_skips_existing_objects(make_adapter):
    adapter = make_adapter()
    key, chunk = _key(7), _chunk(seed=7)

    assert _store(adapter, [key], [chunk]).bytes_transferred() == chunk.get_size()
    second = _store(adapter, [key], [chunk])

    assert second.is_successful()
    assert second.bytes_transferred() == 0
    adapter.delete([key])


def test_load_rejects_size_mismatch(make_adapter):
    adapter = make_adapter()
    key, chunk = _key(8), _chunk(seed=8, numel=4096)
    _store(adapter, [key], [chunk])

    wrong_size = _tensor_obj(torch.zeros(2048, dtype=torch.bfloat16))

    assert _load(adapter, [key], [wrong_size]) == [False]
    adapter.delete([key])


def test_large_object_is_sharded_and_restored(make_adapter, store_kind):
    # 1 MiB shards force a 3 MiB object into several Couchbase documents.
    adapter = make_adapter(shard_size_bytes=1024 * 1024)
    key, chunk = _key(9), _chunk(seed=9, numel=3 * 512 * 1024)

    assert _store(adapter, [key], [chunk]).is_successful()
    buffer = _empty_like(chunk)

    assert _load(adapter, [key], [buffer]) == [True]
    assert torch.equal(buffer.raw_data, chunk.raw_data)
    if store_kind == "couchbase":
        doc_key = object_key_to_document_key(key)
        assert adapter.store.exists(adapter.store.shard_key(doc_key, 2))
    adapter.delete([key])


def test_two_adapters_share_objects(make_adapter):
    """An object stored by one LMCache server is loadable by another."""

    writer = make_adapter()
    reader = make_adapter(key_prefix=writer.cfg.key_prefix)
    if isinstance(writer.store, _MemoryStore):
        reader.store.docs = writer.store.docs
    key, chunk = _key(10), _chunk(seed=10)

    _store(writer, [key], [chunk])
    buffer = _empty_like(chunk)

    assert _lookup(reader, [key]) == [True]
    assert _load(reader, [key], [buffer]) == [True]
    assert torch.equal(buffer.raw_data, chunk.raw_data)
    writer.delete([key])
