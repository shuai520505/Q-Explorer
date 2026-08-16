"""Perform one credential-safe live LLM health check without using VQE budget."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research import OpenAICompatibleProvider, redact_sensitive_text


def main() -> int:
    output = ROOT / "results" / "v03" / "live_llm_healthcheck.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    required = {name: bool(os.environ.get(name)) for name in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")}
    provider_name = os.environ.get("LLM_PROVIDER") or "NOT_SET"
    model = os.environ.get("LLM_MODEL") or "NOT_SET"
    result = {
        "provider": provider_name, "model": model, "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": False, "api_auth": "NOT_TESTED", "model_available": "NOT_TESTED",
        "response_received": False, "latency_seconds": None, "response_format_valid": False,
        "thinking_mode_requested": True, "thinking_mode_observed": False,
        "required_environment_variables": {name: "SET" if value else "NOT_SET" for name, value in required.items()},
    }
    if not all(required.values()):
        result["error"] = "REQUIRED_ENVIRONMENT_VARIABLE_NOT_SET"
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("LLM_API_KEY=" + result["required_environment_variables"]["LLM_API_KEY"])
        return 2
    try:
        llm = OpenAICompatibleProvider(max_tokens=128, timeout=60, retry=0, thinking_mode=True, reasoning_effort="high")
        response = llm.generate(
            "Return JSON only. This is an API health check, not scientific evidence.",
            {"instruction": "Return exactly {\"status\":\"OK\"}."},
            0.0,
        )
        parsed = json.loads(response.text)
        valid = parsed == {"status": "OK"}
        result.update({
            "success": valid, "api_auth": "PASS", "model_available": "PASS",
            "response_received": True, "latency_seconds": response.latency_seconds,
            "response_format_valid": valid, "thinking_mode_observed": response.reasoning_content_present,
            "request_id": response.request_id, "response_hash": __import__("hashlib").sha256(response.text.encode()).hexdigest(),
            "usage": response.usage,
        })
    except Exception as exc:
        safe = redact_sensitive_text(str(exc), [os.environ.get("LLM_API_KEY", "")])
        result["error"] = safe[:1000]
        if "401" in safe or "403" in safe:
            result["api_auth"] = "FAIL"
        elif "model" in safe.lower() or "404" in safe:
            result["api_auth"], result["model_available"] = "PASS", "FAIL"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("LLM_API_KEY=SET")
    print(f"API_AUTH={result['api_auth']}")
    print(f"MODEL_AVAILABLE={result['model_available']}")
    print(f"RESPONSE_RECEIVED={'PASS' if result['response_received'] else 'FAIL'}")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
