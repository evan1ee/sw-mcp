"""RFC 6901 JSON Pointer construction."""


def escape_token(token: str | int) -> str:
    """Escape one reference token: ``~`` becomes ``~0`` first, then ``/`` becomes ``~1``."""
    return str(token).replace("~", "~0").replace("/", "~1")


def json_pointer(*tokens: str | int) -> str:
    """Build a JSON Pointer from tokens. No tokens gives the whole-document pointer ``""``."""
    return "".join(f"/{escape_token(t)}" for t in tokens)
