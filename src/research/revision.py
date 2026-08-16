"""Immutable hypothesis lineage: revisions append children and never overwrite parents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re


@dataclass(frozen=True)
class HypothesisRevision:
    parent_hypothesis_id: str
    new_hypothesis_id: str
    old_claim: str
    new_claim: str
    revision_reason: str
    triggering_evidence_ids: tuple[str, ...]
    scope_change: str
    timestamp: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["triggering_evidence_ids"] = list(self.triggering_evidence_ids)
        return payload


def revise_hypothesis(
    parent: dict,
    new_claim: str,
    revision_reason: str,
    triggering_evidence_ids: list[str],
    scope_change: str,
    existing_ids: set[str],
) -> tuple[dict, HypothesisRevision]:
    parent_id = parent["hypothesis_id"]
    revision_numbers = []
    pattern = re.compile(rf"^{re.escape(parent_id)}\.R(\d+)$")
    for identifier in existing_ids:
        match = pattern.fullmatch(identifier)
        if match:
            revision_numbers.append(int(match.group(1)))
    child_id = f"{parent_id}.R{max(revision_numbers, default=0) + 1}"
    timestamp = datetime.now(timezone.utc).isoformat()
    revision = HypothesisRevision(
        parent_hypothesis_id=parent_id,
        new_hypothesis_id=child_id,
        old_claim=parent["claim"],
        new_claim=new_claim,
        revision_reason=revision_reason,
        triggering_evidence_ids=tuple(triggering_evidence_ids),
        scope_change=scope_change,
        timestamp=timestamp,
    )
    child = {
        "hypothesis_id": child_id,
        "parent_hypothesis_id": parent_id,
        "claim": new_claim,
        "status": "PENDING",
        "supporting_experiments": [],
        "counterexamples": [],
        "revision_history": [revision.to_dict()],
    }
    return child, revision

