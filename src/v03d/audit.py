"""Deterministic, strategy-agnostic scientific-validity audit rules."""

from __future__ import annotations

import json
import re
from collections import Counter

from .evidence_graph import EvidenceGraph


SCOPE_STATUSES = (
    "STRICTLY_SUPPORTED", "DETERMINISTICALLY_RECONSTRUCTABLE",
    "INDIRECTLY_SUPPORTED", "UNSUPPORTED_ATTRIBUTION",
)
QUALIFYING_SCOPE_DECISIONS = {"COUNTEREXAMPLE", "WEAKEN"}
DECISIVE = {"SUPPORT", "WEAKEN", "COUNTEREXAMPLE"}


def _complete_experiment_links(graph: EvidenceGraph, evidence: dict) -> bool:
    experiments = graph.get_experiments_for_evidence(evidence)
    return bool(experiments) and all(
        row.get("status") != "MISSING_LINK" and row.get("run_id") == evidence.get("run_id")
        for row in experiments
    )


def _scope_change_type(revision: dict) -> str:
    text = " ".join(str(revision.get(key, "")) for key in ("new_claim", "scope_change")).lower()
    if any(token in text for token in ("all nisq", "universal", "all systems", "broaden", "expand")):
        return "EXPANDED"
    if any(token in text for token in ("conditional", "only", "restrict", "narrow", "exclude", "within", "subset")):
        return "NARROWED"
    return "UNDETERMINED"


def _metadata_contradicts(revision: dict, evidence: dict) -> bool:
    text = " ".join(str(revision.get(key, "")) for key in ("revision_reason", "scope_change", "new_claim"))
    referenced = set(re.findall(r"(?:V\w+_EVID_\d+|EXP_\d+)", text))
    eligible = {str(evidence.get("evidence_id")), *(str(value) for value in evidence.get("experiment_ids", []))}
    return bool(referenced and not referenced <= eligible)


def audit_scope_revision(graph: EvidenceGraph, revision: dict, previous_revision_round: int = 0) -> dict:
    run_id, task_id = revision.get("run_id"), revision.get("task_id")
    round_no = int(revision.get("round", 0))
    parent = revision.get("parent_hypothesis_id")
    scope_type = _scope_change_type(revision)
    recorded_ids = list(revision.get("triggering_evidence_ids") or [])
    recorded_evidence = [graph.get_evidence(identifier) for identifier in recorded_ids]
    recorded_experiment_ids = [
        experiment_id
        for evidence in recorded_evidence if evidence.get("status") != "MISSING_LINK"
        for experiment_id in evidence.get("experiment_ids", [])
    ]

    def eligible(evidence: dict) -> bool:
        return all((
            evidence.get("status") != "MISSING_LINK",
            evidence.get("run_id") == run_id,
            evidence.get("task_id") == task_id,
            evidence.get("hypothesis_id") == parent,
            previous_revision_round < int(evidence.get("round", -1)) < round_no,
            evidence.get("decision") in QUALIFYING_SCOPE_DECISIONS,
            _complete_experiment_links(graph, evidence),
            not _metadata_contradicts(revision, evidence),
            scope_type == "NARROWED",
        ))

    explicit = [evidence for evidence in recorded_evidence if eligible(evidence)]
    candidates = [
        evidence for evidence in graph.records["evidence"]
        if eligible(evidence)
    ]
    if explicit:
        status, reconstructed = "STRICTLY_SUPPORTED", []
    elif len(candidates) == 1:
        status, reconstructed = "DETERMINISTICALLY_RECONSTRUCTABLE", candidates
    else:
        related = [
            evidence for evidence in graph.records["evidence"]
            if evidence.get("run_id") == run_id
            and evidence.get("task_id") == task_id
            and evidence.get("hypothesis_id") == parent
            and previous_revision_round < int(evidence.get("round", -1)) <= round_no
        ]
        status = "INDIRECTLY_SUPPORTED" if related or recorded_ids else "UNSUPPORTED_ATTRIBUTION"
        reconstructed = []
    selected = explicit or reconstructed
    locator = f"{revision.get('_source_path', '')}:{revision.get('_source_line', '')}"
    return {
        "run_id": run_id,
        "revision_id": revision.get("revision_id"),
        "revision_record_locator": locator,
        "parent_hypothesis_id": parent,
        "child_hypothesis_id": revision.get("new_hypothesis_id"),
        "old_scope": revision.get("old_claim"),
        "new_scope": revision.get("new_claim"),
        "triggering_evidence_ids_recorded": json.dumps(recorded_ids),
        "triggering_experiment_ids_recorded": json.dumps(recorded_experiment_ids),
        "evidence_link_complete": bool(explicit),
        "counterexample_label_present": any(row.get("decision") == "COUNTEREXAMPLE" for row in recorded_evidence),
        "counterexample_experiment_present": any(_complete_experiment_links(graph, row) for row in recorded_evidence if row.get("decision") == "COUNTEREXAMPLE"),
        "revision_reason": revision.get("revision_reason"),
        "revision_timestamp": revision.get("timestamp"),
        "can_reconstruct_from_existing_trace": status == "DETERMINISTICALLY_RECONSTRUCTABLE",
        "reconstructed_evidence_ids": json.dumps([row["evidence_id"] for row in selected]),
        "reconstructed_experiment_ids": json.dumps([value for row in selected for value in row.get("experiment_ids", [])]),
        "eligible_candidate_count": len(candidates),
        "scope_change_type": scope_type,
        "evidence_attribution_score": {"STRICTLY_SUPPORTED": 3, "DETERMINISTICALLY_RECONSTRUCTABLE": 2, "INDIRECTLY_SUPPORTED": 1, "UNSUPPORTED_ATTRIBUTION": 0}[status],
        "audit_status": status,
    }


def classify_scope_run(run: dict, revision_audits: list[dict]) -> str:
    if run.get("final_judgment") == "INVALID_ACTION":
        return "INVALID_RUN"
    if not (run.get("validated_judgment") or {}).get("validated"):
        return "NOT_VALIDATED"
    statuses = {row["audit_status"] for row in revision_audits}
    if "STRICTLY_SUPPORTED" in statuses:
        return "VALIDATED_WITH_STRICT_REVISION"
    if "DETERMINISTICALLY_RECONSTRUCTABLE" in statuses:
        return "VALIDATED_WITH_RECONSTRUCTED_REVISION"
    if "INDIRECTLY_SUPPORTED" in statuses:
        return "VALIDATED_WITH_INDIRECT_REVISION"
    return "VALIDATED_WITH_UNATTRIBUTED_REVISION"


def _condition_differences(left: dict, right: dict) -> list[str]:
    differences = []
    if left.get("ham_seed") != right.get("ham_seed") or left.get("topology") != right.get("topology"):
        differences.append("hamiltonian_topology")
    for key in ("num_qubits", "depth", "entanglement"):
        if left.get(key) != right.get(key):
            differences.append(key)
    return differences


def _explanation_side(decision: str | None) -> str | None:
    if decision == "SUPPORT":
        return "H_A"
    if decision in {"WEAKEN", "COUNTEREXAMPLE"}:
        return "H_B"
    return None


def audit_competing_run(graph: EvidenceGraph, run: dict, task) -> dict:
    run_id = run["run_id"]
    actions = sorted((row for row in graph.records["actions"] if row.get("run_id") == run_id), key=lambda row: int(row.get("round", 0)))
    evidence_by_action = {row.get("action_id"): row for row in graph.records["evidence"] if row.get("run_id") == run_id}
    experiments = [row for row in graph.records["experiments"] if row.get("run_id") == run_id]
    successful_by_action = Counter(row.get("action_id") for row in experiments if row.get("status") == "SUCCESS")
    conditions = {row["condition_id"]: row for row in task.experiment_pool}
    text = " ".join(
        str(action.get(key, ""))
        for action in actions
        for key in ("reason", "information_goal", "expected_outcome", "falsification_condition")
    ).lower()
    identified = ("connectivity" in text and "depth" in text) or ("hd_a" in text and "hd_b" in text)
    attempted = any(action.get("action_type") == "CONTROL_DEPTH" for action in actions)
    valid_controls = []
    multi_changes = []
    for index, action in enumerate(actions):
        reported = list(action.get("changed_variables") or [])
        if len(reported) > 1:
            multi_changes.append({"action_id": action.get("action_id"), "variables": reported})
        if action.get("action_type") != "CONTROL_DEPTH" or successful_by_action[action.get("action_id")] < 1:
            continue
        current = conditions.get(action.get("condition_id"))
        previous = next((
            prior for prior in reversed(actions[:index])
            if prior.get("condition_id") != action.get("condition_id")
            and successful_by_action[prior.get("action_id")] > 0
        ), None)
        prior_condition = conditions.get(previous.get("condition_id")) if previous else None
        linked_evidence = evidence_by_action.get(action.get("action_id"))
        if not current or not prior_condition or not linked_evidence:
            continue
        differences = _condition_differences(prior_condition, current)
        reason_codes = set(linked_evidence.get("reason_codes") or [])
        if (
            differences == ["depth"]
            and linked_evidence.get("decision") in DECISIVE
            and bool(reason_codes & {"CONTROL_SUPPORTS_H_A", "CONTROL_SUPPORTS_H_B"})
            and _complete_experiment_links(graph, linked_evidence)
        ):
            valid_controls.append({
                "action_id": action["action_id"], "control_action_id": previous["action_id"],
                "evidence_id": linked_evidence["evidence_id"], "decision": linked_evidence["decision"],
                "experiment_ids": linked_evidence.get("experiment_ids", []), "changed_variables_inferred": differences,
            })
    original_validated = bool((run.get("validated_judgment") or {}).get("validated"))
    held_out = [row for row in graph.records["evidence"] if row.get("run_id") == run_id and row.get("held_out")]
    held_out_validated = original_validated and bool(held_out)
    final_side = _explanation_side(run.get("final_judgment"))
    control_sides = {_explanation_side(row["decision"]) for row in valid_controls}
    judgment_consistent = bool(final_side and final_side in control_sides)
    design_valid = bool(identified and valid_controls and judgment_consistent)
    scientific_validated = bool(original_validated and design_valid)
    reasons = []
    if not identified:
        reasons.append("FAILED_TO_IDENTIFY_COMPETING_EXPLANATIONS")
    if not attempted:
        reasons.append("NO_VALID_SINGLE_VARIABLE_CONTROL")
    elif not valid_controls:
        reasons.extend(("FAILED_TO_CONTROL_CONFOUND", "NON_DISCRIMINATIVE_EXPERIMENT", "NO_VALID_SINGLE_VARIABLE_CONTROL"))
    if multi_changes:
        reasons.append("MULTI_VARIABLE_CHANGE")
    if run.get("final_judgment") == "INVALID_ACTION":
        reasons.append("INVALID_ACTION")
    if int(run.get("budget_spent", 0)) >= int(run.get("budget", 0)) and not scientific_validated:
        reasons.append("BUDGET_EXHAUSTED")
    for action in actions:
        reasons.extend(mode for mode in action.get("failure_modes", []) if mode in {"PREMATURE_CONCLUSION", "COUNTEREXAMPLE_IGNORED", "EXCESSIVE_REPLICATION"})
    if original_validated and not design_valid:
        reasons.append("OUTCOME_RIGHT_FOR_WRONG_EXPERIMENTAL_REASON")
    if valid_controls and judgment_consistent:
        control_score = 3
    elif valid_controls:
        control_score = 2
    elif attempted:
        control_score = 1
    else:
        control_score = 0
    if run.get("final_judgment") == "INVALID_ACTION":
        status = "INVALID_RUN"
    elif scientific_validated:
        status = "SCIENTIFICALLY_VALIDATED"
    elif original_validated:
        status = "OUTCOME_VALIDATED_BUT_DESIGN_INVALID"
    else:
        status = "NOT_VALIDATED"
    return {
        "run_id": run_id, "strategy": run.get("strategy"), "validated_original": original_validated,
        "num_actions": len(actions), "num_experiments": len(experiments),
        "competing_hypotheses_identified": identified,
        "single_variable_control_attempted": attempted,
        "single_variable_control_executed": bool(valid_controls),
        "multi_variable_change_count": len(multi_changes),
        "multi_variable_change_ratio": len(multi_changes) / max(len(actions), 1),
        "multi_variable_changes": json.dumps(multi_changes, sort_keys=True),
        "confound_control_valid": bool(valid_controls),
        "discriminative_experiment_count": len(valid_controls),
        "discriminative_experiment_ratio": len(valid_controls) / max(len(actions), 1),
        "valid_control_chains": json.dumps(valid_controls, sort_keys=True),
        "held_out_validated": held_out_validated,
        "final_judgment_consistent_with_control": judgment_consistent,
        "scientific_control_score": control_score,
        "scientific_design_valid": design_valid,
        "scientifically_validated": scientific_validated,
        "audit_status": status,
        "failure_reason": "|".join(sorted(set(reasons))),
    }


def audit_boundary_run(graph: EvidenceGraph, run: dict) -> dict:
    run_id = run["run_id"]
    actions = [row for row in graph.records["actions"] if row.get("run_id") == run_id]
    probes = [row for row in actions if row.get("action_type") == "BOUNDARY_PROBE"]
    evidence_by_action = {row.get("action_id"): row for row in graph.records["evidence"] if row.get("run_id") == run_id}
    experiments_by_action: dict[str, list[dict]] = {}
    for row in graph.records["experiments"]:
        if row.get("run_id") == run_id:
            experiments_by_action.setdefault(row.get("action_id"), []).append(row)
    complete_probes = [
        action for action in probes
        if action.get("action_id") in evidence_by_action
        and experiments_by_action.get(action.get("action_id"))
        and _complete_experiment_links(graph, evidence_by_action[action["action_id"]])
    ]
    held_out = [row for row in evidence_by_action.values() if row.get("held_out") and _complete_experiment_links(graph, row)]
    validated = bool((run.get("validated_judgment") or {}).get("validated"))
    complete = bool(not validated or (complete_probes and held_out))
    return {
        "run_id": run_id, "validated_original": validated,
        "adaptive_probe_action_ids": json.dumps([row["action_id"] for row in probes]),
        "complete_probe_action_ids": json.dumps([row["action_id"] for row in complete_probes]),
        "probe_evidence_ids": json.dumps([evidence_by_action[row["action_id"]]["evidence_id"] for row in complete_probes]),
        "held_out_evidence_ids": json.dumps([row["evidence_id"] for row in held_out]),
        "revision_count": len(graph.revisions_for_run(run_id)),
        "evidence_chain_complete": complete,
        "audit_status": "PASS" if complete else "MISSING_LINK",
    }
