"""Narrow interface reserved for Fixed/Random/No-intervention in a later phase."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaselineStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Stable baseline identifier."""

    @abstractmethod
    def select_experiments(self, available: list[dict], budget: int) -> list[dict]:
        """Select experiments without executing them."""

