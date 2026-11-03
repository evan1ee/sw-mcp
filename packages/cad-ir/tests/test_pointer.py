from cad_ir.core.pointer import json_pointer


def test_json_pointer_escapes() -> None:
    assert json_pointer("nodes", "a/b", "m~n", 0) == "/nodes/a~1b/m~0n/0"
    assert json_pointer() == ""


def test_json_pointer_tilde_slash_order() -> None:
    assert json_pointer("~1") == "/~01"
    assert json_pointer("") == "/"
