"""Q-Explorer V0.3 multi-task scientific exploration layer."""

from .tasks import ResearchTask, TaskSuite, TaskValidationError
from .validation import ValidatedJudgment, evaluate_validated_judgment
from .actions import HypothesisProposal, V03Action
from .diagnostics import diagnose_scientific_failure_modes
from .checkpoint import TaskCheckpoint
from .runner import PlannedCondition, V03TaskRunner, plan_conditions, select_rule_based_condition
from .live_runner import LiveTaskRunner

__all__ = [
    "HypothesisProposal", "ResearchTask", "TaskCheckpoint", "TaskSuite",
    "TaskValidationError", "V03Action", "ValidatedJudgment",
    "LiveTaskRunner", "PlannedCondition", "V03TaskRunner", "plan_conditions",
    "select_rule_based_condition",
    "diagnose_scientific_failure_modes", "evaluate_validated_judgment",
]
