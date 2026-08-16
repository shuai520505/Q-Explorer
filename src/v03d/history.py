"""Content-addressed snapshots for immutable V0.3/V0.3-C artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_paths(workspace: str | Path, groups: dict[str, list[str]]) -> dict:
    root = Path(workspace).resolve()
    snapshot = {"algorithm": "SHA256_BYTES_PER_FILE_THEN_SHA256_SORTED_RELATIVE_PATH_AND_DIGEST", "groups": {}}
    for group, configured_paths in groups.items():
        files: dict[str, str] = {}
        for configured in configured_paths:
            target = root / configured
            candidates = sorted(target.rglob("*")) if target.is_dir() else [target]
            for candidate in candidates:
                if candidate.is_file():
                    relative = candidate.relative_to(root).as_posix()
                    files[relative] = _digest(candidate)
        lines = "".join(f"{name}\0{digest}\n" for name, digest in sorted(files.items()))
        snapshot["groups"][group] = {
            "file_count": len(files),
            "aggregate_sha256": hashlib.sha256(lines.encode("utf-8")).hexdigest(),
            "files": files,
        }
    return snapshot


def compare_snapshots(before: dict, after: dict) -> dict[str, bool]:
    groups = set(before.get("groups", {})) | set(after.get("groups", {}))
    return {
        group: before.get("groups", {}).get(group) == after.get("groups", {}).get(group)
        for group in sorted(groups)
    }
