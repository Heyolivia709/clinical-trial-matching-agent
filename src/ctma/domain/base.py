"""The shared model base.

Snapshots, expressions, retrieval ranks, assessments, and runs are all
specified as immutable, so frozen is the default here rather than a decision
each model makes for itself.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Frozen(BaseModel):
    """Immutable, closed to unknown fields, and validated on assignment.

    Authored artifacts are versioned and frozen by the specification, so
    mutability is a defect rather than a convenience. `extra="forbid"` means a
    typo in an authored JSON file fails loudly instead of being dropped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)
