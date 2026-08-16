import pytest

from src.v05_gate0 import HardwareExecutionForbidden, MobileCloudHardwareAdapter


def test_v05_no_formal_job_submission_reaches_provider_client():
    called = {"submit": False}

    class Client:
        def submit_job(self, *_args, **_kwargs):
            called["submit"] = True

    adapter = MobileCloudHardwareAdapter(
        environ={"MOBILE_QUANTUM_ACCESS_KEY": "present", "MOBILE_QUANTUM_SECRET_KEY": "present"},
        client_factory=lambda *_args: Client(),
    )
    with pytest.raises(HardwareExecutionForbidden):
        adapter.submit_job({"circuits": 1})
    assert called["submit"] is False
