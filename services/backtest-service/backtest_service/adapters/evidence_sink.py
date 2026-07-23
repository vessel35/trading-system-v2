"""Write detailed evidence to one SQLite file per run."""

from .evidence_schema import (
    EVIDENCE_SCHEMA_VERSION,
    initialize_evidence_schema,
)

__all__ = ["EVIDENCE_SCHEMA_VERSION", "initialize_evidence_schema"]
