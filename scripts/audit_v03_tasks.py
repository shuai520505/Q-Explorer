"""Render the frozen task quality audit without executing VQE."""

from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.v03 import TaskSuite

suite = TaskSuite(ROOT / "configs" / "frozen_v03_tasks.yaml")
destination = ROOT / "results" / "v03" / "task_quality_audit.csv"
destination.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(suite.quality_audit()).to_csv(destination, index=False)
print(f"TASKS={len(suite.tasks)}")
print(f"TASK_SUITE_HASH={suite.sha256}")
print(f"WROTE={destination}")

