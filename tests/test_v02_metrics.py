from src.research import compute_run_metrics


def test_four_metrics_are_transparent_and_budget_based():
    run = {"run_id": "R", "strategy": "active_agent", "strategy_category": "active_agent", "budget": 6, "budget_spent": 6, "rounds_completed": 3, "optimization_drift": False, "invalid_actions": 0}
    actions = [
        {"run_id": "R", "round": i, "action_id": f"A{i}", "action_type": "CONTROL_ENTANGLEMENT", "validation_status": "VALID", "budget_cost": 2, "responding_to_evidence_label": label, "experiment": {"hamiltonian_id": "HAM_A", "depth": 1, "entanglement": ent}}
        for i, label, ent in [(1, "INCONCLUSIVE", "ring"), (2, "INCONCLUSIVE", "linear"), (3, "COUNTEREXAMPLE", "linear")]
    ]
    evidence = [{"run_id": "R", "round": 2, "decision": "COUNTEREXAMPLE", "held_out": False}]
    experiments = [{"run_id": "R", "status": "SUCCESS"} for _ in range(6)]
    metrics = compute_run_metrics(run, actions, experiments, evidence, adequate_replication=2)
    assert metrics["experiments_to_stable_judgment"] == 4
    assert metrics["counterexample_discovery"] is True
    assert metrics["redundant_experiment_ratio"] == 1 / 3
    assert metrics["held_out_replication"] == "NOT_COMPLETED"

