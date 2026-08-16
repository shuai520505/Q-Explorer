"""Transparent scientific-policy failure diagnostics."""

from __future__ import annotations


FAILURE_MODES = frozenset({
    "OPTIMIZATION_DRIFT", "RANDOM_SEARCH_DEGENERATION", "COUNTEREXAMPLE_IGNORED",
    "PREMATURE_CONCLUSION", "EXCESSIVE_REPLICATION", "FAILED_TO_CONTROL_CONFOUND",
    "FAILED_TO_DISCRIMINATE", "HYPOTHESIS_SCOPE_CREEP",
})


def diagnose_scientific_failure_modes(action: dict, recent_evidence: list[dict], task, prior_actions: list[dict]) -> list[str]:
    modes = []
    text = " ".join(str(action.get(key, "")) for key in ("reason", "information_goal", "expected_outcome")).lower()
    if any(term in text for term in ("lowest energy", "best circuit", "minimize energy")):
        modes.append("OPTIMIZATION_DRIFT")
    if recent_evidence and recent_evidence[-1].get("decision") == "COUNTEREXAMPLE" and action.get("action_type") not in {
        "REVISE_HYPOTHESIS", "SEARCH_COUNTEREXAMPLE", "CONTROL_DEPTH", "CONTROL_ENTANGLEMENT", "ABANDON_HYPOTHESIS",
    }:
        modes.append("COUNTEREXAMPLE_IGNORED")
    if action.get("claimed_status") == "SUPPORTED":
        modes.append("PREMATURE_CONCLUSION")
    if task.competing_hypotheses and action.get("action_type") not in {"CONTROL_DEPTH", "CONTROL_ENTANGLEMENT"} and len(prior_actions) >= 2:
        modes.append("FAILED_TO_DISCRIMINATE")
    proposal = action.get("hypothesis_proposal") or action.get("revision_proposal") or {}
    scope = proposal.get("scope", {}) if isinstance(proposal, dict) else {}
    supported_qubits = {item.get("num_qubits") for item in task.experiment_pool}
    if scope.get("num_qubits") and not set(scope["num_qubits"]) <= supported_qubits:
        modes.append("HYPOTHESIS_SCOPE_CREEP")
    experiment = action.get("experiment") or {}
    key = (experiment.get("hamiltonian_id"), experiment.get("depth"), experiment.get("entanglement"))
    repetitions = sum(
        (prior.get("experiment") or {}).get("hamiltonian_id") == key[0]
        and (prior.get("experiment") or {}).get("depth") == key[1]
        and (prior.get("experiment") or {}).get("entanglement") == key[2]
        for prior in prior_actions
    )
    if repetitions >= 2 and action.get("action_type") != "REPLICATE":
        modes.append("EXCESSIVE_REPLICATION")
    return modes

