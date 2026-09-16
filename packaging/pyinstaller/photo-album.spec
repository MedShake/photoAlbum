# -*- mode: python ; coding: utf-8 -*-

import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


datas = collect_data_files("photoalbum")

icon = None
if sys.platform == "win32":
    icon = "../../src/photoalbum/resources/icons/photoalbum.svg"


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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="photo-album",
)
