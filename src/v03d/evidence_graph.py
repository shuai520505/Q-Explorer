"""Read-only graph over immutable Q-Explorer scientific traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def missing_link(kind: str, identifier=None, reason: str = "not_found") -> dict:
    return {"status": "MISSING_LINK", "kind": kind, "identifier": identifier, "reason": reason}


class EvidenceGraph:
    """Index trace nodes without fabricating identifiers absent from history."""

    NODE_TYPES = ("runs", "actions", "experiments", "evidence", "hypotheses", "revisions")

    def __init__(self, records: dict[str, list[dict]] | None = None) -> None:
        self.records = {name: list((records or {}).get(name, [])) for name in self.NODE_TYPES}
        self._by_id = {
            "actions": self._index("actions", "action_id"),
            "experiments": self._index("experiments", "experiment_id"),
            "evidence": self._index("evidence", "evidence_id"),
            "revisions": self._index("revisions", "revision_id"),
        }

    @classmethod
    def from_trace_roots(cls, roots: Iterable[str | Path]) -> "EvidenceGraph":
        records = {name: [] for name in cls.NODE_TYPES}
        for root_value in roots:
            root = Path(root_value)
            for name in cls.NODE_TYPES:
                path = root / f"{name}.jsonl"
                if not path.exists():
                    continue
                for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if line.strip():
                        row = json.loads(line)
                        row["_source_path"] = path.as_posix()
                        row["_source_line"] = line_number
                        records[name].append(row)
        return cls(records)

    def _index(self, kind: str, key: str) -> dict[str, list[dict]]:
        index: dict[str, list[dict]] = {}
        for row in self.records[kind]:
            if row.get(key):
                index.setdefault(str(row[key]), []).append(row)
        return index

    @staticmethod
    def _resolve(kind: str, identifier, rows: list[dict]) -> dict:
        if not rows:
            return missing_link(kind, identifier)
        if len(rows) > 1:
            unique = {json.dumps(row, sort_keys=True, default=str) for row in rows}
            if len(unique) > 1:
                return missing_link(kind, identifier, "ambiguous")
        return rows[-1]

    def get_run(self, run_id: str) -> dict:
        rows = [row for row in self.records["runs"] if row.get("run_id") == run_id]
        terminal = [row for row in rows if row.get("event") in {"END", "FAILED"}]
        return self._resolve("run", run_id, terminal or rows)

    def get_action(self, action_id: str) -> dict:
        return self._resolve("action", action_id, self._by_id["actions"].get(action_id, []))

    def get_experiment(self, experiment_id: str) -> dict:
        return self._resolve("experiment", experiment_id, self._by_id["experiments"].get(experiment_id, []))

    def get_evidence(self, evidence_id: str) -> dict:
        return self._resolve("evidence", evidence_id, self._by_id["evidence"].get(evidence_id, []))

    def get_hypothesis(self, hypothesis_id: str, run_id: str | None = None, round_no: int | None = None):
        rows = [row for row in self.records["hypotheses"] if row.get("hypothesis_id") == hypothesis_id]
        if run_id is not None:
            rows = [row for row in rows if row.get("run_id") == run_id]
        if round_no is not None:
            rows = [row for row in rows if int(row.get("round", -1)) == int(round_no)]
        if not rows:
            return missing_link("hypothesis", hypothesis_id)
        return rows[-1] if run_id is not None else rows

    def get_revision(self, revision_id: str) -> dict:
        return self._resolve("revision", revision_id, self._by_id["revisions"].get(revision_id, []))

    def revisions_for_run(self, run_id: str) -> list[dict]:
        return sorted(
            (row for row in self.records["revisions"] if row.get("run_id") == run_id),
            key=lambda row: (int(row.get("round", 0)), int(row.get("_source_line", 0))),
        )

    def get_evidence_for_revision(self, revision_id_or_record) -> list[dict]:
        revision = revision_id_or_record if isinstance(revision_id_or_record, dict) else self.get_revision(revision_id_or_record)
        if revision.get("status") == "MISSING_LINK":
            return [revision]
        ids = revision.get("triggering_evidence_ids") or []
        return [self.get_evidence(identifier) for identifier in ids] or [missing_link("evidence", None, "revision_has_no_evidence_ids")]

    def get_experiments_for_evidence(self, evidence_id_or_record) -> list[dict]:
        evidence = evidence_id_or_record if isinstance(evidence_id_or_record, dict) else self.get_evidence(evidence_id_or_record)
        if evidence.get("status") == "MISSING_LINK":
            return [evidence]
        ids = evidence.get("experiment_ids") or []
        return [self.get_experiment(identifier) for identifier in ids] or [missing_link("experiment", None, "evidence_has_no_experiment_ids")]

    def get_trigger_path(self, revision_id_or_record) -> dict:
        revision = revision_id_or_record if isinstance(revision_id_or_record, dict) else self.get_revision(revision_id_or_record)
        if revision.get("status") == "MISSING_LINK":
            return revision
        if not revision.get("revision_id"):
            return missing_link("revision_id", None, "historical_revision_has_no_revision_id")
        paths = []
        for evidence in self.get_evidence_for_revision(revision):
            if evidence.get("status") == "MISSING_LINK":
                return evidence
            experiments = self.get_experiments_for_evidence(evidence)
            if any(row.get("status") == "MISSING_LINK" for row in experiments):
                return next(row for row in experiments if row.get("status") == "MISSING_LINK")
            paths.append({
                "experiment_ids": [row["experiment_id"] for row in experiments],
                "evidence_id": evidence["evidence_id"],
                "decision": evidence.get("decision"),
                "revision_id": revision["revision_id"],
                "new_hypothesis_id": revision.get("new_hypothesis_id"),
            })
        return {"status": "COMPLETE", "paths": paths}

    def summary(self) -> dict:
        missing_revision_ids = sum(not row.get("revision_id") for row in self.records["revisions"])
        return {
            "node_counts": {name: len(rows) for name, rows in self.records.items()},
            "historical_revisions_without_revision_id": missing_revision_ids,
        }
