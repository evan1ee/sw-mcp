from cad_ir.core.text import normalize_text


def test_normalize_text_nfc() -> None:
    nfd = "é"
    nfc = "é"
    assert nfd != nfc
    assert normalize_text(nfd) == nfc
    assert normalize_text(nfc) == nfc
    assert normalize_text("前视基准面") == "前视基准面"
