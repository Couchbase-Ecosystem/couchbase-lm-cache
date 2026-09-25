# Agent notes

Repository-local guidance for automated contributors.

## Validation

Every change should pass the same commands CI runs
(`.github/workflows/ci.yml`):

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest
python -m build
```

Changes that touch `src/`, dependencies, or examples should also be verified
against a real Couchbase cluster with a task-scoped bucket/scope/collection:

```bash
export LMCACHE_COUCHBASE_LIVE_TESTS=1  # plus LMCACHE_COUCHBASE_* settings
pytest -m live
python examples/store_smoke.py
```

The connector only uses KV APIs; no SQL++ indexes are needed. Tear down any
temporary Couchbase resources afterwards.

## Conventions

- Packaging is hatchling with pip editable installs. Do not add a lockfile or
  switch package managers.
- `lmcache` is an optional extra because it pulls in torch and CUDA packages.
  Unit tests must keep passing both with and without LMCache installed.
- Never commit `.env` files, credentials, or a filled-in root-level
  `lmcache-couchbase.yaml`.

## Releases

Releases are manual (see `docs/developer.md`). Do not bump versions, create
tags or GitHub releases, upload to PyPI, or open upstream LMCache PRs without
explicit maintainer approval.
