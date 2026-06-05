import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_py37_compat.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_py37_compat", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_python_file(tmp_path, source):
    file_path = tmp_path / "sample.py"
    file_path.write_text(source, encoding="utf-8")
    return str(file_path)


def test_typing_aliases_are_not_reported_as_pep585(tmp_path):
    checker = load_checker()
    file_path = write_python_file(
        tmp_path,
        "from typing import Dict, List, Tuple\n"
        "value: List[Tuple[str, str]] = []\n"
        "def f(items: Dict[str, int]) -> Tuple[str, int]:\n"
        "    return ('ok', 1)\n",
    )

    assert checker.find_incompatible_syntax(file_path) == []


def test_builtin_generic_annotations_are_reported(tmp_path):
    checker = load_checker()
    file_path = write_python_file(
        tmp_path,
        "value: list[tuple[str, str]] = []\n"
        "def f(items: dict[str, int]) -> set[str]:\n"
        "    return set()\n",
    )

    issues = checker.find_incompatible_syntax(file_path)

    assert [issue[0] for issue in issues] == [
        "PEP 585 generic",
        "PEP 585 generic",
        "PEP 585 generic",
        "PEP 585 generic",
    ]


def test_value_level_set_union_is_not_reported(tmp_path):
    checker = load_checker()
    file_path = write_python_file(
        tmp_path,
        "def f():\n"
        "    left = {'a'}\n"
        "    right = {'b'}\n"
        "    return left | right\n",
    )

    assert checker.find_incompatible_syntax(file_path) == []


def test_union_pipe_annotation_is_reported(tmp_path):
    checker = load_checker()
    file_path = write_python_file(tmp_path, "def f(value: str | None) -> None:\n    pass\n")

    assert checker.find_incompatible_syntax(file_path) == [
        ("Union | syntax", 1, "Use Union[...] instead of | in annotations")
    ]


def test_builtin_generic_alias_assignment_is_reported(tmp_path):
    checker = load_checker()
    file_path = write_python_file(tmp_path, "TorrentMap = dict[str, str]\n")

    assert checker.find_incompatible_syntax(file_path) == [
        ("PEP 585 generic", 1, "Use typing.Dict instead of built-in dict[...]")
    ]


def test_qualified_unsupported_typing_name_is_reported(tmp_path):
    checker = load_checker()
    file_path = write_python_file(
        tmp_path,
        "import typing\n"
        "class Example:\n"
        "    def clone(self) -> typing.Self:\n"
        "        return self\n",
    )

    assert checker.find_incompatible_syntax(file_path) == [
        ("Unsupported typing: Self", 3, "Requires typing_extensions or a newer Python runtime")
    ]


def test_direct_file_path_is_scanned(tmp_path):
    checker = load_checker()
    file_path = write_python_file(tmp_path, "value: list[str] = []\n")

    assert checker.scan_project(file_path) == [
        (file_path, 1, "PEP 585 generic", "Use typing.List instead of built-in list[...]")
    ]


def test_similarly_named_vendor_directory_is_not_excluded(tmp_path):
    checker = load_checker()
    vendorized_dir = tmp_path / "lib" / "vendorized"
    vendorized_dir.mkdir(parents=True)
    file_path = vendorized_dir / "bad.py"
    file_path.write_text("value: list[str] = []\n", encoding="utf-8")

    assert checker.scan_project(str(tmp_path)) == [
        (str(file_path), 1, "PEP 585 generic", "Use typing.List instead of built-in list[...]")
    ]


def test_excluded_directories_are_skipped(tmp_path):
    checker = load_checker()
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "bad.py").write_text("value: list[str] = []\n", encoding="utf-8")

    assert checker.scan_project(str(tmp_path)) == []
