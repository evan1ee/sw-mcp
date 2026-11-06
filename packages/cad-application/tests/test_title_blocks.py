"""Title-block mappings loaded from the drafting standard folder (spec 13.3.4)."""

from cad_application.config import ConfigError, load_title_block_mappings
from cad_application.ports import FileStat
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_drawing.checks import TitleBlockMapping

STD = "C:\\std\\iso"
FOLDER = STD + "\\title-blocks"

GOOD = """config_version = "1.0"
template = "Company-A3.slddrt"
revision_table = true

[fields.part_number]
source = ["design_intent:metadata.part_number", "part_property:PartNo"]
required = true

[fields.material]
source = ["part_material"]

[fields.general_tolerance]
source = ["drawing_intent:general_tolerance"]
required = true
"""


class RecordingFs(MemoryFileSystem):
    """Remembers every path read or listed."""

    def __init__(self) -> None:
        super().__init__()
        self.touched: list[str] = []

    def read_bytes(self, path: str) -> bytes:
        self.touched.append(path)
        return super().read_bytes(path)

    def list_dir(self, path: str) -> tuple[str, ...]:
        self.touched.append(path)
        return super().list_dir(path)

    def stat(self, path: str) -> FileStat | None:
        self.touched.append(path)
        return super().stat(path)


def test_no_title_block_folder_gives_no_mappings() -> None:
    fs = MemoryFileSystem()
    fs.make_dirs(STD)
    assert load_title_block_mappings(fs, STD) == {}
    assert load_title_block_mappings(MemoryFileSystem(), "C:\\no\\such\\dir") == {}


def test_mapping_loaded_from_synthetic_file() -> None:
    fs = MemoryFileSystem()
    fs.make_dirs(FOLDER)
    fs.write_atomic(FOLDER + "\\Company-A3.toml", GOOD.encode())
    fs.write_atomic(FOLDER + "\\readme.txt", b"ignored")
    result = load_title_block_mappings(fs, STD)
    assert result == {
        "Company-A3.slddrt": TitleBlockMapping(
            template="Company-A3.slddrt",
            required=("part_number", "general_tolerance"),
            revision_table=True,
        )
    }


def test_invalid_mapping_is_config_invalid() -> None:
    fs = MemoryFileSystem()
    fs.make_dirs(FOLDER)
    fs.write_atomic(FOLDER + "\\bad.toml", GOOD.replace("template =", "templat =").encode())
    result = load_title_block_mappings(fs, STD)
    assert isinstance(result, ConfigError)
    assert result.code == "CONFIG_INVALID"
    assert result.origin == FOLDER + "\\bad.toml"
    assert result.key is not None


def test_toml_syntax_error_is_config_invalid_with_line() -> None:
    fs = MemoryFileSystem()
    fs.make_dirs(FOLDER)
    fs.write_atomic(FOLDER + "\\bad.toml", b'config_version = "1.0"\n[fields\n')
    result = load_title_block_mappings(fs, STD)
    assert isinstance(result, ConfigError)
    assert result.line == 2  # noqa: PLR2004


def test_duplicate_template_is_config_invalid() -> None:
    fs = MemoryFileSystem()
    fs.make_dirs(FOLDER)
    fs.write_atomic(FOLDER + "\\a.toml", GOOD.encode())
    fs.write_atomic(FOLDER + "\\b.toml", GOOD.encode())
    assert isinstance(load_title_block_mappings(fs, STD), ConfigError)


def test_only_title_blocks_folder_is_read() -> None:
    fs = RecordingFs()
    fs.make_dirs(FOLDER)
    fs.make_dirs(STD + "\\templates")
    fs.write_atomic(STD + "\\templates\\a3.slddrt", b"binary")
    fs.write_atomic(FOLDER + "\\Company-A3.toml", GOOD.encode())
    fs.touched.clear()
    load_title_block_mappings(fs, STD)
    assert fs.touched
    assert all(p.lower().startswith(FOLDER.lower()) for p in fs.touched)
    assert not any("templates" in p.lower() for p in fs.touched)
