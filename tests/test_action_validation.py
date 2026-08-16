import pytest

from src.research import ActionValidationError, ResearchAction
from tests.test_action_schema import valid_payload


def test_extra_fields_are_rejected_instead_of_silently_ignored():
    payload = valid_payload() | {"developer_fallback": True}
    with pytest.raises(ActionValidationError, match="extra"):
        ResearchAction.from_dict(payload)


def test_invalid_seed_group_is_rejected():
    payload = valid_payload()
    payload["experiment"] = payload["experiment"] | {"seed_group": [1, 1]}
    with pytest.raises(ActionValidationError, match="duplicates"):
        ResearchAction.from_dict(payload)

