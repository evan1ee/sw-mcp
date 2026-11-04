"""Errors of the project store (ADR-037). Messages never carry file contents."""

from dataclasses import dataclass
from typing import Literal

from cad_ir.core.json_types import JsonValue


@dataclass(frozen=True, slots=True)
class StoreError:
    """``STORE_LOCKED`` or ``STORE_CORRUPT``, returned instead of raised."""

    code: Literal["STORE_LOCKED", "STORE_CORRUPT"]
    message: str
    details: JsonValue = None


def locked() -> StoreError:
    return StoreError(
        "STORE_LOCKED", "The project store is locked by another writer.", {"reason": "lock_held"}
    )


def corrupt(reason: str, file: str) -> StoreError:
    """``file`` is a name relative to the store, never a path outside it."""
    return StoreError(
        "STORE_CORRUPT",
        f"The project store failed an integrity check ({reason}).",
        {"reason": reason, "file": file},
    )
