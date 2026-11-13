"""Verify FastEmbed model download and exact ONNX SHA-256 integrity."""
import hashlib
import os
from pathlib import Path
import sys

from fastembed import TextEmbedding

EXPECTED_SHA256 = "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431"


def main() -> None:
    cache_path = os.environ.get("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")
    print(f"Pre-downloading FastEmbed model into: {cache_path}")
    _ = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", cache_dir=cache_path)

    cache_dir = Path(cache_path)
    opt_files = list(cache_dir.glob("**/model_optimized.onnx"))
    onnx_file = (
        opt_files[0]
        if opt_files
        else (list(cache_dir.glob("**/*.onnx"))[0] if list(cache_dir.glob("**/*.onnx")) else None)
    )

    if not onnx_file or not onnx_file.exists():
        print(f"ERROR: No ONNX binary downloaded in {cache_path}!", file=sys.stderr)
        sys.exit(1)

    actual_sha = hashlib.sha256(onnx_file.read_bytes()).hexdigest()
    print(f"ONNX File: {onnx_file}")
    print(f"Actual SHA-256:   {actual_sha}")
    print(f"Expected SHA-256: {EXPECTED_SHA256}")

    if actual_sha != EXPECTED_SHA256:
        print(
            f"ERROR: SHA-256 mismatch! Expected {EXPECTED_SHA256}, got {actual_sha}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("VERIFICATION SUCCESS: ONNX model binary matches expected SHA-256 exactly.")


if __name__ == "__main__":
    main()
