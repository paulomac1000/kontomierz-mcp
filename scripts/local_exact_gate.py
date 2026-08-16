#!/usr/bin/env python3
"""Reproduce repository-owned standards, quality, and exact-image gates locally.

Provider-backed adoption evidence is intentionally out of scope: this command
verifies only controls that can be reproduced from an exact clean checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_LOCK = ROOT / "requirements/runtime-linux-x64-py312.lock"
_BUILD_LOCK = ROOT / "requirements/build-linux-x64.lock"
_DEV_LOCK = ROOT / "requirements/dev-linux-x64-py312.lock"


def _run(arguments: list[str], *, cwd: Path = ROOT, capture: bool = False) -> str:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
        timeout=20 * 60,
    )
    return completed.stdout.strip() if capture else ""


def _source_sha() -> str:
    return _run(["git", "rev-parse", "HEAD"], capture=True)


def _require_clean_checkout(root: Path) -> None:
    status = _run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, capture=True)
    if status:
        raise RuntimeError(f"exact local gate requires a clean checkout: {root}")


def _trusted_ai_skills() -> tuple[str, str]:
    text = (ROOT / "trusted-executable-sources.lock.yaml").read_text(encoding="utf-8")
    marker = "  - id: ai-skills\n"
    if marker not in text:
        raise RuntimeError("ai-skills is missing from trusted executable source lock")
    block = text.split(marker, 1)[1].split("\n  - id:", 1)[0]
    repository = re.search(r"^    repository: ([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s*$", block, re.MULTILINE)
    revision = re.search(r"^    revision: ([0-9a-f]{40})\s*$", block, re.MULTILINE)
    if repository is None or revision is None:
        raise RuntimeError("trusted ai-skills repository/revision is malformed")
    return repository.group(1), revision.group(1)


def _require_authority(ai_skills_root: Path, expected_repository: str, expected_revision: str) -> None:
    root = ai_skills_root.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("ai-skills root must be a directory")
    _require_clean_checkout(root)
    actual_revision = _run(["git", "rev-parse", "HEAD"], cwd=root, capture=True)
    if actual_revision != expected_revision:
        raise RuntimeError(f"ai-skills checkout is {actual_revision}, expected {expected_revision}")
    remote = _run(["git", "remote", "get-url", "origin"], cwd=root, capture=True)
    normalized = remote.removesuffix(".git").rstrip("/")
    if not normalized.endswith("/" + expected_repository):
        raise RuntimeError(f"ai-skills origin does not match {expected_repository}")


def _run_standards(ai_skills_root: Path, temporary: Path) -> None:
    contracts = ai_skills_root / "contracts"
    mcp_tools = ai_skills_root / "skills/mcp-server-architect/tools"
    _run(
        [
            sys.executable,
            str(contracts / "validate_trusted_executable_sources.py"),
            "trusted-executable-sources.lock.yaml",
            "--repository-root",
            ".",
            "--authority-root",
            f"ai-skills={ai_skills_root}",
            "--require-authority",
        ]
    )
    _run([sys.executable, str(ai_skills_root / "skills/afds-doc-writer/validate.py"), "AGENTS.md", "docs"])
    _run(
        [
            sys.executable,
            str(ai_skills_root / "skills/agents-md-architect/tools/audit_agents_md.py"),
            ".",
            "--profile",
            "mcp-server",
            "--layout",
            "single",
            "--language",
            "en",
            "--strict",
        ]
    )
    _run([sys.executable, str(ai_skills_root / "skills/ci-cd-architect/tools/check_github_actions_policy.py"), "."])
    _run([sys.executable, str(ai_skills_root / "skills/ci-cd-architect/tools/check_consumer_trust_hygiene.py"), "."])

    discovery = temporary / "discovery.json"
    plan = temporary / "plan.json"
    _run([sys.executable, str(mcp_tools / "inspect_existing_project.py"), ".", "--output", str(discovery)])
    _run(
        [
            sys.executable,
            str(mcp_tools / "plan_existing_project.py"),
            ".",
            "--target-level",
            "L2",
            "--output",
            str(plan),
        ]
    )
    discovered = json.loads(discovery.read_text(encoding="utf-8"))
    if discovered["unknowns"]:
        raise RuntimeError("trusted discovery still reports unknowns: " + "; ".join(discovered["unknowns"]))
    if discovered["plan"].get("container_artifact_binding") != "declared":
        raise RuntimeError("container artifact source binding is not declared")

    _run(
        [
            sys.executable,
            str(contracts / "validate_upstream_contract.py"),
            "upstream-contract.yaml",
            "--require-observed",
        ]
    )
    _run([sys.executable, str(contracts / "validate_live_backend_test_policy.py"), "live-backend-test-policy.yaml"])


def _run_quality() -> None:
    _run([sys.executable, "-m", "pip", "check"])
    _run([sys.executable, "-m", "ruff", "check", "."])
    _run([sys.executable, "-m", "ruff", "format", "--check", "."])
    _run([sys.executable, "-m", "mypy", "src/kontomierz_mcp"])
    _run([sys.executable, "-m", "bandit", "-q", "-r", "src/kontomierz_mcp"])
    _run([sys.executable, "-m", "pip_audit"])
    _run([sys.executable, "-m", "pytest", "-m", "not external", "-q"])
    _run([sys.executable, "scripts/mock_smoke.py"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_image_manifest(source_sha: str) -> None:
    dist = ROOT / "dist"
    (dist / "SOURCE_REVISION").write_text(source_sha + "\n", encoding="ascii", newline="\n")
    files = sorted(
        path
        for path in dist.rglob("*")
        if path.is_file()
        and (path.suffix == ".whl" or path.name in {"runtime-linux-x64-py312.lock", "SOURCE_REVISION"})
    )
    if not files:
        raise RuntimeError("no exact image inputs were materialized")
    manifest = "".join(f"{_sha256(path)}  {path.relative_to(dist).as_posix()}\n" for path in files)
    (dist / "SHA256SUMS").write_text(manifest, encoding="ascii", newline="\n")


def _build_exact_image(source_sha: str) -> None:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("exact local artifact lane requires Python 3.12")
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    for egg_info in (ROOT / "src").glob("*.egg-info"):
        shutil.rmtree(egg_info, ignore_errors=True)
    _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", ".", "--wheel-dir", "dist"])
    wheelhouse = ROOT / "dist/wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--no-deps",
            "--only-binary=:all:",
            "--require-hashes",
            "--dest",
            str(wheelhouse),
            "-r",
            str(_RUNTIME_LOCK),
        ]
    )
    shutil.copy2(_RUNTIME_LOCK, ROOT / "dist/runtime-linux-x64-py312.lock")
    _write_image_manifest(source_sha)
    _run(["sha256sum", "--check", "SHA256SUMS"], cwd=ROOT / "dist")

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"^FROM\s+(\S+)", dockerfile, re.MULTILINE)
    if match is None or "@sha256:" not in match.group(1):
        raise RuntimeError("Dockerfile base image must be digest-pinned")
    base_image = match.group(1)
    _run(["docker", "pull", base_image])
    tag = f"kontomierz-mcp:{source_sha}"
    _run(
        [
            "docker",
            "build",
            "--pull=false",
            "--build-arg",
            f"EXPECTED_SOURCE_REVISION={source_sha}",
            "-t",
            tag,
            ".",
        ]
    )
    revision = _run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            '{{ index .Config.Labels "org.opencontainers.image.revision" }}',
            tag,
        ],
        capture=True,
    )
    if revision != source_sha:
        raise RuntimeError("container source revision label does not match exact checkout")
    _run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "python",
            tag,
            "-c",
            "import os, kontomierz_mcp; assert os.geteuid() != 0; print(kontomierz_mcp.__version__)",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai-skills-root", type=Path, required=True)
    parser.add_argument("--skip-quality", action="store_true")
    parser.add_argument("--skip-image", action="store_true")
    args = parser.parse_args(argv)

    if Path.cwd().resolve() != ROOT:
        parser.error(f"run from repository root: {ROOT}")
    try:
        _require_clean_checkout(ROOT)
        source_sha = _source_sha()
        repository, revision = _trusted_ai_skills()
        _require_authority(args.ai_skills_root, repository, revision)
        with tempfile.TemporaryDirectory(prefix="kontomierz-local-gate-") as temporary_name:
            _run_standards(args.ai_skills_root.resolve(), Path(temporary_name))
        if not args.skip_quality:
            _run_quality()
        if not args.skip_image:
            _build_exact_image(source_sha)
    except (OSError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    print(f"local exact gate passed for {source_sha}; provider-backed evidence was not claimed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
