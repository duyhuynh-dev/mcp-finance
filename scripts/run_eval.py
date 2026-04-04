#!/usr/bin/env python3
"""Run JSON scenarios under scenarios/eval (exit 1 if any fail)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "packages", "core"))

from finance_core.eval_runner import discover_and_run  # noqa: E402


def main() -> None:
    d = os.path.join(ROOT, "scenarios", "eval")
    results = discover_and_run(d)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{status}  {r.name}  {r.detail}")
    if any(not x.passed for x in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
