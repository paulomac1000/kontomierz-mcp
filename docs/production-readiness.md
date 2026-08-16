---
description: Defines the remaining production acceptance work, evidence, and operator handoff.
doc_id: guide.kontomierz-production-readiness
type: guide
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Complete each external evidence gate on the exact candidate SHA, then run authority-owned provider-backed ai-skills acceptance with independent review.
---
# Production readiness handoff

## Current executable baseline

The repository is a production-quality candidate before the remaining provider administration, live-system, provenance, and independent-review evidence is supplied. Runtime behavior, schemas, strict input handling, authentication, exact-resource authorization, audit, readiness, bounded I/O, hash-locked dependencies, packaging, official MCP transports, structural standards validation, and the closed release artifact are exercised by the normal automated gate.

The runtime fails closed by default: stdio is default; Streamable HTTP is authenticated and loopback-only; writes require server-owned policy; destructive operations require exact capability/resource allowlists; tool schemas reject undeclared properties and scalar types do not rely on coercion; optional resource IDs must be positive when supplied; model-controlled inputs and upstream/result bodies are bounded; readiness authenticates before dependency I/O; ambiguous mutation outcomes are non-retryable; application-dispatched invocations are audited without credentials; request diagnostics cannot expose the query-string API key; plain `pytest` excludes external evidence; and production metadata/locks pin `mcp==2.0.0`.

Real Kontomierz evidence lives in `tests/external/test_real_kontomierz_contract.py`, `upstream-contract.yaml`, and `live-backend-test-policy.yaml`. Provider/repository gaps remain deliberate external evidence requirements and must be implemented from real provider/admin authority rather than skipped or fabricated.

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

The exact-artifact job builds one wheel, materializes the Python 3.12 runtime wheelhouse, installs/tests the exact wheel outside the source tree, runs official-client stdio and authenticated HTTP smoke, builds a non-root image from verified inputs, binds `org.opencontainers.image.revision` to the full source SHA, verifies that label, smoke-tests the exact image, captures the public MCP contract from that same installed wheel, and closes the release bundle with checksum metadata. The Dockerfile does not rebuild project source.

## Live Kontomierz evidence gate

Run only against an explicitly accepted disposable account and include every documented live-test guard:

```bash
KONTOMIERZ_EXTERNAL_TESTS=1 \
KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 \
KONTOMIERZ_EXCLUSIVE_DISPOSABLE_ACCOUNT=1 \
KONTOMIERZ_DISPOSABLE_WALLET_ID=123 \
.venv/bin/python -m pytest -o addopts='' -m external -q tests/external/test_real_kontomierz_contract.py
```

Both mutation opt-ins are required before credential access. The guard also verifies the expected disposable wallet in the authenticated account before any cleanup or mutation, pre-cleans the unique namespace, captures a budget baseline, and after each test reconciles/deletes test-owned schedules, transactions, and new budgets. The live run fails if cleanup cannot be confirmed.

Implemented live evidence covers read shapes, form-encoded schedule/transaction/budget writes, schedule paid/unpaid transitions, schedule pagination ordering/termination, withdrawal normalization, credential rejection/success, upstream `DD-MM-YYYY` behavior, and JSON-write rejection. Remaining real-system gaps include `client_assigned_id` uniqueness/reconciliation, post-send timeout reconciliation, real rate limits, broader precision/rounding limits, readiness credential recovery, budget-copy behavior, wallet mutation response behavior, and populated transaction pagination termination.

## Structural standards evidence versus provider-backed acceptance

`trusted-executable-sources.lock.yaml` is the candidate-side executable-provenance declaration. Candidate-owned CI may resolve the declared immutable `ai-skills` revision, validate its recorded digests, and run structural standards checks from that checkout. This proves which verifier bytes ran; it does not prove provider-backed approval because the candidate controls the lock and its own CI orchestration.

Provider-backed adoption must start inside the authority repository from a protected authority ref through `.github/workflows/consumer-acceptance-dispatch.yml`. That dispatcher supplies the exact candidate repository and candidate SHA, then calls the same-revision local `consumer-acceptance.yml`. The reusable workflow verifies the authority caller/workflow repository and SHA, requires a protected authority ref, compares the externally supplied authority coordinates with the candidate trust lock, performs provider-control preflight against GitHub itself, validates exact-SHA evidence, and requires independent review. A direct candidate-owned cross-repository call to `consumer-acceptance.yml` is non-authoritative diagnostic evidence and does not satisfy provider-backed acceptance.

The current state is **`provider-preflight-blocked`**: GitHub reports `main` as unprotected and reports no environments, while `.github/workflows/publish.yml` declares the protected `release` environment. Repository code cannot repair those provider settings. An administrator must establish them and then rerun the external preflight.

## Release trust and administrative gate

The release workflow deliberately separates candidate execution from production write authority:

1. Read-only `verify-artifact` proves source ancestry, release-environment policy, bundle checksums, and source SHA.
2. `quarantine` has no production package permission. It loads/smokes the tested CI archive, pushes it to an isolated non-GHCR registry, resolves an immutable digest, removes the local image, pulls `reference@digest`, rechecks the OCI source-revision label, and smokes the pulled digest.
3. Protected `publish` receives only the immutable quarantine reference/digest. It never checks out candidate code, downloads the archive, loads the image, or runs candidate content; it promotes the exact digest to GHCR using registry tooling, verifies the production digest, and emits a promotion attestation.

Administrators must create/protect the `release` environment and configure `QUARANTINE_REGISTRY`, `QUARANTINE_REPOSITORY`, `QUARANTINE_USERNAME`, and `QUARANTINE_TOKEN`. The quarantine registry must not be production GHCR. The source tree cannot prove the actual provider scope of the secret, so provider-backed evidence must prove that the quarantine credential cannot mutate production.

## External-admin checklist

Before provider-backed acceptance can move beyond `provider-preflight-blocked`, an administrator must make the following provider state observable and acceptable, then rerun the trusted preflight:

- repository: `paulomac1000/kontomierz-mcp`;
- default branch: `main`, protected by provider policy with the reviewed required checks/merge policy;
- environment: literal `release`, present in GitHub and protected by reviewed reviewer/deployment-branch rules, including self-review prevention where required by the chosen release policy;
- quarantine credentials: scoped so they cannot mutate the production GHCR package;
- external acceptance: launch `paulomac1000/ai-skills/.github/workflows/consumer-acceptance-dispatch.yml` from the intended protected authority revision and supply the exact candidate repository/SHA; do not substitute a candidate-owned direct call to the reusable workflow;
- independent review and build-provenance evidence: both bind to that exact candidate/artifact identity.

## Definition of done

The candidate may be treated as fully production/adoption complete only when all of the following are true on one final immutable revision:

1. normal hash-locked quality and compatibility gates pass;
2. the latest-reviewed structural standards and exact-artifact gates pass;
3. required live Kontomierz evidence passes in an authorized disposable environment;
4. provider branch/environment/credential controls are observable and pass the trusted external preflight;
5. authority-owned protected dispatch runs the same-revision acceptance workflow for the intended immutable `ai-skills` authority SHA and exact candidate SHA;
6. an independent reviewer submits the canonical review;
7. provider-backed build provenance matches the same SHA/artifact;
8. documentation/manifests claim no stronger guarantee than the evidence supports.

The repository intentionally does not claim formal L2+ adoption before these conditions are met.
