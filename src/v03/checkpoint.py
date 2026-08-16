"""Atomic checkpoint/resume state that never recharges completed experiments."""

from __future__ import annotations

import json
from pathlib import Path
import os


class TaskCheckpoint:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)

    def load(self) -> dict | None:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else None

    def completed_experiment_ids(self) -> set[str]:
        state = self.load() or {}
        return set(state.get("completed_experiment_ids", []))

