# Developer Guide

## Repository strategy

This repository is a Couchbase-owned standalone package/example. LMCache already
supports plug-and-play storage plugins, so this integration does not need to
patch LMCache upstream for evaluation or use. An upstream contribution could
later add Couchbase to LMCache's built-in catalog, but this package is usable
independently.

The package plugs into both LMCache architectures:

| Module | LMCache architecture | Plugin point |
| --- | --- | --- |
| `couchbase_lm_cache.l2_adapter.CouchbaseL2Adapter` | Multiprocess (MP) mode: `lmcache server` + vLLM `LMCacheMPConnector` | `--l2-adapter '{"type": "plugin", ...}'` |
| `couchbase_lm_cache.connector.CouchbaseConnector` | In-process: vLLM `LMCacheConnectorV1` | `remote_storage_plugins` + `extra_config` |

Both share `CouchbaseKVStore` (KV access, sharding, TTL, ping) and
`CouchbaseLMCacheConfig` (settings with `LMCACHE_COUCHBASE_*` env fallback).

MP mode is the recommended path. With vLLM >= 0.26 (fused/packed KV layout),
LMCache 0.5.6's in-process `LMCacheConnectorV1` loads KV non-deterministically on
every backend, including LMCache's own CPU tier, so outputs served from cache can
differ from recomputation (LMCache issue #4463, fix in PR #4467, not yet
released). MP mode is not affected. We confirmed this with log-probability probes
on this stack: in-process loads differed from load to load; MP-mode loads were
identical every time and matched the cold run like vLLM's own prefix cache.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
pytest
ruff check .
python -m build
```

To test with LMCache, install LMCache in the same environment following LMCache's
own instructions. LMCache source builds generally need Python 3.12 and either
`NO_NATIVE_EXT=1` or the appropriate CUDA/HIP/native toolchain.

## Couchbase development setup

For local testing, run Couchbase Server with Docker and create a bucket named
`lmcache`, or use Capella. The connector uses KV operations on the configured
bucket/scope/collection and does not require a SQL++ primary index for normal
LMCache reads/writes.

Example environment:

```bash
export LMCACHE_COUCHBASE_CONNSTR=couchbase://127.0.0.1
export LMCACHE_COUCHBASE_USERNAME=Administrator
export LMCACHE_COUCHBASE_PASSWORD=password
export LMCACHE_COUCHBASE_BUCKET=lmcache
export LMCACHE_COUCHBASE_SCOPE=_default
export LMCACHE_COUCHBASE_COLLECTION=_default
export LMCACHE_COUCHBASE_LIVE_TESTS=1
pytest -m live
python examples/store_smoke.py
```

## Internal API/config reference

`CouchbaseL2Adapter` is created by LMCache's L2 adapter registry from a `plugin`
spec. `adapter_params` take the same field names as the table in the README; any
field left out is read from `LMCACHE_COUCHBASE_*`:

```bash
lmcache server --l1-size-gb 8 --eviction-policy LRU --l2-adapter \
  '{"type": "plugin", "module_path": "couchbase_lm_cache.l2_adapter",
    "class_name": "CouchbaseL2Adapter", "adapter_params": {"ttl_seconds": 86400}}'
```

The adapter implements `L2AdapterInterface`: store, lookup-and-lock and load
tasks run on a private event loop with blocking SDK calls on a thread pool, and
completions are signalled through LMCache event fds. Couchbase has no item locks,
so `submit_unlock` is a no-op and a document that expires between lookup and load
becomes a load miss. Existing objects are not rewritten on store.

`CouchbaseConnector` is loaded by LMCache's `ConnectorManager` as a
`RemoteConnector` class:

```yaml
remote_storage_plugins:
  - couchbase
extra_config:
  remote_storage_plugin.couchbase.module_path: couchbase_lm_cache.connector
  remote_storage_plugin.couchbase.class_name: CouchbaseConnector
  remote_storage_plugin.couchbase.connection_string: couchbase://host
  remote_storage_plugin.couchbase.username: Administrator
  remote_storage_plugin.couchbase.password: password
  remote_storage_plugin.couchbase.bucket_name: lmcache
```

Configuration can also be supplied through `LMCACHE_COUCHBASE_*` environment
variables. The password is never logged by the helper's `redacted()` method.

## Required Couchbase resources

- Bucket: configurable, default examples use `lmcache`.
- Scope and collection: configurable, defaults to `_default._default`.
- Indexes: none for connector reads/writes; only KV APIs are used.
- Optional collection/bucket TTL can be configured in Couchbase. Connector-level
  `ttl_seconds` sets per-write document expiry when greater than zero.

## Release process

The version lives in `src/couchbase_lm_cache/__init__.py` (`__version__`);
`pyproject.toml` reads it from there.

1. Update `__version__` and add the release to `CHANGELOG.md`.
2. Check: `ruff check .`, `pytest`, and the live suite in the LMCache image
   (see the README's Development section).
3. Build and check the distributions:

   ```bash
   rm -rf dist && python -m build && twine check dist/*
   ```

   The sdist only contains the package, tests, docs and `examples/store_smoke.py`
   (see `[tool.hatch.build.targets.sdist]`); the demo, Docker stack and video
   stay in the repository.
4. Upload to PyPI with an API token for the `couchbase-lm-cache` project,
   configured in `~/.pypirc` or passed as `TWINE_USERNAME=__token__` /
   `TWINE_PASSWORD`:

   ```bash
   twine upload dist/*
   ```

5. Tag the commit and publish a GitHub release with the changelog entry:

   ```bash
   git tag -a v0.2.0 -m "couchbase-lm-cache 0.2.0" && git push origin v0.2.0
   gh release create v0.2.0 dist/* --title "couchbase-lm-cache 0.2.0" --notes-file <notes>
   ```

6. If LMCache maintainers want Couchbase listed in LMCache, open an upstream PR
   adding a docs page that points to this package.

## Storage format

MP mode (L2 adapter): each object is stored under
`<key_prefix><model>@0x<kv_rank>@<object_group_id>@<chunk_hash>[@<cache_salt>]`,
the same key layout as LMCache's built-in L2 adapters, and holds the raw chunk
bytes; LMCache passes load buffers of the right layout, so no header is needed.

In-process mode (connector): each LMCache chunk is stored under
`<key_prefix><CacheEngineKey.to_string()>`.

- With LMCache's `save_chunk_meta` (the LMCache default), the document is
  LMCache's serialized `RemoteMetadata` header followed by the chunk bytes. Reads
  allocate the exact stored shape, so partial chunks round-trip without
  guessing. Header and payload live in one document, so they are written and
  expired together.
- With `save_chunk_meta: false` in `extra_config`, the document is the raw chunk
  bytes and reads use LMCache's `reshape_partial_chunk`.
In both modes, payloads larger than `shard_size_bytes` (default 1 MiB, maximum
20 MiB) are written as binary `<key>::shard::<n>` documents first, then a JSON
manifest `{"lmcache_shards": n, "bytes": size}` at `<key>`. Document flags
(binary vs JSON) distinguish manifests from chunks. 1 MiB shards read about twice
as fast as 16 MiB ones on a single-node Couchbase 8.0.2 (about 1.1 vs 0.45-0.63
GiB/s for 26 chunks of 28 MiB with 32 threads).

## Tests

- `tests/test_config.py`, `tests/test_store.py`, `tests/test_connector.py`: unit
  tests with fakes; run anywhere.
- `tests/test_l2_adapter.py`: creates the MP-mode adapter through LMCache's own
  L2 adapter registry and runs store/lookup/load/delete, sharding and
  cross-server sharing. Needs LMCache; adds live variants when
  `LMCACHE_COUCHBASE_LIVE_TESTS=1`.
- `tests/test_lmcache_remote_backend.py`: loads the connector through LMCache's
  own `RemoteBackend`/`ConnectorManager` and round-trips real KV tensors. Needs
  LMCache installed; adds live Couchbase variants when
  `LMCACHE_COUCHBASE_LIVE_TESTS=1`.
- `tests/test_live_couchbase.py`: live Couchbase only, including a 25 MiB
  payload that exceeds the server's document limit.
- `examples/vllm_e2e_demo.py`: end-to-end check against the Docker stack in
  `docker/compose.yaml` (two LMCache servers + vLLM pairs sharing Couchbase,
  plus a restart).
- `examples/ttft_benchmark.py`: time-to-first-token before and after a restart,
  with the KV cache recomputed vs. loaded from Couchbase.

## Design limitations

Couchbase is best treated as a durable/warm remote tier. It is not a replacement
for LMCache's lowest-latency CPU/GPU/RDMA tiers. Sharded chunks need one KV
round trip per shard; a stale shard set left behind by overwriting a sharded
chunk with a smaller one expires with its TTL.
