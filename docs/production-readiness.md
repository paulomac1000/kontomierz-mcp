---
description: Defines the remaining production acceptance work, evidence, and operator handoff.
doc_id: guide.kontomierz-production-readiness
type: guide
status: evolving
rigor: operational
owners: [repository-maintainers]
verification: Complete each external evidence gate on the exact candidate SHA, then run the provider-backed ai-skills acceptance validator with independent review.
---
# Production readiness handoff

## Current executable baseline

The repository is a production-quality candidate before the remaining repository-administration and independent-review evidence is supplied. Runtime behavior, schemas, authentication, exact-resource authorization, audit, readiness, bounded I/O, hash-locked dependency installation, packaging, official MCP transports, and the closed release artifact are exercised by the normal automated gate.

The runtime fails closed by default:

- stdio is the default transport;
- Streamable HTTP is loopback-only and requires a bounded visible-ASCII Bearer token plus a server-owned principal;
- HTTP reads are the default capability class; writes require explicit HTTP policy and the independent operator write gate;
- destructive operations require exact capability and exact-resource allowlists on both stdio and HTTP;
- public text and scalar inputs are type-checked and bounded before upstream I/O, including UTF-8 byte limits for model-controlled text;
- successful Kontomierz bodies are streamed with a 4 MiB decoded-body limit before JSON parsing;
- every tool manifest declares a final response byte budget; oversized reads fail closed while completed mutations use a small reconciliation marker rather than a retry-provoking failure;
- readiness is authenticated before any dependency probe while liveness remains dependency-free;
- mutation timeout, transport loss, malformed or oversized success responses, and other indeterminate post-send failures remain non-retryable ambiguous outcomes;
- cancellation after a mutation starts remains cancellation to the caller but is audited as ambiguous;
- one structured server-side audit event is emitted per invocation through a sink independent of normal application log verbosity;
- `httpx` and `httpcore` request diagnostics remain at WARNING or above so the legacy query-string API credential is not emitted when application logging is DEBUG;
- normal tests and live/provider evidence are separate; plain `pytest` cannot mutate a real Kontomierz account;
- production package metadata and locks pin the exact tested MCP SDK lane (`mcp==2.0.0`).

Real Kontomierz contract evidence is implemented in `tests/external/test_real_kontomierz_contract.py` and was collected on 2026-08-08. Provider/repository gaps remain encoded in `tests/external/test_production_evidence.py` as deliberate `NOT IMPLEMENTED` failures. An agent with the required GitHub administration/reviewer access must implement those provider assertions rather than delete, skip, weaken, or fabricate them.

## Normal completion gate

Create an isolated Linux x64 environment on Python 3.11, 3.12, or 3.13 and use its interpreter explicitly:

```bash
python3 -m venv .venv
PYTAG="$(.venv/bin/python -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")')"
.venv/bin/python -m pip install --no-deps --only-binary=:all: --require-hashes \
  -r "requirements/dev-linux-x64-${PYTAG}.lock"
.venv/bin/python -m pip install --no-deps --only-binary=:all: --require-hashes \
  -r requirements/build-linux-x64.lock
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

Plain `pytest` excludes `external` by repository policy. Hosted CI additionally runs the same locked development graph on Python 3.11, 3.12, and 3.13.

## Exact artifact and Docker parity

The image must consume exactly the runtime lock and wheels already included in the verified `dist/` input closure. A local reproduction of that closure is:

```bash
rm -rf dist build src/*.egg-info
.venv/bin/python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist
mkdir -p dist/wheelhouse
.venv/bin/python -m pip download \
  --no-deps --only-binary=:all: --require-hashes \
  --dest dist/wheelhouse \
  -r requirements/runtime-linux-x64-py312.lock
cp requirements/runtime-linux-x64-py312.lock dist/
(
  cd dist
  find . -type f \( -name '*.whl' -o -name 'runtime-linux-x64-py312.lock' \) \
    -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS
)
docker build --pull=false -t kontomierz-mcp:local .
docker run --rm --entrypoint python kontomierz-mcp:local -c \
  'import os, kontomierz_mcp; assert os.geteuid() != 0; print(kontomierz_mcp.__version__)'
```

`Dockerfile` copies only `dist/`, verifies `dist/SHA256SUMS`, and installs `dist/runtime-linux-x64-py312.lock` with `--require-hashes`. It does not separately copy an unverified source-tree lock. Hosted CI additionally installs a runtime-only exact-wheel environment without network resolution, tests the installed wheel outside the source tree without `src` path injection, runs official-client stdio and authenticated Streamable HTTP smoke, verifies the image inputs, smoke-tests the non-root image, saves the image archive, and closes the release bundle with a second checksum manifest. The runtime and build locks are included in the release bundle and covered by its checksum manifest.

## Live Kontomierz evidence gate

Run only after confirming that the configured account is disposable and that real mutations are acceptable:

```bash
KONTOMIERZ_EXTERNAL_TESTS=1 \
KONTOMIERZ_ALLOW_REAL_MUTATIONS=1 \
.venv/bin/python -m pytest -o addopts='' -m external -q \
  tests/external/test_real_kontomierz_contract.py
```

Both opt-ins are required before the suite reads `KONTOMIERZ_API_KEY` from the repository `.env`. Schedule and transaction cleanup fallbacks traverse bounded pagination rather than only the first upstream page; budget cleanup uses a pre-create ID snapshot plus post-failure recovery. A failed cleanup must be treated as an operational reconciliation event, not as permission to rerun a mutation blindly. After any failed live run, an operator must still confirm that no `MCP-E2E-TEST` records remain.

The implemented live suite proves real read shapes, form-encoded schedule/transaction/budget writes with cleanup, schedule paid/unpaid transitions, schedule pagination ordering and termination, withdrawal amount normalization, credential rejection/success, upstream `DD-MM-YYYY` date behavior, and rejection of JSON-encoded write bodies.

The following real-system behaviors remain separate evidence gaps rather than implicit claims:

- `client_assigned_id` uniqueness/replay/reconciliation semantics;
- post-send timeout reconciliation before retry;
- real 429/`Retry-After` behavior;
- full accepted money precision/rounding limits beyond the observed normalization case;
- readiness recovery transitions under invalid/restored credentials;
- budget-copy semantics;
- wallet mutation response behavior not yet exercised on the evidence account.

Never run destructive external tests against a personal or non-disposable account.

## Provider and repository evidence gate

`tests/external/test_production_evidence.py` requires trusted provider/repository access and must prove:

- an existing protected GitHub `release` environment with required reviewers, self-review prevention, and protected-branch deployment policy;
- a provider-backed migration/adoption assessment bound to the final immutable revision and a real independent GitHub review;
- provider-verifiable build provenance for the read-only build in addition to promotion evidence.

To exercise those placeholders deliberately, clear the default marker policy:

```bash
.venv/bin/python -m pytest -o addopts='' -m "external and evidence" -q \
  tests/external/test_production_evidence.py
```

This provider command remains intentionally red until external authority exists. `NOT IMPLEMENTED` is a handoff contract, not a flaky-test suppression mechanism. Do not invent run IDs, artifact IDs, reviewer IDs, digests, or approval records. Evidence must be retrieved from the provider and match the exact assessed revision.

## ai-skills authority

The candidate CI pins an immutable `AI_SKILLS_REV` rather than a branch name. The assessment records the exact `fix/unified-contract-release-hardening` revision used for review. Before final approval, confirm that the branch has not moved; if it has, repin the exact new revision, rerun the standards gate, and update the assessment. A previously green run against an older authority is not evidence for a later standard.

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

The repository intentionally does not claim formal L2+ adoption before these conditions are met.
