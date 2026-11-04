"""Ports the application depends on (guideline G2). Adapters live in other packages."""

from collections.abc import Sequence
from typing import Protocol

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import HelloResult, Meta, OperationGroup, OpsApplyResult


class Backend(Protocol):
    """A CAD backend session (ADR-036): the add-in, or a replay of one."""

    @property
    def session(self) -> HelloResult: ...

    def snapshot_drawing(
        self, document: str, sheets: Sequence[str] | None = None, *, meta: Meta | None = None
    ) -> JsonValue: ...

    def apply_ops(
        self, groups: Sequence[OperationGroup], *, meta: Meta | None = None
    ) -> OpsApplyResult: ...

    def completed_operations(self) -> tuple[str, ...]: ...

    def cancel(self, *, meta: Meta | None = None) -> bool: ...
