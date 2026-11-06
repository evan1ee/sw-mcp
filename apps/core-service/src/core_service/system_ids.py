"""``<prefix>_<ULID>`` IDs from the clock and the OS random source (13.2.1).

Monotonic within the process: IDs made in the same millisecond count up from the first one's
randomness, as the ULID specification suggests, so they sort in creation order.
"""

import secrets
import threading
import time
from typing import Final

from cad_application.ids import IdPrefix, encode_ulid

_RANDOM_BYTES: Final = 10
_RANDOM_MODULUS: Final = 1 << (8 * _RANDOM_BYTES)


class SystemIdSource:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._last_ms = -1
        self._last_random = 0

    def new_id(self, prefix: IdPrefix) -> str:
        with self._guard:
            ms = time.time_ns() // 1_000_000
            if ms > self._last_ms:
                self._last_ms = ms
                self._last_random = int.from_bytes(secrets.token_bytes(_RANDOM_BYTES), "big")
            else:
                ms = self._last_ms
                self._last_random += 1
                if self._last_random >= _RANDOM_MODULUS:  # 2**80 IDs in one millisecond
                    self._last_ms += 1
                    ms = self._last_ms
                    self._last_random = 0
            randomness = self._last_random.to_bytes(_RANDOM_BYTES, "big")
        return f"{prefix}_{encode_ulid(ms, randomness)}"
