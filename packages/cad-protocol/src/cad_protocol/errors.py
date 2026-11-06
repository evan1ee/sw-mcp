"""Errors raised by the IPC client (spec 8.7). No message ever holds the session token (G3)."""

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import Error, OperationOutcome

# JSON-RPC code for a response the client cannot make sense of (8.7).
INVALID_RESPONSE = -32600


class FrameError(Exception):
    """A frame that is truncated or longer than the limit."""


class IpcError(Exception):
    """A catalogue error (ADR-037): from the add-in, or raised by the client itself."""

    def __init__(
        self,
        code: str,
        message: str,
        retryable: str = "never",
        details: JsonValue = None,
        original_result: JsonValue = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details
        self.original_result = original_result

    @classmethod
    def from_error(cls, error: Error, original_result: JsonValue = None) -> "IpcError":
        """The exception for an ADR-037 error object; an unknown code is kept as text."""
        return cls(error.code, error.message, error.retryable, error.details, original_result)

    @classmethod
    def from_outcome(cls, outcome: OperationOutcome) -> "IpcError":
        """The exception for a failed operation; ``DUPLICATE_OPERATION`` keeps the old result."""
        if outcome.error is None:
            raise ValueError(f"operation {outcome.operation_id} did not fail")
        return cls.from_error(outcome.error, outcome.result)


class IpcProtocolFault(Exception):  # noqa: N818 - name fixed by the plan
    """A JSON-RPC protocol fault (-326xx), or a frame the client cannot parse."""

    def __init__(self, rpc_code: int, message: str) -> None:
        super().__init__(f"protocol fault {rpc_code}: {message}")
        self.rpc_code = rpc_code
        self.message = message
