---
description: Defines the executable handoff from the production candidate to the remaining real-system and provider-backed evidence work.
doc_id: guide.kontomierz-production-readiness
type: guide
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Run the normal completion gate, then run explicitly authorized live/provider evidence in controlled environments.
---
# Production readiness handoff

## Current boundary

The repository is intended to be a production-quality candidate before the remaining repository-administration and independent-review evidence is supplied. Runtime behavior, schemas, authentication, exact-resource authorization, audit, readiness, hash-locked dependency installation, packaging, official MCP transports, and the closed release artifact are exercised by the normal automated gate.

Real Kontomierz contract evidence has been implemented in `tests/external/test_real_kontomierz_contract.py` and was collected on 2026-08-08. Those tests remain excluded from normal pytest execution and require two explicit live-test opt-ins because they mutate the real service. Provider/repository gaps remain encoded in `tests/external/test_production_evidence.py` as deliberate `NOT IMPLEMENTED` failures. An agent with the required GitHub administration/reviewer access must implement those provider assertions rather than delete, skip, weaken, or fabricate them.

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
python -m pytest --cov=kontomierz_mcp --cov-branch --cov-report=term-missing --cov-report=xml
python scripts/mock_smoke.py
```

Plain `pytest` excludes `external` by repository policy. Hosted CI additionally runs the same locked development graph on Python 3.11, 3.12, and 3.13. The exact-artifact job uses the Python 3.12 runtime lock to materialize the wheelhouse, installs a runtime-only exact-wheel environment without network resolution, runs official-client stdio and authenticated Streamable HTTP smoke, tests the installed wheel outside the source tree in a separate locked test environment, verifies the container install inputs and runtime lock, smoke-tests the non-root image, and preserves the exact release bundle. The runtime and build locks are included in the release bundle and covered by its checksum manifest.

## Live Kontomierz evidence gate

Run only after confirming that the configured account is disposable and that real mutations are acceptable:

```bash
KONTOMIERZ_EXTERNAL_TESTS=1 \
KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 \
python -m pytest -o addopts='' -m external -q tests/external/test_real_kontomierz_contract.py
```

Both opt-ins are required before the suite reads `KONTOMIERZ_API_KEY` from the repository `.env`. Schedule, transaction, and budget tests use captured IDs plus description/snapshot reconciliation fallbacks during cleanup so a failure immediately after a successful create still triggers best-effort removal. A failed cleanup must be treated as an operational reconciliation event, not as permission to rerun the mutation blindly.

The implemented live suite currently proves real read shapes, form-encoded schedule/transaction/budget writes with cleanup, schedule paid/unpaid transitions, schedule pagination ordering and termination, withdrawal amount normalization, credential rejection/success, upstream `DD-MM-YYYY` date behavior, and rejection of JSON-encoded write bodies.

The following real-system behaviors remain separate evidence gaps rather than implicit claims:

- `client_assigned_id` uniqueness/replay/reconciliation semantics;
- post-send timeout reconciliation before retry;
- real 429/`Retry-After` behavior;
- full accepted money precision/rounding limits beyond the observed normalization case;
- readiness recovery transitions under invalid/restored credentials;
- budget-copy semantics.

Never run destructive external tests against a personal or non-disposable account.

## Provider and repository evidence gate

`tests/external/test_production_evidence.py` requires trusted provider/repository access and must prove:

- an existing protected GitHub `release` environment with required reviewers, self-review prevention, and protected-branch deployment policy;
- a provider-backed migration/adoption assessment bound to the final immutable revision and a real independent GitHub review;
- provider-verifiable build provenance for the read-only build in addition to promotion evidence.

To exercise those placeholders deliberately, clear the default marker policy:

```bash
python -m pytest -o addopts='' -m "external and evidence" -q tests/external/test_production_evidence.py
```

This provider command remains intentionally red until external authority exists. `NOT IMPLEMENTED` is a handoff contract, not a flaky-test suppression mechanism. Do not invent run IDs, artifact IDs, reviewer IDs, digests, or approval records. Evidence must be retrieved from the provider and match the exact assessed revision.

## Definition of done

The candidate may be treated as fully production/adoption complete only when all of the following are true on one final immutable revision:

1. the normal hash-locked completion gate is green;
2. the hosted exact-artifact and latest-pinned standards gates are green;
3. the required live Kontomierz evidence for the claimed behaviors is green in an explicitly authorized disposable environment;
4. every provider/repository `NOT IMPLEMENTED` placeholder has been replaced by executable verification and passes;
5. the `release` environment is administratively protected;
6. an independent reviewer has submitted the real review required by the canonical adoption contract;
7. provider-backed migration/adoption assessment and build provenance verify against the same final revision;
8. no documentation or manifest claims a stronger guarantee than those executable checks prove.
