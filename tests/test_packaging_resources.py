"""Release artifacts must retain pack data and actually initialize the GUI."""
import io
from importlib.util import find_spec
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tarfile
from types import SimpleNamespace
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
verify = SimpleNamespace(**runpy.run_path(str(ROOT / "packaging" / "verify_artifact.py")))


@pytest.fixture
def source(tmp_path):
    package = tmp_path / "source" / "photoalbum"
    for name, content in {
        "templates/complex/photo_page/geometry.json": b'{"families": {}}',
        "templates/msb/assets/geographic_map/countries.json": b'{"type": "FeatureCollection"}',
        "templates/complex/docs/help.fr.html": b"<h1>Complex</h1>",
        "templates/complex/docs/preview_landscape.png": b"image",
        "templates/simplex/i18n/en.json": b"{}",
        "resources/icons/photoalbum.svg": b"<svg/>",
    }.items():
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return package


def make_artifact(tmp_path, kind, resources):
    artifact = tmp_path / f"artifact.{kind}"
    if kind == "bundle":
        for name, data in resources.items():
            path = artifact / "_internal" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    elif kind == "whl":
        with ZipFile(artifact, "w") as archive:
            for name, data in resources.items():
                archive.writestr(name, data)
    else:
        with tarfile.open(artifact, "w:gz") as archive:
            for name, data in resources.items():
                prefix = "photo_album-0.5.0/src" if kind == "sdist" else "photo-album/_internal"
                info = tarfile.TarInfo(f"{prefix}/{name}")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    return artifact


@pytest.mark.parametrize("kind", ["bundle", "whl", "sdist", "tar.gz"])
def test_artifact_resources_match_source(tmp_path, source, kind):
    artifact = make_artifact(tmp_path, kind, verify.package_resources(source))
    verify.verify_artifact(artifact, source)


@pytest.mark.parametrize("kind", ["bundle", "whl", "sdist", "tar.gz"])
@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_artifact_verification_rejects_missing_or_changed_geometry(tmp_path, source, kind, damage):
    resources = verify.package_resources(source)
    name = "photoalbum/templates/complex/photo_page/geometry.json"
    if damage == "missing":
        resources.pop(name)
    else:
        resources[name] = b"{}"
    artifact = make_artifact(tmp_path, kind, resources)
    with pytest.raises(ValueError, match="geometry.json"):
        verify.verify_artifact(artifact, source)


def test_pyinstaller_collection_checks_other_pack_resources(source):
    datas = [(str(path), (Path("photoalbum") / path.relative_to(source).parent).as_posix())
             for path in source.rglob("*") if path.is_file()]
    verify.verify_collected_resources(datas, source)
    datas = [(path, destination) for path, destination in datas if not path.endswith("countries.json")]
    with pytest.raises(ValueError, match="countries.json"):
        verify.verify_collected_resources(datas, source)


@pytest.mark.skipif(find_spec("build") is None, reason="Requires the packaging extra")
def test_built_sdist_and_wheel_include_all_package_resources(tmp_path):
    # build creates the wheel from the sdist, as in release CI. Inspect the
    # artifacts themselves rather than an editable install or SOURCES.txt.
    result = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheel, = tmp_path.glob("*.whl")
    sdist, = tmp_path.glob("*.tar.gz")
    verify.verify_artifact(sdist)
    verify.verify_artifact(wheel)


def gui_command(source):
    return [sys.executable, "-c", (
        f"import sys; sys.path.insert(0, {str(source)!r}); "
        "from photoalbum.gui.application import main; raise SystemExit(main())"
    )]


def test_real_gui_startup_in_both_languages():
    verify.smoke_test(gui_command(ROOT / "src"))


def test_real_gui_startup_fails_when_complex_geometry_is_missing(tmp_path):
    package = shutil.copytree(ROOT / "src" / "photoalbum", tmp_path / "photoalbum",
                              ignore=shutil.ignore_patterns("__pycache__"))
    (package / "templates" / "complex" / "photo_page" / "geometry.json").unlink()
    with pytest.raises(RuntimeError, match="geometry.json"):
        verify.smoke_test(gui_command(tmp_path))
