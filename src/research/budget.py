"""Strict VQE-run-count budget accounting."""

from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class ExperimentBudget:
    total: int
    spent: int = 0
    ledger: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.total < 0 or self.spent < 0 or self.spent > self.total:
            raise ValueError("Invalid experiment budget")

    @property
    def remaining(self) -> int:
        return self.total - self.spent

    def can_afford(self, cost: int) -> bool:
        return isinstance(cost, int) and cost >= 0 and cost <= self.remaining

    def consume(self, action_id: str, cost: int, round_id: int) -> dict:
        if not isinstance(cost, int) or cost < 0:
            raise ValueError("budget cost must be a non-negative integer VQE run count")
        before = self.remaining
        if cost > before:
            raise BudgetExceeded(f"Action {action_id} costs {cost}, only {before} VQE runs remain")
        self.spent += cost
        entry = {
            "action_id": action_id,
            "round": round_id,
            "budget_before": before,
            "budget_cost": cost,
            "budget_after": self.remaining,
        }
        self.ledger.append(entry)
        return entry

    @classmethod
    def from_ledger(cls, total: int, ledger: list[dict]) -> "ExperimentBudget":
        budget = cls(total)
        for entry in ledger:
            produced = budget.consume(entry["action_id"], int(entry["budget_cost"]), int(entry["round"]))
            if any(produced[key] != entry[key] for key in ("budget_before", "budget_cost", "budget_after")):
                raise ValueError("Budget ledger is inconsistent")
        return budget

