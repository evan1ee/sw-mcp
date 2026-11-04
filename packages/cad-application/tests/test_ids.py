"""ULID encoding and the ID shapes of 13.2.1."""

import pytest
from cad_application.ids import ID_PREFIXES, encode_ulid, is_id

# The example ULID of the ULID specification, decoded by hand: its 48-bit time and 80 random bits.
SPEC_MS = 1469922850259
SPEC_RANDOM = bytes.fromhex("d6764c61efb99302bd5b")
SPEC_ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_ulid_golden() -> None:
    assert encode_ulid(SPEC_MS, SPEC_RANDOM) == SPEC_ULID
    assert encode_ulid(0, bytes(10)) == "0" * 26
    assert encode_ulid(2**48 - 1, b"\xff" * 10) == "7" + "Z" * 25


def test_ulid_sorts_by_time() -> None:
    low = encode_ulid(1_000, b"\xff" * 10)
    high = encode_ulid(1_001, bytes(10))
    assert low < high
    same_ms = [encode_ulid(5, n.to_bytes(10, "big")) for n in (0, 1, 31, 32, 1024)]
    assert same_ms == sorted(same_ms)


@pytest.mark.parametrize(
    ("ms", "randomness"),
    [(-1, bytes(10)), (2**48, bytes(10)), (0, bytes(9)), (0, bytes(11))],
)
def test_encode_rejects_out_of_range(ms: int, randomness: bytes) -> None:
    with pytest.raises(ValueError, match="ulid"):
        encode_ulid(ms, randomness)


def test_is_id_accepts_every_prefix() -> None:
    for prefix in ID_PREFIXES:
        assert is_id(f"{prefix}_{SPEC_ULID}", prefix)


@pytest.mark.parametrize(
    "value",
    [
        "job_01ARZ3NDEKTSV4RRFFQ69G5FAI",  # I is not in the alphabet
        "job_01ARZ3NDEKTSV4RRFFQ69G5FAL",
        "job_01ARZ3NDEKTSV4RRFFQ69G5FAO",
        "job_01ARZ3NDEKTSV4RRFFQ69G5FAU",
        "job_01arz3ndektsv4rrffq69g5fav",
        "job_01ARZ3NDEKTSV4RRFFQ69G5FA",
        "job_01ARZ3NDEKTSV4RRFFQ69G5FAVV",
        "job_01ARZ3NDEKTSV4RRFFQ69G5FAV\n",
        "rep_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "",
    ],
)
def test_is_id_rejects_bad_alphabet(value: str) -> None:
    assert not is_id(value, "job")
