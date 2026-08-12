---
description: Defines the remaining production acceptance work, evidence, and operator handoff.
doc_id: guide.kontomierz-production-readiness
type: guide
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Complete each external evidence gate on the exact candidate SHA, then run provider-backed ai-skills acceptance with independent review.
---
# Production readiness handoff

## Current executable baseline

The repository is a production-quality candidate before the remaining repository-administration, provider, and independent-review evidence is supplied. Runtime behavior, schemas, authentication, exact-resource authorization, audit, readiness, bounded I/O, hash-locked dependencies, packaging, official MCP transports, trusted standards validation, and the closed release artifact are exercised by the normal automated gate.

The runtime fails closed by default: stdio is default; Streamable HTTP is authenticated and loopback-only; writes require server-owned policy; destructive operations require exact capability/resource allowlists; model-controlled inputs and upstream/result bodies are bounded; readiness authenticates before dependency I/O; ambiguous mutation outcomes are non-retryable; audit is structured and credential-free; request diagnostics cannot expose the query-string API key at debug verbosity; plain `pytest` excludes external evidence; and production metadata/locks pin `mcp==2.0.0`.

Real Kontomierz evidence lives in `tests/external/test_real_kontomierz_contract.py`, `upstream-contract.yaml`, and `live-backend-test-policy.yaml`. Provider/repository gaps remain deliberate `NOT IMPLEMENTED` tests in `tests/external/test_production_evidence.py`; they must be implemented from real provider/admin authority rather than skipped or fabricated.

## Normal completion gate

Use an isolated Linux x64 Python 3.11, 3.12, or 3.13 environment and the committed exact-wheel locks:

```bash
python3 -m venv .venv
PYTAG="$(.venv/bin/python -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")')"
.venv/bin/python -m pip install --no-deps --only-binary=:all: --require-hashes -r "requirements/dev-linux-x64-${PYTAG}.lock"
.venv/bin/python -m pip install --no-deps --only-binary=:all: --require-hashes -r requirements/build-linux-x64.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src/kontomierz_mcp
.venv/bin/python -m bandit -q -r src/kontomierz_mcp
.venv/bin/python -m pip_audit
.venv/bin/python -m pytest --cov=kontomierz_mcp --cov-branch --cov-report=term-missing --cov-report=xml
.venv/bin/python scripts/mock_smoke.py
```

Plain pytest excludes `external`; hosted CI additionally runs the locked graph on Python 3.11, 3.12, and 3.13.

## Exact artifact and Docker parity

The exact-artifact job builds one wheel, materializes the Python 3.12 runtime wheelhouse, installs/tests the exact wheel outside the source tree, runs official-client stdio and authenticated HTTP smoke, builds a non-root image from verified inputs, binds `org.opencontainers.image.revision` to the full source SHA, verifies that label, smoke-tests the exact image, and closes the release bundle with checksum metadata. The Dockerfile does not rebuild project source.

## Live Kontomierz evidence gate

Run only against an explicitly accepted disposable account:

```bash
KONTOMIERZ_EXTERNAL_TESTS=1 \
KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 \
.venv/bin/python -m pytest -o addopts='' -m external -q tests/external/test_real_kontomierz_contract.py
```

Both opt-ins are required before credential access. The guard pre-cleans the unique namespace, captures a budget baseline, then after each test traverses paid/unpaid schedules, reconciles transactions and new budgets, deletes discovered resources, and fails if cleanup cannot be verified.

Implemented live evidence covers read shapes, form-encoded schedule/transaction/budget writes, schedule paid/unpaid transitions, schedule pagination ordering/termination, withdrawal normalization, credential rejection/success, upstream `DD-MM-YYYY` behavior, and JSON-write rejection. Remaining real-system gaps include `client_assigned_id` uniqueness/reconciliation, post-send timeout reconciliation, real rate limits, broader precision/rounding limits, readiness credential recovery, budget-copy behavior, wallet mutation response behavior, and populated transaction pagination termination.

## Trusted standards authority

`trusted-executable-sources.lock.yaml` is the single authority source. It binds the reviewed exact `paulomac1000/ai-skills` revision and SHA-256 digests for every trusted executable used by standards CI. CI resolves authority coordinates from that lock, validates the lock from the immutable external checkout, then runs AFDS, AGENTS, workflow policy, consumer-trust hygiene, MCP discovery, upstream-contract, and live-backend-policy checks. If the authority branch moves, review its delta and update this canonical lock only when the new branch head is the intended authority; a previously green run against an older lock is not evidence for the later revision.

## Release trust and administrative gate

The release workflow deliberately separates candidate execution from production write authority:

1. Read-only `verify-artifact` proves source ancestry, release-environment policy, bundle checksums, and source SHA.
2. `quarantine` has no production package permission. It loads/smokes the tested CI archive, pushes it to an isolated non-GHCR registry, resolves an immutable digest, removes the local image, pulls `reference@digest`, rechecks the OCI source-revision label, and smokes the pulled digest.
3. Protected `publish` receives only the immutable quarantine reference/digest. It never checks out candidate code, downloads the archive, loads the image, or runs candidate content; it promotes the exact digest to GHCR using registry tooling, verifies the production digest, and emits a promotion attestation.

Administrators must create/protect the `release` environment and configure `QUARANTINE_REGISTRY`, `QUARANTINE_REPOSITORY`, `QUARANTINE_USERNAME`, and `QUARANTINE_TOKEN`. The quarantine registry must not be production GHCR. The source tree cannot prove the actual provider scope of the secret, so `tests/external/test_production_evidence.py` intentionally requires provider-backed proof that the quarantine credential cannot mutate production.

## Provider and repository evidence gate

The external provider suite must eventually prove:

- the protected `release` environment has required reviewers, self-review prevention, and protected-branch policy;
- quarantine credentials are isolated from production authority;
- provider-backed migration/adoption assessment matches the final immutable SHA and a real independent GitHub review;
- provider-verifiable provenance binds the original read-only CI build to that SHA/artifact.

Run those placeholders only deliberately:

```bash
.venv/bin/python -m pytest -o addopts='' -m "external and evidence" -q tests/external/test_production_evidence.py
```

The command remains intentionally red until the external authorities exist. Never fabricate run IDs, reviewer IDs, registry scope, digests, or approval records.

## Definition of done

The candidate may be treated as fully production/adoption complete only when all of the following are true on one final immutable revision:

1. normal hash-locked quality and compatibility gates pass;
2. latest-reviewed standards and exact-artifact gates pass;
3. required live Kontomierz evidence passes in an authorized disposable environment;
4. all provider/repository placeholders are replaced by real executable verification and pass;
5. release environment and quarantine registry/credential boundaries are administratively verified;
6. an independent reviewer submits the canonical review;
7. provider-backed migration/adoption assessment and build provenance match the same SHA;
8. documentation/manifests claim no stronger guarantee than the evidence supports.

The repository intentionally does not claim formal L2+ adoption before these conditions are met.
