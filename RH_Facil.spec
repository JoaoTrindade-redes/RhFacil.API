# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project = Path(SPECPATH)

app_datas = [
    (str(project / "rh_facil.db"), "."),
]
app_datas += collect_data_files("customtkinter")

app_hiddenimports = []
app_hiddenimports += collect_submodules("customtkinter")
app_hiddenimports += collect_submodules("reportlab")

# ---------------- RH Fácil ----------------
a = Analysis(
    ["app.py"],
    pathex=[str(project)],
    binaries=[],
    datas=app_datas,
    hiddenimports=app_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RH Facil",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="version_info.txt",
    icon=None,
)

# ---------------- Atualizador ----------------
u = Analysis(
    ["atualizador.py"],
    pathex=[str(project)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

upyz = PYZ(u.pure)

updater_exe = EXE(
    upyz,
    u.scripts,
    [],
    exclude_binaries=True,
    name="RH Facil Updater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="version_info.txt",
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    updater_exe,
    u.binaries,
    u.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RH Facil",
)
