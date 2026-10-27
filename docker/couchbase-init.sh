#!/usr/bin/env bash
# One-shot initialization of the demo Couchbase node and the lmcache bucket.
set -euo pipefail

HOST=${COUCHBASE_HOST:-couchbase}
USER=${LMCACHE_COUCHBASE_USERNAME:-Administrator}
PASS=${LMCACHE_COUCHBASE_PASSWORD:-password}
BUCKET=${LMCACHE_COUCHBASE_BUCKET:-lmcache}

# Any HTTP answer (200 before init, 401 after) means the REST API is up.
until curl -s -o /dev/null "http://${HOST}:8091/pools"; do sleep 2; done

if ! curl -fs -u "${USER}:${PASS}" "http://${HOST}:8091/pools/default" >/dev/null; then
  couchbase-cli cluster-init -c "${HOST}" \
    --cluster-username "${USER}" --cluster-password "${PASS}" \
    --cluster-name lmcache-demo --services data \
    --cluster-ramsize "${COUCHBASE_RAM_MB:-4096}"
fi

if ! couchbase-cli bucket-list -c "${HOST}" -u "${USER}" -p "${PASS}" | grep -qx "${BUCKET}"; then
  couchbase-cli bucket-create -c "${HOST}" -u "${USER}" -p "${PASS}" \
    --bucket "${BUCKET}" --bucket-type couchbase \
    --bucket-ramsize "${COUCHBASE_BUCKET_RAM_MB:-3072}" \
    --bucket-eviction-policy fullEviction --bucket-replica 0 --wait
fi

until curl -fs -u "${USER}:${PASS}" \
  "http://${HOST}:8091/pools/default/buckets/${BUCKET}" | grep -q '"status":"healthy"'; do
  sleep 2
done
echo "Couchbase bucket ${BUCKET} is ready"
