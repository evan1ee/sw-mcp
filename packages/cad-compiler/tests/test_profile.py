"""Tests for CapabilityProfile (spec 6.6)."""

from cad_compiler.profile import CapabilityProfile
from cad_ir.generated.ipc import HelloResult, OperationInfo, SolidWorksInfo


def _make_session(
    version: str = "2025",
    service_pack: str = "sp1",
    ui_language: str = "en-US",
    operations: tuple[str, ...] = ("part.create", "sketch.create", "feature.create"),
) -> HelloResult:
    return HelloResult(
        protocol="0.1",
        addin_version="0.1.0",
        solidworks=SolidWorksInfo(
            version=version,
            service_pack=service_pack,
            ui_language=ui_language,
        ),
        capabilities=(),
        operations=tuple(OperationInfo(op=op, schema_version="0.1") for op in operations),
        licensed_modules=(),
        warnings=(),
    )


def test_profile_includes_coverage() -> None:
    session = _make_session()
    profile = CapabilityProfile.from_session(session)
    assert profile.operations == frozenset({"part.create", "sketch.create", "feature.create"})
    assert "sketch" in profile.coverage
    assert "extrude" in profile.coverage
    assert "cut_extrude" in profile.coverage
    assert profile.coverage["sketch"] == "create"
    assert profile.coverage["extrude"] == "create"
    assert profile.coverage["cut_extrude"] == "create"
    assert profile.hash.startswith("sha256:")


def test_profile_hash_changes_with_session() -> None:
    session1 = _make_session(service_pack="sp1")
    session2 = _make_session(service_pack="sp2")
    profile1 = CapabilityProfile.from_session(session1)
    profile2 = CapabilityProfile.from_session(session2)
    assert profile1.hash != profile2.hash
