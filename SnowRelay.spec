# -*- mode: python ; coding: utf-8 -*-
import os
import sys

tcl_root = os.path.join(sys.base_prefix, 'tcl')
python_dlls = os.path.join(sys.base_prefix, 'DLLs')
datas = [
    ('rules', 'rules'),
    ('assets', 'assets'),
    (os.path.join(tcl_root, 'tcl8.6'), '_tcl_data'),
    (os.path.join(tcl_root, 'tk8.6'), '_tk_data'),
    (os.path.join(tcl_root, 'tcl8'), 'tcl8'),
]
binaries = [
    (os.path.join(python_dlls, '_tkinter.pyd'), '.'),
    (os.path.join(python_dlls, 'tcl86t.dll'), '.'),
    (os.path.join(python_dlls, 'tk86t.dll'), '.'),
]
hiddenimports = ['openpyxl', 'xlrd']


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['build_hooks'],
    hooksconfig={},
    runtime_hooks=['build_hooks/runtime_tk.py'],
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
    name='SnowRelay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/brand/snowrelay.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SnowRelay-v0.5.0',
)
