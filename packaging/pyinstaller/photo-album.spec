# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_delvewheel_libs_directory,
    collect_submodules,
    copy_metadata,
)


spec_dir = Path(SPECPATH).resolve()
sys.path.insert(0, str(spec_dir.parent))
from verify_artifact import verify_collected_resources

# Collect from the installed distribution, just as in release CI. Do not mix
# source-tree modules with installed data: that can hide an incomplete wheel.
datas = collect_data_files("photoalbum")
verify_collected_resources(datas)
datas += copy_metadata("photo-album")
heif_datas, heif_binaries, heif_imports = collect_all("pillow_heif")
datas += heif_datas + copy_metadata("Pillow")
datas, heif_binaries = collect_delvewheel_libs_directory(
    "pillow_heif", datas=datas, binaries=heif_binaries,
)
image_imports = heif_imports + ["_pillow_heif", "PIL._imagingcms"]

icon = None
if sys.platform == "win32":
    icon = str(spec_dir / "photoalbum.ico")


a = Analysis(
    [str(spec_dir / "photo_album.py")],
    pathex=[str(spec_dir)],
    binaries=heif_binaries,
    datas=datas,
    hiddenimports=collect_submodules("photoalbum.templates") + image_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="photo-album",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon,
)

cli_analysis = Analysis(
    [str(spec_dir / "photo_album_cli.py")],
    pathex=[str(spec_dir)],
    binaries=heif_binaries,
    datas=datas,
    hiddenimports=collect_submodules("photoalbum.templates") + image_imports,
)
cli_exe = EXE(
    PYZ(cli_analysis.pure),
    cli_analysis.scripts,
    [],
    exclude_binaries=True,
    name="photo-album-cli",
    console=True,
    icon=icon,
)

coll = COLLECT(
    exe,
    cli_exe,
    cli_analysis.binaries,
    cli_analysis.datas,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="photo-album",
)
