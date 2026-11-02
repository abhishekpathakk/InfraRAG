#!/usr/bin/env python3
"""
CI Integrity Guard: Verifies frozen evaluation dataset immutability via SHA-256.

Enforces Directive #4 in AGENTS.md:
"No changes to evaluation datasets, ground-truth labels, or retrieval vocabulary/mock clusters
after a freeze tag has been cut without cutting a new git tag and adding an explicit changelog entry."
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
HASH_MANIFEST = ROOT_DIR / "evaluation" / "frozen_dataset_hashes.json"


def verify_datasets() -> None:
    if not HASH_MANIFEST.exists():
        print(f"Error: Hash manifest {HASH_MANIFEST} not found.", file=sys.stderr)
        sys.exit(1)

    with open(HASH_MANIFEST, "r", encoding="utf-8") as f:
        expected_hashes: dict[str, str] = json.load(f)

    failures = []
    print("🔒 Verifying Frozen Evaluation Dataset Integrity (SHA-256):")
    for rel_path, expected_hash in expected_hashes.items():
        file_path = ROOT_DIR / rel_path
        if not file_path.exists():
            failures.append(f"Missing file: {rel_path}")
            continue

        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            failures.append(
                f"Hash mismatch on {rel_path}!\n"
                f"  Expected: {expected_hash}\n"
                f"  Actual:   {actual_hash}\n"
                f"  VIOLATION: Frozen dataset has been modified post-freeze without an authorized tag update."
            )
        else:
            print(f"  ✅ [PASS] {rel_path} ({actual_hash[:12]}...)")

    if failures:
        print("\n❌ CI Dataset Integrity Check FAILED:", file=sys.stderr)
        for fail in failures:
            print(f"  - {fail}", file=sys.stderr)
        sys.exit(1)

    print("\n✅ All frozen evaluation datasets match locked cryptographic hashes.\n")


if __name__ == "__main__":
    verify_datasets()
