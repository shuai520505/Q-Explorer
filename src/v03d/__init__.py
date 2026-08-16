"""Q-Explorer V0.3-D read-only scientific validity audit layer."""

from .audit import (
    SCOPE_STATUSES,
    audit_boundary_run,
    audit_competing_run,
    audit_scope_revision,
    classify_scope_run,
)
from .evidence_graph import EvidenceGraph, missing_link
from .guard import AuditExecutionForbidden, AuditModeGuard
from .history import compare_snapshots, snapshot_paths

__all__ = [
    "AuditExecutionForbidden", "AuditModeGuard", "EvidenceGraph", "SCOPE_STATUSES",
    "audit_boundary_run", "audit_competing_run", "audit_scope_revision",
    "classify_scope_run", "compare_snapshots", "missing_link", "snapshot_paths",
]
