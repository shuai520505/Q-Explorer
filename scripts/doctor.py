"""Inspect the actual host and verify that Qiskit Aer can execute a circuit."""

from __future__ import annotations

import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend import AerBackend


PACKAGE_IMPORTS = {
    "numpy": "numpy",
    "scipy": "scipy",
    "qiskit": "qiskit",
    "qiskit-aer": "qiskit_aer",
    "pandas": "pandas",
    "networkx": "networkx",
    "matplotlib": "matplotlib",
    "pytest": "pytest",
    "pyyaml": "yaml",
}


def command_version(command: list[str]) -> dict:
    executable = shutil.which(command[0])
    if not executable:
        return {"available": False, "executable": None, "version": None}
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    output = (process.stdout or process.stderr).strip()
    return {"available": process.returncode == 0, "executable": executable, "version": output}


def package_report(distribution: str, import_name: str) -> dict:
    try:
        importlib.import_module(import_name)
        version = metadata.version(distribution)
        return {"available": True, "version": version, "import_name": import_name}
    except Exception as exc:
        return {"available": False, "version": None, "import_name": import_name, "error": repr(exc)}


def memory_bytes() -> tuple[int | None, int | None]:
    try:
        import psutil

        memory = psutil.virtual_memory()
        return int(memory.total), int(memory.available)
    except Exception:
        return None, None


def build_report() -> dict:
    disk = shutil.disk_usage(ROOT)
    total_ram, available_ram = memory_bytes()
    packages = {name: package_report(name, module) for name, module in PACKAGE_IMPORTS.items()}
    try:
        aer_health = AerBackend().health_check()
    except Exception as exc:
        aer_health = {"success": False, "error": repr(exc)}
    runtime_usable = all(entry["available"] for entry in packages.values()) and bool(aer_health.get("success"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment_identity": "current execution host; cloud provider not independently verified",
        "aliyun_verified": False,
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
        },
        "cpu": {"model": platform.processor(), "logical_count": os.cpu_count()},
        "ram": {"total_bytes": total_ram, "available_bytes": available_ram},
        "disk": {"path": str(ROOT), "total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free},
        "python": {"version": platform.python_version(), "executable": sys.executable, "in_virtualenv": sys.prefix != sys.base_prefix},
        "pip": command_version([sys.executable, "-m", "pip", "--version"]),
        "git": command_version(["git", "--version"]),
        "packages": packages,
        "aer_health_check": aer_health,
        "environment_pass": runtime_usable,
        "real_quantum_hardware_used": False,
        "llm_agent_used": False,
    }


def main() -> int:
    report = build_report()
    destination = ROOT / "results" / "environment_report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"WROTE={destination}")
    return 0 if report["environment_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

