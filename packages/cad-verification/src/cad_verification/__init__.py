"""Verification layers (spec 10)."""

from cad_verification.api import (
    CheckStatus,
    ContractCheck,
    NotEvaluatedReason,
    PostconditionResult,
    VerificationContract,
    evaluate,
    feature_contracts,
)
from cad_verification.part import (
    Box,
    CheckResult,
    ExpectedCylinder,
    ExpectedFeature,
    ExpectedGeometry,
    Point3,
    compare,
    expected_geometry,
)

__all__ = [
    "Box",
    "CheckResult",
    "CheckStatus",
    "ContractCheck",
    "ExpectedCylinder",
    "ExpectedFeature",
    "ExpectedGeometry",
    "NotEvaluatedReason",
    "Point3",
    "PostconditionResult",
    "VerificationContract",
    "compare",
    "evaluate",
    "expected_geometry",
    "feature_contracts",
]
