# vLLM + LMCache (official LMCache image) with the Couchbase plugins installed:
# - couchbase_lm_cache.l2_adapter.CouchbaseL2Adapter for `lmcache server` (MP mode)
# - couchbase_lm_cache.connector.CouchbaseConnector for in-process LMCacheConnectorV1
ARG LMCACHE_IMAGE=lmcache/vllm-openai:v0.5.6
FROM ${LMCACHE_IMAGE}

COPY pyproject.toml README.md /opt/couchbase-lm-cache/
COPY src /opt/couchbase-lm-cache/src
COPY tests /opt/couchbase-lm-cache/tests
RUN uv pip install --python /opt/venv/bin/python --no-cache /opt/couchbase-lm-cache

WORKDIR /opt/couchbase-lm-cache
