from pathlib import Path
import shutil

from tests.pack_lifecycle_support import run_pack_lifecycle


def test_adding_only_a_pack_directory_in_source_tree(tmp_path):
    root = tmp_path / "src"
    shutil.copytree(
        Path("src/photoalbum"), root / "photoalbum",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    core = {p.relative_to(root): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and "templates" not in p.relative_to(root).parts}
    run_pack_lifecycle(root, tmp_path)
    assert all((root / name).read_bytes() == content for name, content in core.items())
