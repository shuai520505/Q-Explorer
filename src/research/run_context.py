"""Frozen configuration verification and traceable run identities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess

import yaml


class FrozenConfig:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._bytes = self.path.read_bytes()
        self.sha256 = hashlib.sha256(self._bytes).hexdigest()
        self.data = yaml.safe_load(self._bytes)

    def verify_unchanged(self) -> None:
        actual = hashlib.sha256(self.path.read_bytes()).hexdigest()
        if actual != self.sha256:
            raise RuntimeError("Frozen V0.2 configuration changed during a run")


@dataclass(frozen=True)
class RunIdentity:
    run_id: str
    strategy: str
    git_commit: str
    config_hash: str
    prompt_version: str
    prompt_hash: str
    model: str
    temperature: float
    start_time: str
    budget: int

    def to_dict(self) -> dict:
        return asdict(self)


def create_run_identity(
    existing_run_ids: list[str],
    strategy: str,
    config_hash: str,
    prompt_path: str | Path,
    prompt_version: str,
    model: str,
    temperature: float,
    budget: int,
    now: datetime | None = None,
) -> RunIdentity:
    timestamp = now or datetime.now(timezone.utc)
    date = timestamp.strftime("%Y%m%d")
    prefix = f"RUN_{date}_"
    numbers = [int(value.removeprefix(prefix)) for value in existing_run_ids if value.startswith(prefix) and value.removeprefix(prefix).isdigit()]
    run_id = f"{prefix}{max(numbers, default=0) + 1:03d}"
    prompt_bytes = Path(prompt_path).read_bytes()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = "UNAVAILABLE"
    return RunIdentity(
        run_id=run_id,
        strategy=strategy,
        git_commit=commit,
        config_hash=config_hash,
        prompt_version=prompt_version,
        prompt_hash=hashlib.sha256(prompt_bytes).hexdigest(),
        model=model,
        temperature=float(temperature),
        start_time=timestamp.isoformat(),
        budget=budget,
    )

