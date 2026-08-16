from src.v03 import TaskSuite, evaluate_validated_judgment


def test_validated_judgment_requires_independent_heldout_evidence():
    task = TaskSuite("configs/frozen_v03_tasks.yaml").tasks[0]
    actions = [{"round": 1, "budget_cost": 2, "action_type": "CONTROL_ENTANGLEMENT"}, {"round": 2, "budget_cost": 2, "action_type": "VALIDATE_HYPOTHESIS"}]
    experiments = [{"hamiltonian_id": "A", "depth": 1, "entanglement": "linear", "status": "SUCCESS"} for _ in range(2)]
    evidence = [{"round": 1, "decision": "COUNTEREXAMPLE", "reason_codes": [], "held_out": False, "comparison": {"hamiltonian_id": "A"}}]
    assert not evaluate_validated_judgment(task, evidence, actions, experiments).validated
    evidence.append({"round": 2, "decision": "COUNTEREXAMPLE", "reason_codes": [], "held_out": True, "comparison": {"hamiltonian_id": "B"}})
    assert evaluate_validated_judgment(task, evidence, actions, experiments).validated

