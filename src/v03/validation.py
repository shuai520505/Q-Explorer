"""Task-specific validated judgment beyond the first status transition."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ValidatedJudgment:
    validated: bool
    experiments_to_validated_judgment: int | None
    final_decision: str
    independent_instances: int
    minimum_replication_met: bool
    control_met: bool
    held_out_met: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_validated_judgment(task, evidence: list[dict], actions: list[dict], experiments: list[dict]) -> ValidatedJudgment:
    criteria = task.success_criteria
    paired = [item for item in evidence if "INSUFFICIENT_REPLICATION" not in item.get("reason_codes", [])]
    instances = {item.get("comparison", {}).get("hamiltonian_id") for item in paired if item.get("comparison")}
    counts = {}
    for record in experiments:
        key = (record.get("hamiltonian_id"), record.get("depth"), record.get("entanglement"))
        counts[key] = counts.get(key, 0) + int(record.get("status") == "SUCCESS")
    replication_met = any(value >= int(criteria["minimum_seeds_per_condition"]) for value in counts.values())
    control_met = (not criteria["control_required"]) or any(
        item.get("action_type") in {"CONTROL_DEPTH", "CONTROL_ENTANGLEMENT"} for item in actions
    )
    held_out_evidence = [item for item in paired if item.get("held_out")]
    held_out_met = (not criteria["held_out_required"]) or bool(held_out_evidence)
    instance_met = len(instances) >= int(criteria["minimum_independent_instances"])
    decisive = [item for item in paired if item.get("decision") in {"SUPPORT", "COUNTEREXAMPLE", "WEAKEN"}]
    validated = bool(decisive and instance_met and replication_met and control_met and held_out_met)
    cost = None
    if validated:
        last_round = max(int(item.get("round", 0)) for item in decisive + held_out_evidence)
        cost = sum(int(item.get("budget_cost", 0)) for item in actions if int(item.get("round", 0)) <= last_round)
    codes = []
    if not instance_met: codes.append("INSUFFICIENT_INDEPENDENT_INSTANCES")
    if not replication_met: codes.append("INSUFFICIENT_REPLICATION")
    if not control_met: codes.append("REQUIRED_CONTROL_MISSING")
    if not held_out_met: codes.append("HELD_OUT_VALIDATION_MISSING")
    if validated: codes.append("VALIDATED_JUDGMENT_CRITERIA_MET")
    final = decisive[-1]["decision"] if decisive else "INCONCLUSIVE"
    return ValidatedJudgment(validated, cost, final, len(instances), replication_met, control_met, held_out_met, tuple(codes))

