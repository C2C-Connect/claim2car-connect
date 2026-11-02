#!/usr/bin/env python3
"""Validate the repo-level M2 checkpoint guardrails.

This script is intentionally narrow: it checks that the canonical repo contains the
project governance and acceptance artifacts and that the M2 controlled-test milestone
is explicitly documented as a capture-to-seal checkpoint rather than a live pilot or
production deployment claim.
"""

from __future__ import annotations

from pathlib import Path
import sys

REQUIRED_FILES = [
    "GOVERNANCE.md",
    "README.md",
    "docs/acceptance/baseline-and-milestone.md",
    "docs/acceptance/database-contract.md",
    "docs/acceptance/product-contract.md",
    "docs/acceptance/m2-capture-to-seal-checkpoint.md",
]

REQUIRED_TOKENS = {
    "GOVERNANCE.md": [
        "M2 — Capture to seal checkpoint",
        "Pilot is a milestone inside the full product",
    ],
    "docs/acceptance/m2-capture-to-seal-checkpoint.md": [
        "controlled-test evidence",
        "capture-to-seal readiness",
        "not a broad product launch",
    ],
    "README.md": [
        "C2C-Connect/claim2car-connect is the single canonical product repository",
        "San Antonio pilot direction includes a multi-dealer network",
    ],
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = []
    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            missing.append(relative)

    if missing:
        print("M2_CHECKPOINT: FAIL")
        print("Missing required files:")
        for item in missing:
            print(f"  - {item}")
        return 1

    fails = []
    for relative, tokens in REQUIRED_TOKENS.items():
        path = root / relative
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                fails.append(f"{relative} missing token: {token}")

    if fails:
        print("M2_CHECKPOINT: FAIL")
        for item in fails:
            print(f"  - {item}")
        return 1

    print("M2_CHECKPOINT: PASS")
    print("Repository contains the governance and acceptance baseline for the controlled-test M2 checkpoint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
