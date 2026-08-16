"""Event-sourced active-science infrastructure for Q-Explorer V0.2."""

from .budget import BudgetExceeded, ExperimentBudget
from .agents import FixtureResearchAgent, ResearchAgent, RuleBasedResearchAgent
from .llm_agent import LLMResearchAgent
from .experiment import ActiveExperimentExecutor, judge_current_comparison
from .models import (
    ACTION_TYPES,
    ActionValidationError,
    ExperimentSpec,
    Observation,
    ResearchAction,
    ResearchState,
)
from .memory import ResearchMemory
from .metrics import aggregate_random_metrics, compute_run_metrics
from .provider import FixtureProvider, LLMProvider, OpenAICompatibleProvider, redact_sensitive_text
from .revision import HypothesisRevision, revise_hypothesis
from .run_context import FrozenConfig, RunIdentity, create_run_identity

__all__ = [
    "ACTION_TYPES",
    "ActionValidationError",
    "ActiveExperimentExecutor",
    "BudgetExceeded",
    "ExperimentBudget",
    "ExperimentSpec",
    "FixtureProvider",
    "FixtureResearchAgent",
    "FrozenConfig",
    "HypothesisRevision",
    "LLMProvider",
    "LLMResearchAgent",
    "Observation",
    "OpenAICompatibleProvider",
    "redact_sensitive_text",
    "ResearchAction",
    "ResearchAgent",
    "ResearchMemory",
    "ResearchState",
    "RunIdentity",
    "RuleBasedResearchAgent",
    "create_run_identity",
    "compute_run_metrics",
    "aggregate_random_metrics",
    "revise_hypothesis",
    "judge_current_comparison",
]
