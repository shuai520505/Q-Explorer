"""Counterfactual SUPPORT-vs-COUNTEREXAMPLE sensitivity evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research import Observation, ResearchState, RuleBasedResearchAgent


def synthetic_state(decision: str) -> ResearchState:
    return ResearchState(
        round=1,
        current_hypotheses=({"hypothesis_id": "H001", "claim": "For fixed Hamiltonian and depth, ring has lower error.", "status": "PENDING"},),
        hypothesis_status={"H001": "PENDING"}, supporting_experiments={"H001": ()}, counterexamples={"H001": ()}, recent_experiments=(),
        tested_regions=({"hamiltonian_id": "HAM_BASE", "depth": 1, "entanglement": "linear", "set": "exploration"},),
        untested_regions=(
            {"hamiltonian_id": "HAM_NEW", "depth": 2, "entanglement": "ring", "set": "exploration", "seed_group": [1011, 1029]},
            {"hamiltonian_id": "HAM_BASE", "depth": 3, "entanglement": "ring", "set": "exploration", "seed_group": [1031, 1049]},
        ),
        remaining_budget=20, available_actions=(), hamiltonian_features={}, aggregate_statistics=(), previous_agent_actions=(),
        recent_evidence=({"evidence_id": "SYNTHETIC_EVIDENCE", "decision": decision, "rule": "counterfactual_fixture"},), held_out_ids=(),
    )


def main() -> int:
    agent = RuleBasedResearchAgent()
    support = agent.select_action(Observation.from_state(synthetic_state("SUPPORT")), "ACT_000001")
    counterexample = agent.select_action(Observation.from_state(synthetic_state("COUNTEREXAMPLE")), "ACT_000002")
    action_changed = support.action_type != counterexample.action_type or support.experiment.to_dict() != counterexample.experiment.to_dict()
    reasoning_changed = support.reason != counterexample.reason and support.information_goal != counterexample.information_goal
    passed = bool(action_changed and reasoning_changed)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": agent.name,
        "state_difference": "recent_evidence.decision only",
        "support_action": support.to_dict(),
        "counterexample_action": counterexample.to_dict(),
        "action_changed": action_changed,
        "reasoning_changed": reasoning_changed,
        "feedback_sensitivity": "PASS" if passed else "FAIL",
    }
    destination = ROOT / "results" / "v02" / "feedback_sensitivity.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
