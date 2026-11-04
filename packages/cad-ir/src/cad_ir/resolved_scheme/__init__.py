"""Resolved Dimension Scheme (spec 11.10.1)."""

from cad_ir.resolved_scheme.model import (
    RESOLVED_SCHEME_SCHEMA_ID,
    ResolvedScheme,
    SchemeEntry,
)
from cad_ir.resolved_scheme.parse import parse_resolved_scheme

__all__ = [
    "RESOLVED_SCHEME_SCHEMA_ID",
    "ResolvedScheme",
    "SchemeEntry",
    "parse_resolved_scheme",
]
