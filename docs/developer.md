# Developer Guide

## Repository strategy

This repository is a Couchbase-owned standalone package/example. LMCache already
supports plug-and-play remote storage connectors through `remote_storage_plugins`,
so this integration does not need to patch LMCache upstream for evaluation or use.
An upstream contribution could later add Couchbase to LMCache's built-in connector
catalog, but this package is usable independently.

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

## Publish/release path

1. Update `version` in `pyproject.toml`.
2. Run `pytest`, optional `pytest -m live`, `ruff check .`, and `python -m build`.
3. Tag the release in GitHub.
4. Publish the wheel/sdist from `dist/` to the chosen package index with the
   organization's normal credentials, for example `twine upload dist/*` if PyPI
   publication is approved.
5. If maintainers want this listed inside LMCache, open an upstream PR adding a
   built-in Couchbase adapter or a docs page that points to this package.

## Design limitations

Couchbase is best treated as a durable/warm remote tier. It is not a replacement
for LMCache's lowest-latency CPU/GPU/RDMA tiers. Couchbase Server's KV document
size limit means LMCache chunk sizes must keep serialized payloads under the
server limit or a future sharding enhancement is required.
