#!/usr/bin/env python3
"""Run the repository's one canonical governed-document validation command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai-skills-root", type=Path, required=True)
    args = parser.parse_args(argv)

    ai_skills_root = args.ai_skills_root.resolve(strict=True)
    validator = ai_skills_root / "skills/afds-doc-writer/validate.py"
    if not validator.is_file():
        parser.error(f"trusted AFDS validator is missing: {validator}")
    try:
        subprocess.run(
            [sys.executable, str(validator), "AGENTS.md", "docs"],
            cwd=ROOT,
            check=True,
            timeout=5 * 60,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
