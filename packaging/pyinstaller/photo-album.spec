# -*- mode: python ; coding: utf-8 -*-

import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


datas = collect_data_files("photoalbum")

icon = None
if sys.platform == "win32":
    icon = "photoalbum.ico"


a = Analysis(
    ["photo_album.py"],
    pathex=["../../src"],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("photoalbum.templates"),
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
    ["photo_album_cli.py"],
    pathex=["../../src"],
    datas=datas,
    hiddenimports=collect_submodules("photoalbum.templates"),
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
