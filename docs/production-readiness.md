---
description: Defines production verification, release evidence, external provider controls, and operator handoff for the merged 2.0.0 baseline.
doc_id: guide.kontomierz-production-readiness
type: guide
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Run repository-owned gates on the exact source revision, then complete authority-owned provider-backed ai-skills acceptance and independent review for that same revision.
---
# Production readiness handoff

## Current baseline

Version 2.0.0 is merged to `main`. The merged implementation includes the repository-owned runtime, schema, authorization, audit, bounded-I/O, dependency-lock, packaging, official MCP transport, exact-artifact, and structural standards controls described in this repository.

The runtime fails closed by default:

- stdio is the default transport;
- Streamable HTTP is Bearer-authenticated and loopback-only;
- HTTP authorization is read-only by default;
- writes require the independent `ENABLE_WRITE_OPERATIONS` operator gate;
- destructive calls require exact capability/resource allowlists;
- public schemas reject undeclared properties and invalid scalar coercions;
- model-controlled inputs, HTTP bodies, upstream bodies, final results, and audit events are bounded;
- authenticated readiness performs only bounded dependency work;
- completion-uncertain mutations are non-retryable and require reconciliation;
- application-dispatched invocations are audited without credentials, raw arguments, or protected result bodies;
- production metadata pins `mcp==2.0.0` and the exact-artifact path uses hash-locked dependency graphs.

Repository-owned green CI is necessary but is not equivalent to provider-backed adoption. The remaining external controls are described below.

## Normal repository gate

Use an isolated Linux x64 Python 3.11, 3.12, or 3.13 environment with the matching committed exact-wheel lock:

```bash
python3 -m venv .venv
. .venv/bin/activate

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

Plain `pytest` excludes the `external` evidence suite. Hosted CI runs the locked graph across Python 3.11, 3.12, and 3.13.

## Exact artifact and Docker parity

The exact-artifact lane uses Python 3.12. It builds one application wheel with `SOURCE_DATE_EPOCH` bound to the source commit timestamp, materializes the locked runtime wheelhouse, and then treats that materialized artifact set as the release input.

The lane then:

1. installs the exact wheel outside the source tree;
2. runs the normal test suite against that installed artifact;
3. runs official MCP client smoke over stdio and authenticated Streamable HTTP;
4. captures the public MCP contract from the same installed wheel;
5. writes `SOURCE_REVISION` and checksum manifests;
6. builds the non-root Docker image from those verified `dist/` inputs;
7. verifies the OCI `org.opencontainers.image.revision` label;
8. smoke-tests the exact image;
9. closes the release bundle with checksum metadata.

The Dockerfile does not rebuild application source.

To reproduce the repository-owned exact lane locally from a clean checkout, use Python 3.12 and an `ai-skills` checkout whose repository/revision matches `trusted-executable-sources.lock.yaml`:

```bash
python scripts/local_exact_gate.py --ai-skills-root ../ai-skills
```

The helper intentionally does not claim provider-backed adoption evidence.

## Live Kontomierz evidence gate

Run destructive external tests only against an explicitly accepted **exclusive disposable account**. Never run them against an ordinary personal account.

The live suite requires all mutation safety controls, including the expected disposable wallet identity:

```bash
KONTOMIERZ_EXTERNAL_TESTS=1 \
KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 \
KONTOMIERZ_EXCLUSIVE_DISPOSABLE_ACCOUNT=1 \
KONTOMIERZ_DISPOSABLE_WALLET_ID=123 \
python -m pytest -o addopts='' -m external -q tests/external/test_real_kontomierz_contract.py
```

Before mutation or cleanup, the guard verifies the expected wallet against the authenticated `user_accounts.json` response. The suite pre-cleans only the controlled namespace, captures relevant baselines, uses bounded reconciliation, and verifies post-test cleanup. A cleanup result that cannot be confirmed fails the run rather than being ignored.

Implemented live evidence covers the currently recorded read shapes, form-encoded transaction/budget/schedule writes, schedule paid/unpaid transitions, schedule pagination behavior, withdrawal normalization, credential rejection/success, upstream `DD-MM-YYYY` behavior, and rejection of the obsolete JSON write mode.

Unclaimed real-system behavior includes `client_assigned_id` uniqueness/replay semantics, interrupted-create reconciliation after a post-send failure, real 429/`Retry-After`, wallet create response-body behavior, populated transaction pagination termination, and budget-copy semantics.

## Structural standards versus provider-backed adoption

`trusted-executable-sources.lock.yaml` is the repository-side executable-provenance declaration. Repository-owned CI can resolve its immutable `ai-skills` revision, verify recorded hashes, and run structural standards checks from that authority checkout. This proves which verifier bytes were used; it does not prove that the repository independently approved itself.

Provider-backed adoption must begin in the authority repository from a protected authority ref through `.github/workflows/consumer-acceptance-dispatch.yml`. The authority-owned dispatcher supplies the exact repository and source revision and calls the same-revision local `consumer-acceptance.yml`.

The external acceptance path is responsible for verifying:

- authority workflow repository/ref/SHA identity;
- protected authority ref;
- equality between externally supplied authority coordinates and this repository's trust declaration;
- provider controls on this repository;
- exact-source evidence;
- independent review;
- provider-backed build/release provenance required by the selected adoption level.

A reusable-workflow call initiated by this repository remains diagnostic rather than authoritative.

A fresh provider check after the 2.0.0 merge still reports `main` as unprotected. Formal adoption therefore remains **`provider-preflight-blocked`** until the required provider settings are established and the authority-owned preflight succeeds.

## Release trust boundary

The release design separates verification, unprivileged candidate execution, and production write authority.

1. **verify-artifact** is read-only. It requires the release source revision to be the exact trusted default-branch tip, verifies the release-environment policy expected by the workflow, downloads the closed CI bundle, and validates checksums/source identity without executing repository content.
2. **quarantine** loads and smokes the exact tested image while remaining unprivileged to the production package. It pushes to an isolated non-GHCR quarantine registry, resolves an immutable digest, pulls that digest again, verifies source-revision identity, and smoke-tests the pulled object.
3. **publish** runs behind the protected `release` environment. It receives only the immutable quarantine reference/digest, does not checkout repository code or execute the CI archive, promotes the exact digest to production GHCR using registry tooling, verifies the resulting digest, and emits a promotion attestation.

The exact default-branch-tip requirement prevents an older successful run from being promoted after `main` advances.

## Administrator handoff

Before provider-backed acceptance can move beyond `provider-preflight-blocked`, administrators must make the required provider state observable and acceptable:

- protect the default branch `main` with the intended required checks and merge policy;
- create/configure the literal `release` environment expected by the workflow, including reviewer/deployment rules and self-review prevention where required;
- configure `QUARANTINE_REGISTRY` and `QUARANTINE_REPOSITORY` plus `QUARANTINE_USERNAME`/`QUARANTINE_TOKEN`;
- ensure the quarantine registry is not the production GHCR target;
- provide provider-verifiable evidence that quarantine credentials cannot mutate the production package;
- launch `paulomac1000/ai-skills/.github/workflows/consumer-acceptance-dispatch.yml` from the intended protected authority revision for the exact repository revision being evaluated;
- obtain independent review and provider-backed build provenance bound to that same immutable source/artifact identity.

Repository source cannot manufacture these administrative facts.

## Definition of done

Repository implementation readiness and formal adoption are separate states.

The repository may claim formal L2+/`adopted` completion only when all of the following are true for one exact immutable source revision:

1. hash-locked quality and compatibility gates pass;
2. structural standards and exact-artifact gates pass;
3. all claimed live Kontomierz behavior is backed by authorized disposable-account evidence;
4. branch/environment/credential provider controls are observable and pass the external preflight;
5. the protected authority dispatcher runs same-revision acceptance for the intended immutable `ai-skills` authority SHA and repository source revision;
6. independent review is bound to that exact revision;
7. provider-backed build provenance matches the same artifact identity;
8. documentation and manifests claim no stronger guarantee than the evidence supports.

Until those conditions are met, describe the merged 2.0.0 implementation as repository-tested and structurally aligned with the pinned standards, not as formally adopted.
