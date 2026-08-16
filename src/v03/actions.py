"""V0.3 action extension for hypothesis proposal and confidence auditing."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.research.models import ResearchAction


@dataclass(frozen=True)
class HypothesisProposal:
    claim: str
    scope: dict
    expected_observation: str
    falsification_condition: str
    alternative_explanations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claim.strip() or not self.expected_observation.strip() or not self.falsification_condition.strip():
            raise ValueError("Hypothesis proposal text fields cannot be empty")
        if not self.scope or not self.alternative_explanations:
            raise ValueError("Hypothesis proposal requires explicit scope and alternatives")

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["alternative_explanations"] = list(self.alternative_explanations)
        return payload


@dataclass(frozen=True)
class V03Action:
    action: ResearchAction
    confidence: float
    hypothesis_proposal: HypothesisProposal | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.hypothesis_proposal is not None and self.action.action_type != "PROPOSE_HYPOTHESIS":
            raise ValueError("hypothesis_proposal requires PROPOSE_HYPOTHESIS")

    def to_dict(self) -> dict:
        return self.action.to_dict() | {
            "confidence": self.confidence,
            "hypothesis_proposal": None if self.hypothesis_proposal is None else self.hypothesis_proposal.to_dict(),
        }

