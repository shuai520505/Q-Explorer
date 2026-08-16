"""Read-only China Mobile Cloud/WuYue adapter used by Gate 0."""

from __future__ import annotations

from abc import ABC, abstractmethod
import importlib.util
import os
from typing import Callable, Mapping

from .guard import HardwareExecutionGuard
from .models import HardwareDevice, UNKNOWN, redact_secrets


class HardwareBackendInterface(ABC):
    @abstractmethod
    def list_devices(self) -> list[HardwareDevice]: ...

    @abstractmethod
    def get_device_metadata(self, device_id: str) -> HardwareDevice | None: ...

    @abstractmethod
    def compile_or_transpile(self, circuit, device_id: str | None = None) -> dict: ...

    @abstractmethod
    def estimate_job(self, specification: Mapping) -> dict: ...

    @abstractmethod
    def prepare_job(self, specification: Mapping) -> dict: ...

    @abstractmethod
    def submit_job(self, specification: Mapping): ...


class MobileCloudHardwareAdapter(HardwareBackendInterface):
    """Provider-neutral audit adapter; submission is impossible by construction."""

    ACCESS_KEY_ENV = "MOBILE_QUANTUM_ACCESS_KEY"
    SECRET_KEY_ENV = "MOBILE_QUANTUM_SECRET_KEY"
    ENDPOINT_ENV = "MOBILE_QUANTUM_ENDPOINT"

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        client_factory: Callable[[str, str, str | None], object] | None = None,
        guard: HardwareExecutionGuard | None = None,
    ) -> None:
        self._environ = dict(os.environ if environ is None else environ)
        self._client_factory = client_factory
        self.guard = guard or HardwareExecutionGuard()
        self.guard.assert_audit_mode()
        self._client = None

    @property
    def credential_status(self) -> str:
        return "SET" if self._environ.get(self.ACCESS_KEY_ENV) and self._environ.get(self.SECRET_KEY_ENV) else "NOT_SET"

    @property
    def sdk_status(self) -> str:
        return "INSTALLED" if importlib.util.find_spec("wuyue") is not None else "NOT_INSTALLED"

    def capability_status(self) -> dict:
        return {
            "platform_name": "China Mobile Cloud WuYue Quantum Computing Cloud Platform",
            "sdk_name": "WuYueSDK",
            "sdk_installed_in_project_environment": self.sdk_status == "INSTALLED",
            "credential": self.credential_status,
            "execution_mode": self.guard.mode,
            "account_query_status": (
                "READY_FOR_READ_ONLY_QUERY" if self.credential_status == "SET" and (self._client_factory or self.sdk_status == "INSTALLED")
                else "NOT_QUERIED_CREDENTIAL_NOT_SET" if self.credential_status == "NOT_SET"
                else "NOT_QUERIED_SDK_NOT_INSTALLED"
            ),
        }

    def _get_client(self):
        if self.credential_status != "SET":
            return None
        if self._client is not None:
            return self._client
        if self._client_factory is None:
            return None
        self._client = self._client_factory(
            self._environ[self.ACCESS_KEY_ENV],
            self._environ[self.SECRET_KEY_ENV],
            self._environ.get(self.ENDPOINT_ENV),
        )
        return self._client

    def list_devices(self) -> list[HardwareDevice]:
        client = self._get_client()
        if client is None:
            return []
        raw_devices = client.get_devices(details=True)
        if isinstance(raw_devices, dict):
            raw_devices = raw_devices.get("devices", raw_devices.get("data", []))
        return [self._normalize_device(item) for item in raw_devices]

    def get_device_metadata(self, device_id: str) -> HardwareDevice | None:
        client = self._get_client()
        if client is None:
            return None
        if hasattr(client, "get_device"):
            return self._normalize_device(client.get_device(device_id, details=True))
        return next((item for item in self.list_devices() if item.device_id == device_id), None)

    @staticmethod
    def _normalize_device(raw: Mapping) -> HardwareDevice:
        identifier = str(raw.get("device_id", raw.get("id", raw.get("name", ""))))
        name = str(raw.get("device_name", raw.get("name", identifier)))
        return HardwareDevice(
            device_id=identifier,
            device_name=name,
            hardware_type=raw.get("hardware_type", raw.get("type", UNKNOWN)),
            real_hardware_or_simulator=raw.get("real_hardware_or_simulator", raw.get("device_type", UNKNOWN)),
            num_qubits=raw.get("num_qubits", raw.get("qubits", UNKNOWN)),
            status=raw.get("status", UNKNOWN),
            queue_state=raw.get("queue_state", raw.get("queue", UNKNOWN)),
            native_gate_set=raw.get("native_gate_set", raw.get("basis_gates", UNKNOWN)),
            connectivity=raw.get("connectivity", raw.get("coupling_map", UNKNOWN)),
            supports_parameterized_circuit=raw.get("supports_parameterized_circuit", UNKNOWN),
            supports_batch_submission=raw.get("supports_batch_submission", UNKNOWN),
            supports_multiple_circuits_per_job=raw.get("supports_multiple_circuits_per_job", UNKNOWN),
            supports_observable_expectation=raw.get("supports_observable_expectation", UNKNOWN),
            supports_raw_counts=raw.get("supports_raw_counts", UNKNOWN),
            supports_shots=raw.get("supports_shots", UNKNOWN),
            max_shots=raw.get("max_shots", UNKNOWN),
            max_circuit_depth=raw.get("max_circuit_depth", UNKNOWN),
            max_gate_count=raw.get("max_gate_count", UNKNOWN),
            max_circuits_per_job=raw.get("max_circuits_per_job", UNKNOWN),
            max_jobs_or_quota=raw.get("max_jobs_or_quota", raw.get("quota", UNKNOWN)),
            calibration_available=raw.get("calibration_available", UNKNOWN),
            gate_error_available=raw.get("gate_error_available", UNKNOWN),
            readout_error_available=raw.get("readout_error_available", UNKNOWN),
            t1_t2_available=raw.get("t1_t2_available", UNKNOWN),
            last_calibration_time=raw.get("last_calibration_time", UNKNOWN),
            suitability=raw.get("suitability", UNKNOWN),
        )

    def compile_or_transpile(self, circuit, device_id: str | None = None) -> dict:
        return {
            "status": "LOCAL_GENERIC_DRY_RUN_ONLY" if device_id is None else "DEVICE_COMPILATION_INTERFACE_NOT_INVOKED",
            "device_id": device_id or UNKNOWN,
            "submitted": False,
            "circuit_name": getattr(circuit, "name", UNKNOWN),
        }

    def estimate_job(self, specification: Mapping) -> dict:
        circuits = int(specification.get("circuits", 0))
        shots = int(specification.get("shots", 0))
        repeats = int(specification.get("repeats", 1))
        return {"circuit_executions": circuits * repeats, "total_shots": circuits * shots * repeats, "submitted": False}

    def prepare_job(self, specification: Mapping) -> dict:
        return redact_secrets({"status": "PREPARED_NOT_SUBMITTED", "scientific_data": False, "specification": dict(specification)})

    def submit_job(self, specification: Mapping):
        self.guard.forbid_submission()
