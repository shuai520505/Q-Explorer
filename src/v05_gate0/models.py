"""Serializable, provider-neutral Gate 0 hardware schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


UNKNOWN = "UNKNOWN"
_SECRET_MARKERS = ("api_key", "secret", "password", "access_key", "private_key", "token")


def redact_secrets(value: Any) -> Any:
    """Recursively redact credential-shaped fields without hiding ordinary metadata."""

    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if any(marker in key.lower() for marker in _SECRET_MARKERS) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


@dataclass(frozen=True)
class HardwareDevice:
    device_id: str
    device_name: str
    hardware_type: str = UNKNOWN
    real_hardware_or_simulator: str = UNKNOWN
    num_qubits: int | str = UNKNOWN
    status: str = UNKNOWN
    queue_state: Any = UNKNOWN
    native_gate_set: Any = UNKNOWN
    connectivity: Any = UNKNOWN
    supports_parameterized_circuit: bool | str = UNKNOWN
    supports_batch_submission: bool | str = UNKNOWN
    supports_multiple_circuits_per_job: bool | str = UNKNOWN
    supports_observable_expectation: bool | str = UNKNOWN
    supports_raw_counts: bool | str = UNKNOWN
    supports_shots: bool | str = UNKNOWN
    max_shots: int | str = UNKNOWN
    max_circuit_depth: int | str = UNKNOWN
    max_gate_count: int | str = UNKNOWN
    max_circuits_per_job: int | str = UNKNOWN
    max_jobs_or_quota: Any = UNKNOWN
    calibration_available: bool | str = UNKNOWN
    gate_error_available: bool | str = UNKNOWN
    readout_error_available: bool | str = UNKNOWN
    t1_t2_available: bool | str = UNKNOWN
    last_calibration_time: str = UNKNOWN
    suitability: str = UNKNOWN

    def __post_init__(self) -> None:
        if not self.device_id or not self.device_name:
            raise ValueError("device_id and device_name are required")
        if isinstance(self.num_qubits, int) and self.num_qubits < 1:
            raise ValueError("num_qubits must be positive or UNKNOWN")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationSnapshot:
    device_id: str
    captured_at: str
    provider_calibration_timestamp: str = UNKNOWN
    one_qubit_errors: Any = UNKNOWN
    two_qubit_errors: Any = UNKNOWN
    readout_errors: Any = UNKNOWN
    t1: Any = UNKNOWN
    t2: Any = UNKNOWN
    source: str = "PROVIDER_API"
    availability: str = UNKNOWN

    def to_dict(self) -> dict:
        return asdict(self)
