"""Immutable, private transfer manifest for an approved affinity runtime."""

from __future__ import annotations

import hashlib
import json
import csv
from pathlib import Path


BUCKET = "ml-runtime-artifacts"
MANIFEST_NAME = "classio_runtime_bundle.json"
REQUIRED_FILES = (
    "resource_affinity_run_summary.json",
    "resource_affinity_model_comparison.csv",
    "resource_affinity_dataset_frozen.csv",
    "resource_affinity_cluster_assignments.csv",
    "resource_affinity_representation_manifest.json",
)
REPRESENTATION_KEYS = ("vectorizer", "normalizer", "svd", "vectors", "resource_keys")


def runtime_bundle_manifest(run_dir: Path, model_name: str) -> dict:
    representation = json.loads((run_dir / REQUIRED_FILES[-1]).read_text(encoding="utf-8"))
    summary = json.loads((run_dir / REQUIRED_FILES[0]).read_text(encoding="utf-8"))
    if str(representation.get("run_id") or "") != run_dir.name:
        raise ValueError("Representation run ID does not match the approved run")
    if summary.get("run_id") and str(summary["run_id"]) != run_dir.name:
        raise ValueError("Summary run ID does not match the approved run")
    with (run_dir / REQUIRED_FILES[1]).open(newline="", encoding="utf-8") as handle:
        if model_name not in {str(row.get("model_name") or "") for row in csv.DictReader(handle)}:
            raise ValueError("Approved model is missing from the run comparison")
    files = set(REQUIRED_FILES)
    for key in REPRESENTATION_KEYS:
        raw = (representation.get("files") or {}).get(key)
        if not raw:
            if key == "svd":
                continue
            raise ValueError(f"Missing runtime representation: {key}")
        filename = Path(str(raw)).name
        path = (run_dir / filename).resolve()
        if path.parent != run_dir.resolve() or not path.is_file():
            raise ValueError(f"Runtime representation unavailable: {key}")
        expected = (representation.get("file_checksums") or {}).get(key)
        if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Runtime representation checksum mismatch: {key}")
        files.add(filename)
    return {
        "schema_version": 1,
        "run_id": run_dir.name,
        "model_name": model_name,
        "files": {
            name: {"sha256": hashlib.sha256((run_dir / name).read_bytes()).hexdigest(), "size": (run_dir / name).stat().st_size}
            for name in sorted(files)
        },
    }
