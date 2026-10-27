# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-27

First release on PyPI.

### Added

- `CouchbaseL2Adapter`, an L2 adapter for LMCache's multiprocess (MP) mode
  (`lmcache server` with vLLM's `LMCacheMPConnector`), loaded through LMCache's
  `plugin` L2 adapter type. This is the recommended integration.
- Sharding of large chunks: payloads above `shard_size_bytes` (default 1 MiB)
  are stored as `<key>::shard::<n>` binary documents plus a JSON manifest, so
  chunks larger than Couchbase's 20 MiB document limit are supported and read in
  parallel.
- `shard_size_bytes` setting, `CouchbaseLMCacheConfig.from_dict()`,
  `CouchbaseKVStore.exists()`, `remove()`, `remove_measured()` and `ping()`.
- In-process connector: support for LMCache's `save_chunk_meta` (metadata header
  and payload in one document), `remove_sync()` and `ping()`.
- Docker Compose stack with Couchbase and two vLLM + LMCache server pairs, an
  end-to-end demo, a time-to-first-token benchmark and integration tests that
  run against real LMCache and Couchbase.
- `__version__` attribute.

### Changed

- Requires LMCache 0.5.6 or later (`lmcache` extra) and Couchbase Python SDK
  4.6.3 or later.
- Default KV timeout raised to 10 s and default concurrency to 32 operations, to
  suit multi-megabyte chunks.
- In-process prefetch returns only the consecutive prefix of found chunks and
  releases buffers on errors.

### Removed

- The `create_primary_index` setting, which had no effect: the connector only
  uses key-value operations.

### Known issues

- In-process mode (`LMCacheConnectorV1`) loads KV non-deterministically with
  vLLM 0.26 and later because of an upstream LMCache bug
  ([LMCache#4463](https://github.com/LMCache/LMCache/issues/4463)). MP mode is
  not affected.

## [0.1.0] - 2026-07-27

Initial version (not published): `CouchbaseConnector`, an LMCache remote storage
plugin for the in-process connector.

[0.2.0]: https://github.com/Couchbase-Ecosystem/couchbase-lm-cache/releases/tag/v0.2.0
[0.1.0]: https://github.com/Couchbase-Ecosystem/couchbase-lm-cache/commit/97d5d6f
