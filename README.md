# Couchbase LMCache Connector

Couchbase LMCache Connector is a standalone Couchbase-owned Python package that
adds a Couchbase KV remote storage connector for [LMCache](https://github.com/LMCache/LMCache).
It stores serialized LMCache KV-cache chunks as binary Couchbase KV documents.

## Feasibility summary

Status: **Implementable with limitations**.

LMCache has a real plugin point for this integration: `remote_storage_plugins`
loads a `RemoteConnector` class from `extra_config` and wraps it in LMCache's
`RemoteBackend`. Existing LMCache connectors include Redis/RESP, S3, filesystem,
Azure, Bigtable, HF3FS, InfiniStore, and MooncakeStore. Couchbase's KV service
supports the required put/get/exists/delete and TTL behavior for a remote cache
persistence tier.

The main limitation is fit: Couchbase is appropriate as a durable warm L2/L3 tier
for reuse across restarts or nodes, not as a lowest-latency GPU/CPU cache tier.
LMCache chunk sizes must stay below Couchbase Server's maximum document size.

## Example use cases

You can use this connector to:

- Persist reusable LMCache prefix chunks across inference-worker restarts.
- Share a warm KV-cache tier between a small group of LMCache-enabled serving
  processes when Couchbase latency is acceptable.
- Evaluate Couchbase durability, TTL, scopes/collections, and Capella operations
  as an LLM KV-cache persistence backend.

It does **not** replace LMCache's local CPU/GPU, NIXL, Mooncake, or other
ultra-low-latency tiers. It also does not create embeddings or perform vector
search; it stores raw serialized KV-cache chunks.

## End-user quickstart

### 1. Provision Couchbase

Use Couchbase Capella when LMCache workers need to reach Couchbase over the
public internet or from managed infrastructure. Use local/self-managed Couchbase
for development or same-network deployments.

Create:

- a bucket, for example `lmcache`
- a scope and collection, or use `_default._default`
- a database user with data reader/writer access to that bucket

No SQL++ index is required for normal connector operation because the connector
uses KV APIs only.

### 2. Install

Install the connector in the same Python environment as LMCache and vLLM:

```bash
pip install couchbase-lm-cache
```

For source checkout testing:

```bash
git clone https://github.com/Couchbase-Ecosystem/couchbase-lm-cache.git
cd couchbase-lm-cache
pip install -e .
```

### 3. Configure credentials safely

```bash
export LMCACHE_COUCHBASE_CONNSTR=couchbase://127.0.0.1
export LMCACHE_COUCHBASE_USERNAME=Administrator
export LMCACHE_COUCHBASE_PASSWORD='password'
export LMCACHE_COUCHBASE_BUCKET=lmcache
export LMCACHE_COUCHBASE_SCOPE=_default
export LMCACHE_COUCHBASE_COLLECTION=_default
```

For Capella, use a `couchbases://...` connection string and credentials from a
Capella database access user.

### 4. Add the LMCache config snippet

Create `lmcache-couchbase.yaml`:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 5
remote_serde: naive
remote_storage_plugins:
  - couchbase
extra_config:
  remote_storage_plugin.couchbase.module_path: couchbase_lm_cache.connector
  remote_storage_plugin.couchbase.class_name: CouchbaseConnector
  remote_storage_plugin.couchbase.connection_string: ${LMCACHE_COUCHBASE_CONNSTR}
  remote_storage_plugin.couchbase.username: ${LMCACHE_COUCHBASE_USERNAME}
  remote_storage_plugin.couchbase.password: ${LMCACHE_COUCHBASE_PASSWORD}
  remote_storage_plugin.couchbase.bucket_name: ${LMCACHE_COUCHBASE_BUCKET}
  remote_storage_plugin.couchbase.scope_name: ${LMCACHE_COUCHBASE_SCOPE:-_default}
  remote_storage_plugin.couchbase.collection_name: ${LMCACHE_COUCHBASE_COLLECTION:-_default}
  remote_storage_plugin.couchbase.key_prefix: ${LMCACHE_COUCHBASE_KEY_PREFIX:-lmcache:}
  remote_storage_plugin.couchbase.ttl_seconds: 3600
```

Then point LMCache at it:

```bash
export LMCACHE_CONFIG_FILE=$PWD/lmcache-couchbase.yaml
vllm serve mistralai/Mistral-7B-Instruct-v0.2 \
  --kv-transfer-config '{"kv_connector":"LMCacheConnectorV1", "kv_role":"kv_both"}'
```

### 5. Verify the Couchbase path

Before starting a full LLM server, verify Couchbase connectivity:

```bash
python examples/store_smoke.py
```

Expected output:

```text
Couchbase LMCache store smoke test passed
```

## Tutorial: local development smoke test

1. Start Couchbase Server locally, or use Capella.
2. Create the `lmcache` bucket.
3. Copy `.env.example` and export the values into your shell.
4. Install dependencies:

   ```bash
   pip install -e '.[dev]'
   ```

5. Run the unit tests:

   ```bash
   pytest
   ```

6. Run the live Couchbase smoke test:

   ```bash
   export LMCACHE_COUCHBASE_LIVE_TESTS=1
   pytest -m live
   python examples/store_smoke.py
   ```

7. Configure LMCache with `examples/lmcache-couchbase.yaml` and start your
   LMCache-enabled vLLM server.

## Troubleshooting

- `Missing required Couchbase LMCache setting`: set the corresponding
  `LMCACHE_COUCHBASE_*` variable or LMCache `extra_config` key.
- Authentication failures: verify the Couchbase user has data reader/writer
  permissions on the bucket/scope/collection.
- Capella TLS failures: use the Capella `couchbases://` connection string and
  ensure your client IP/network is allowed.
- Payload size errors: reduce LMCache `chunk_size` or model/cache dimensions, or
  add a sharding layer before production use.
- High latency or low hit rate: use Couchbase as a warm durable tier, not as the
  only cache layer; keep local CPU/GPU tiers enabled.

## Developer documentation

See [docs/developer.md](docs/developer.md) for development, verification, and
release instructions.
