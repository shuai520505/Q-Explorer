"""Q-Explorer V0.4 boundary noise-robustness layer."""

from .boundary import BoundaryEstimator, BoundarySignature, shift_category
from .audit import audit_boundary_run, wilson_interval
from .classification import DISCOVERY_SIGNALS, classify_noise_level
from .transfer import build_n0_transfer_hypothesis
from .protocol import V04Protocol

__all__ = [
    "BoundaryEstimator", "BoundarySignature", "audit_boundary_run", "wilson_interval", "DISCOVERY_SIGNALS",
    "V04Protocol", "build_n0_transfer_hypothesis", "classify_noise_level", "shift_category",
]
