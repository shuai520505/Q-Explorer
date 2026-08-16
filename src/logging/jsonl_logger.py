"""Small append-only JSONL writers with deterministic sequential IDs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonlTrace:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid JSONL at {self.path}:{line_number}") from exc
        return records


class ExperimentLogger(JsonlTrace):
    id_pattern = re.compile(r"^EXP_(\d{6})$")

    def next_experiment_id(self) -> str:
        maximum = 0
        for record in self.read_all():
            match = self.id_pattern.match(str(record.get("experiment_id", "")))
            if match:
                maximum = max(maximum, int(match.group(1)))
        return f"EXP_{maximum + 1:06d}"

    def append_experiment(self, record: dict[str, Any]) -> None:
        required = {"experiment_id", "hamiltonian_id", "status", "configuration"}
        missing = required - record.keys()
        if missing:
            raise ValueError(f"Experiment record missing fields: {sorted(missing)}")
        enriched = dict(record)
        enriched.setdefault("recorded_at", utc_now())
        self.append(enriched)

