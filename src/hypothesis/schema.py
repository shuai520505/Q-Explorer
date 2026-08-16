"""Minimal non-LLM hypothesis schema used by the V0.1 closed loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


ALLOWED_STATUSES = {
    "PENDING",
    "PRELIMINARY_SUPPORT",
    "SUPPORTED",
    "NARROWED",
    "INCONCLUSIVE",
    "REJECTED",
}


@dataclass
class Hypothesis:
    hypothesis_id: str
    claim: str
    status: str = "PENDING"
    supporting_experiments: list[str] = field(default_factory=list)
    counterexamples: list[str] = field(default_factory=list)
    revision_history: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid hypothesis status: {self.status}")

    def to_dict(self) -> dict:
        return asdict(self)


def update_hypothesis(hypothesis: Hypothesis, evidence: dict, experiment_ids: list[str]) -> Hypothesis:
    """Apply a conservative V0.1 status mapping to one real evidence record."""

    decision = evidence["decision"]
    status_mapping = {
        "SUPPORT": "PRELIMINARY_SUPPORT",
        "WEAKEN": "INCONCLUSIVE",
        "INCONCLUSIVE": "INCONCLUSIVE",
        "COUNTEREXAMPLE": "NARROWED",
    }
    if decision not in status_mapping:
        raise ValueError(f"Unsupported evidence decision: {decision}")
    previous = hypothesis.status
    hypothesis.status = status_mapping[decision]
    if decision == "SUPPORT":
        hypothesis.supporting_experiments.extend(identifier for identifier in experiment_ids if identifier not in hypothesis.supporting_experiments)
    elif decision == "COUNTEREXAMPLE":
        hypothesis.counterexamples.extend(identifier for identifier in experiment_ids if identifier not in hypothesis.counterexamples)
    hypothesis.revision_history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_status": previous,
            "to_status": hypothesis.status,
            "evidence_id": evidence.get("evidence_id"),
            "decision": decision,
        }
    )
    return hypothesis

