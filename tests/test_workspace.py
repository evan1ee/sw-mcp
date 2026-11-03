"""Smoke test: every workspace package is installed and importable."""

import importlib

import pytest

PACKAGES = [
    "cad_ir",
    "cad_geometry",
    "cad_references",
    "cad_compiler",
    "cad_drawing",
    "cad_verification",
    "cad_protocol",
    "cad_application",
    "core_service",
    "mcp_server",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name: str) -> None:
    assert importlib.import_module(name).__name__ == name
