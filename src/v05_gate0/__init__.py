"""Q-Explorer V0.5 Gate 0 hardware capability audit layer."""

from .adapter import HardwareBackendInterface, MobileCloudHardwareAdapter
from .audit import (
    build_candidate_requirements,
    build_compatibility_rows,
    build_hardware_a_protocol,
    estimate_hardware_b_cost,
    measurement_decomposition,
)
from .guard import HardwareExecutionForbidden, HardwareExecutionGuard
from .models import CalibrationSnapshot, HardwareDevice, redact_secrets
from .transpilation import audit_candidate_transpilation

__all__ = [
    "CalibrationSnapshot",
    "HardwareBackendInterface",
    "HardwareDevice",
    "HardwareExecutionForbidden",
    "HardwareExecutionGuard",
    "MobileCloudHardwareAdapter",
    "audit_candidate_transpilation",
    "build_candidate_requirements",
    "build_compatibility_rows",
    "build_hardware_a_protocol",
    "estimate_hardware_b_cost",
    "measurement_decomposition",
    "redact_secrets",
]
