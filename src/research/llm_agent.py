"""Validated LLM Research Agent with one repair and explicit INVALID_ACTION."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.research.agents import AgentResponse, ResearchAgent
from src.research.models import ActionValidationError, Observation, ResearchAction
from src.research.provider import LLMProvider


class LLMResearchAgent(ResearchAgent):
    name = "llm"

    def __init__(self, provider: LLMProvider, prompt_path: str | Path, prompt_version: str, temperature: float = 0.1, max_repair_attempts: int = 1, require_v03_fields: bool = False) -> None:
        self.provider = provider
        self.prompt_path = Path(prompt_path)
        self.system_prompt = self.prompt_path.read_text(encoding="utf-8")
        self.prompt_version = prompt_version
        self.temperature = float(temperature)
        self.max_repair_attempts = int(max_repair_attempts)
        self.require_v03_fields = bool(require_v03_fields)
        marker = f"prompt version: {prompt_version}"
        if marker not in self.system_prompt:
            raise ValueError("Prompt file version marker does not match configured prompt_version")
        self.last_response: AgentResponse | None = None

    def select_action(self, observation: Observation, action_id: str) -> ResearchAction:
        result = self.request_action(observation, action_id)
        if result.action is None:
            raise ActionValidationError(result.error or "INVALID_ACTION")
        return result.action

    def request_action(self, observation: Observation, action_id: str, action_validator=None) -> AgentResponse:
        payload = {
            "prompt_version": self.prompt_version,
            "observation": observation.to_dict(),
            "required_action_id": action_id,
            "required_round": observation.round,
            "instruction": (
                "Return exactly one JSON object with the ResearchAction fields action_id, round, hypothesis_id, "
                "action_type, reason, experiment, controlled_variables, changed_variables, expected_outcome, "
                "falsification_condition, information_goal, revision_proposal; plus confidence in [0,1] and "
                "hypothesis_proposal (null unless action_type is PROPOSE_HYPOTHESIS). Use only an experiment "
                "listed in observation.untested_conditions and exactly its offered seed_group."
            ),
        }
        repair_attempted = False
        last_text = ""
        last_request_id = None
        last_error = None
        for attempt in range(self.max_repair_attempts + 1):
            if attempt:
                repair_attempted = True
                payload = payload | {"repair": {"invalid_output": last_text, "validation_error": last_error}}
            response = self.provider.generate(self.system_prompt, payload, self.temperature)
            last_text, last_request_id = response.text, response.request_id
            try:
                parsed = _parse_json_object(last_text)
                confidence = parsed.pop("confidence", None)
                proposal = parsed.pop("hypothesis_proposal", None)
                if self.require_v03_fields and confidence is None:
                    raise ActionValidationError("confidence is required for V0.3")
                if confidence is not None and (not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0):
                    raise ActionValidationError("confidence must be in [0,1]")
                if proposal is not None:
                    _validate_hypothesis_proposal(proposal)
                    if parsed.get("action_type") != "PROPOSE_HYPOTHESIS":
                        raise ActionValidationError("hypothesis_proposal requires PROPOSE_HYPOTHESIS")
                parsed["action_id"] = action_id
                parsed["round"] = observation.round
                action = ResearchAction.from_dict(parsed)
                if action_validator is not None:
                    action_validator(action)
                result = AgentResponse(
                    action, "VALID", _sha(last_text), last_request_id, repair_attempted, None,
                    raw_response=last_text, model=response.model, usage=response.usage,
                    latency_seconds=response.latency_seconds,
                    reasoning_content_present=response.reasoning_content_present,
                    reasoning_content_hash=response.reasoning_content_hash,
                    confidence=None if confidence is None else float(confidence), hypothesis_proposal=proposal,
                )
                self.last_response = result
                return result
            except (json.JSONDecodeError, ActionValidationError, TypeError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        result = AgentResponse(
            None, "INVALID_ACTION", _sha(last_text), last_request_id, repair_attempted, last_error,
            raw_response=last_text, model=response.model if 'response' in locals() else None,
            usage=response.usage if 'response' in locals() else None,
            latency_seconds=response.latency_seconds if 'response' in locals() else None,
            reasoning_content_present=response.reasoning_content_present if 'response' in locals() else False,
            reasoning_content_hash=response.reasoning_content_hash if 'response' in locals() else None,
        )
        self.last_response = result
        return result


def _parse_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1])
            if stripped.lstrip().startswith("json"):
                stripped = stripped.lstrip()[4:].lstrip()
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise TypeError("LLM response must be a JSON object")
    return payload


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_hypothesis_proposal(payload: dict) -> None:
    expected = {"claim", "scope", "expected_observation", "falsification_condition", "alternative_explanations"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ActionValidationError("hypothesis_proposal fields mismatch")
    if not isinstance(payload["scope"], dict) or not payload["scope"]:
        raise ActionValidationError("hypothesis_proposal.scope must be a non-empty object")
    if not isinstance(payload["alternative_explanations"], list) or not payload["alternative_explanations"]:
        raise ActionValidationError("hypothesis_proposal.alternative_explanations must be a non-empty array")
    for key in ("claim", "expected_observation", "falsification_condition"):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise ActionValidationError(f"hypothesis_proposal.{key} must be non-empty")
