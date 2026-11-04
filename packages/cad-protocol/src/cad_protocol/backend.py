"""The IPC-backed implementation of the application's ``Backend`` port (ADR-036)."""

from collections.abc import Sequence

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import HelloResult, Meta, OperationGroup, OpsApplyResult

from cad_protocol.client.ipc_client import IpcClient


class IpcBackend:
    """A connected add-in session; construction performs the handshake."""

    def __init__(self, client: IpcClient) -> None:
        self._client = client
        self._session = client.hello()

    @property
    def session(self) -> HelloResult:
        return self._session

    def snapshot_drawing(
        self, document: str, sheets: Sequence[str] | None = None, *, meta: Meta | None = None
    ) -> JsonValue:
        return self._client.snapshot_drawing(document, sheets, meta=meta)

    def apply_ops(
        self, groups: Sequence[OperationGroup], *, meta: Meta | None = None
    ) -> OpsApplyResult:
        return self._client.apply_ops(groups, meta=meta)

    def completed_operations(self) -> tuple[str, ...]:
        return self._client.completed_operations()

    def cancel(self, *, meta: Meta | None = None) -> bool:
        return self._client.cancel(meta=meta)

    def close(self) -> None:
        self._client.close()
