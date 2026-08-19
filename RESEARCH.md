# Repository Orientation

- Target repo: `Couchbase-Ecosystem/couchbase-lm-cache` (empty repo at intake; WRITE permission confirmed through GitHub API).
- Upstream evaluated: `LMCache/LMCache` dev branch, local clone inspected during this task.
- Integration type: LMCache remote storage connector plugin for serialized LLM KV-cache chunks.
- Existing integration patterns: LMCache has `RemoteBackend` plus `remote_storage_plugins`, `ConnectorAdapter`/`RemoteConnector` dynamic loading, and built-in Redis/RESP, S3, filesystem, Bigtable, Azure, HF3FS, InfiniStore, MooncakeStore, audit, blackhole, mock, and LM server connectors.
- Build/test commands for deliverable: Python package with `pytest`, `ruff check .`, `python -m build`, optional live Couchbase test.
- Docs/examples locations: `README.md`, `docs/developer.md`, `examples/`.
- Release/package locations: `pyproject.toml`, `src/couchbase_lm_cache`.
- Open related issues/PRs checked: LMCache issues #3403 Bigtable backend, #3749 GCS connector, #3342 Valkey cluster, #4113 SPDK backend, #3376 S3/minio, #3565 LMCache server reconnect; PRs #3854 GCS connector, #3923 GCS L2 adapter, #3955 Valkey batched exists, #4054 Azure connector, #3593 OBJ backend, #4193 S3 self-signed/path-style.
- Risks: Couchbase KV latency is higher than local CPU/RDMA tiers; Couchbase Server maximum document size means large KV chunks may require smaller LMCache chunks or future sharding; LMCache storage plugin APIs are moving quickly.

# Integration Research

## Target Integration Contract

LMCache has two relevant extension surfaces:

1. `storage_plugins`: dynamically loads classes implementing `StoragePluginInterface` from `config.extra_config["storage_plugin.<name>.module_path/class_name"]` and inserts them directly into `CreateStorageBackends`.
2. `remote_storage_plugins`: dynamically loads remote connector adapters/classes from `config.extra_config["remote_storage_plugin.<name>.module_path/class_name"]`; `CreateStorageBackends` wraps each plugin in `RemoteBackend`, which handles LMCache serialization/deserialization and delegates `exists`, `get`, `put`, batched calls, and close lifecycle to a `RemoteConnector`.

The closest and least invasive contract is `remote_storage_plugins`, because Couchbase is an external service like Redis/S3/Bigtable rather than a new local allocator.

## Competitor References

| Reference | Why relevant | Key API/config patterns | Test/docs patterns |
| --- | --- | --- | --- |
| LMCache Redis/RESP connectors | Network KV backend closest in API shape | `exists`, `get`, `put`, batched exists/get/put; stores `memory_obj.byte_array` by `key.to_string()` | Unit tests exercise `RemoteBackend` with async loop and `LocalCPUBackend` |
| LMCache S3 connector | Durable remote object tier | URI/config-driven, remote serializer, remote backend wrapper | Issues/PRs show endpoint/path-style/auth compatibility matters |
| LMCache filesystem connector | Plugin-style external path config | `remote_storage_plugins=["fs"]` and `extra_config.remote_storage_plugin.fs.*` | Tests cover plugin loading and dual plugin instances |
| LMCache Bigtable connector | External durable cloud KV-like backend | Plugin-specific config object, binary payload sharding, async executor | Tests cover Bigtable connector, integration gate, and benchmark path |
| LMCache Azure/GCS PRs | Cloud object backend guidance | Native connector classes loaded through remote plugin machinery | Open PRs highlight backend-specific auth and async behavior concerns |

## Existing Couchbase References

| Reference | What can be reused | Gaps |
| --- | --- | --- |
| Couchbase Python SDK KV API | Binary `upsert`, `get`, `exists`, `remove`, TTL/expiry, scopes/collections, TLS/Capella connection strings | No LMCache-specific connector exists upstream |
| Couchbase Server KV service | Durable key-value operations and collection/bucket TTL | 20 MB max document size is a hard limit; KV latency not comparable to in-process or RDMA tiers |

## Design Implications

- API shape: expose `couchbase_lm_cache.connector.CouchbaseConnector` as an LMCache `RemoteConnector` loaded by `remote_storage_plugins`.
- Required Couchbase features: KV service, binary documents, scopes/collections, per-document expiry/TTL, username/password auth, Capella TLS via connection string, SDK connection pooling.
- Main risks: item size limit, latency, blocking Python SDK calls in LMCache async paths, and no native LMCache upstream registry entry yet.
- Recommended implementation path: standalone Couchbase-owned package/example. Avoid upstream patch initially; document upstream PR path if maintainers want a built-in connector later.

# Couchbase Capability Matrix

| Required capability | Required by target integration | Couchbase support | Evidence | Implementation decision |
| --- | --- | --- | --- | --- |
| Connection/auth | Connector must connect from LMCache worker using safe credentials | Supported with connection string, username/password, TLS/Capella | Couchbase Python SDK `Cluster`, `PasswordAuthenticator`, connection strings | Implement env/extra_config-driven config |
| CRUD/KV | LMCache remote connector needs put/get/exists/remove-equivalent | Supported by KV collection operations | Couchbase KV APIs expose `upsert`, `get`, `exists`, `remove` | Implement binary store wrapper |
| Query/filtering | LMCache lookup does not require SQL++ queries | Not needed | LMCache `RemoteConnector` uses keys, not queries | Do not require indexes |
| Index management | None for KV connector | Not needed for KV | Couchbase KV by document key | Document no SQL++ primary index required |
| Search/vector search | Not required; KV cache chunks are not embeddings | Supported separately by Couchbase but irrelevant | LMCache stores serialized tensors, not vectors | Out of scope |
| TTL/expiry | Cache entries should expire optionally | Supported with document expiry / maxTTL | Couchbase docs and SDK support TTL/expiry | Implement `ttl_seconds` on upsert |
| Batching/concurrency | LMCache benefits from batched operations | SDK supports concurrent operations; async bulk helpers vary | LMCache connectors often run operations through executor/PQ | Implement batched methods with executor concurrency |
| Transactions/durability | Not required for individual cache chunks | Couchbase supports durability/transactions but overhead may hurt latency | Cache chunks can be overwritten idempotently | Do not require transactions; leave durability for future |
| Local test environment | Required for verification if possible | Docker/local Couchbase available in this environment in principle | `couchbase:latest` image available on host memory note | Provide live test gate and attempt local Docker verification |

# Feasibility Decision

Status: Implementable with limitations

Reason:
- LMCache already supports external remote storage plugins and has comparable remote connectors.
- Couchbase KV supports the needed byte payload put/get/exists/delete and TTL semantics for a warm remote cache tier.
- Couchbase is technically sensible as a durable L2/L3 tier, especially for reuse across restarts/nodes, but not as a replacement for LMCache's fastest CPU/GPU/RDMA tiers.

Evidence:
- `lmcache/v1/storage_backend/connector/__init__.py` dynamically imports `remote_storage_plugin.<name>.module_path/class_name` and accepts `RemoteConnector` subclasses.
- `lmcache/v1/storage_backend/remote_backend.py` delegates serialized `MemoryObj` payloads to `RemoteConnector.put/get/exists` and supports batched connector methods.
- Built-in connector/tests show Redis/RESP, filesystem, S3, Azure, Bigtable and other remote/object stores are expected integration patterns.
- Couchbase Server and Python SDK support KV binary documents, scopes/collections, document expiry, and username/password/TLS connections.

Implementation path:
- Standalone Couchbase-owned Python package in `Couchbase-Ecosystem/couchbase-lm-cache`.
- Provide an LMCache remote connector plugin, low-level Couchbase byte store, unit tests, live test gate, quickstart, developer docs, and tutorial/example.

Questions:
- None blocking. Future maintainer decision: whether to upstream a built-in LMCache adapter or keep this as a standalone package.
