# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['../optical_desk/main.py'],
    pathex=['build_deps'],
    binaries=[],
    datas=[('../optical_desk/discore_64.png', '.'), ('../optical_desk/discore_512.png', '.'), ('../optical_desk/discore_tally.png', '.'), ('../optical_desk/discore_tally_dim.png', '.'), ('../optical_desk/discore.ico', '.'), ('../optical_desk/startup_chime.wav', '.')],
    hiddenimports=['winerror', 'win32api', 'win32file', 'win32event', 'win32process', 'win32security', 'win32con', 'win32timezone', 'win32crypt'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GuanHaiShiGuang',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    version='version_info.txt',
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../optical_desk/discore.ico'],
)
