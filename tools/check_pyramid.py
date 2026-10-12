"""Fails when the test suite stops being a pyramid (rules/test-driven-development.md).

uv run python tools/check_pyramid.py
"""

from __future__ import annotations

import subprocess
import sys

MIN_UNIT_SHARE = 0.70
MAX_E2E_SHARE = 0.10


def count(tier: str) -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", tier],
        capture_output=True,
        text=True,
    )
    return sum(1 for line in result.stdout.splitlines() if "::" in line)


def main() -> int:
    unit, integration, e2e = count("unit"), count("integration"), count("e2e")
    total = unit + integration + e2e
    print(f"unit={unit} integration={integration} e2e={e2e}")
    if total == 0:
        print("no tests collected")
        return 1
    problems = []
    if unit / total < MIN_UNIT_SHARE:
        problems.append(f"unit share {unit / total:.0%} < {MIN_UNIT_SHARE:.0%}")
    if e2e / total > MAX_E2E_SHARE:
        problems.append(f"e2e share {e2e / total:.0%} > {MAX_E2E_SHARE:.0%}")
    for problem in problems:
        print("FAIL", problem)
    print("pyramid:", "FAILED" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
