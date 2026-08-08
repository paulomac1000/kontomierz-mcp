---
description: Defines the executable handoff from the production candidate to the remaining real-system and provider-backed evidence work.
doc_id: guide.kontomierz-production-readiness
type: guide
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Run the normal completion gate, then run the external evidence suite in an authorized disposable environment.
---
# Production readiness handoff

## Current boundary

The repository is intended to be a production-quality candidate before real Kontomierz and repository-administration evidence is supplied. Runtime behavior, schemas, authentication, exact-resource authorization, audit, readiness, hash-locked dependency installation, packaging, official MCP transports, and the closed release artifact are exercised by the normal automated gate.

The repository deliberately does not convert unavailable real-system or provider evidence into a passing claim. Those gaps are encoded as `external` tests that fail with `NOT IMPLEMENTED` when explicitly selected. An agent with the required disposable Kontomierz account or GitHub administration/reviewer access should implement those tests rather than delete, skip, or weaken them.

## Normal completion gate

Run from an activated Linux x64 virtual environment on Python 3.11, 3.12, or 3.13:

```bash
PYTAG="$(python -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")')"
python -m pip install --no-deps --only-binary=:all: --require-hashes -r "requirements/dev-linux-x64-${PYTAG}.lock"
python -m pip install --no-deps --only-binary=:all: --require-hashes -r requirements/build-linux-x64.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m mypy src/kontomierz_mcp
python -m bandit -q -r src/kontomierz_mcp
python -m pip_audit
python -m pytest -m "not external" --cov=kontomierz_mcp --cov-branch --cov-report=term-missing --cov-report=xml
python scripts/mock_smoke.py
```

Hosted CI additionally runs the same locked development graph on Python 3.11, 3.12, and 3.13. The exact-artifact job uses the Python 3.12 runtime lock to materialize the wheelhouse, installs a runtime-only exact-wheel environment without network resolution, runs official-client stdio and authenticated Streamable HTTP smoke, tests the installed wheel outside the source tree in a separate locked test environment, verifies the container install inputs and runtime lock, smoke-tests the non-root image, and preserves the exact release bundle. The runtime and build locks are included in the release bundle and covered by its checksum manifest.

## External evidence gate

Run only with the required controlled environment:

```bash
python -m pytest -m external -q
```

This command is intentionally red until the external evidence is implemented. `NOT IMPLEMENTED` is a handoff contract, not a flaky-test suppression mechanism. Do not replace these failures with unconditional `skip` or `xfail` merely to make a dashboard green.

### Disposable Kontomierz work

`tests/external/test_real_kontomierz_contract.py` requires a disposable account and must prove:

- wallet, transaction, budget, and schedule mutation request/response contracts plus cleanup;
- paid/unpaid schedule state transitions and budget-copy behavior;
- stable pagination ordering and an observed terminating condition;
- `client_assigned_id` uniqueness, replay behavior, and reconciliation after an uncertain response;
- post-send timeout reconciliation before retry;
- real 429/`Retry-After` behavior;
- accepted money precision and rounding behavior;
- readiness behavior for invalid credentials and dependency recovery.

Never run destructive external tests against a personal or non-disposable account. The implementing agent must create or identify disposable resources, record their stable IDs, clean up successful mutations, and leave enough diagnostics to reconcile any ambiguous mutation before another attempt.

### Provider and repository work

`tests/external/test_production_evidence.py` requires trusted provider/repository access and must prove:

- an existing protected GitHub `release` environment with required reviewers, self-review prevention, and protected-branch deployment policy;
- a schema-valid provider-backed `migration-assessment.yaml` bound to the final immutable revision and a real independent GitHub review;
- provider-verifiable build provenance for the read-only build in addition to promotion evidence.

Do not invent run IDs, artifact IDs, reviewer IDs, digests, or approval records. Evidence must be retrieved from the provider and match the exact assessed revision.

## Definition of done

The candidate may be treated as fully production/adoption complete only when all of the following are true on one final immutable revision:

1. the normal hash-locked completion gate is green;
2. the hosted exact-artifact gate is green;
3. every `external` placeholder has been replaced by executable verification and `python -m pytest -m external -q` is green;
4. the `release` environment is administratively protected;
5. an independent reviewer has submitted the real review required by the canonical adoption schema;
6. provider-backed migration assessment and build provenance verify against the same final revision;
7. no documentation or manifest claims a stronger guarantee than those executable checks prove.
