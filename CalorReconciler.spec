# -*- mode: python ; coding: utf-8 -*-
# CalorReconciler PyInstaller spec – optimised build

import os, sys

block_cipher = None

# Heavy packages we do NOT need
EXCLUDES = [
    'tensorflow', 'keras', 'torch', 'torchvision', 'torchaudio',
    'h5py', 'scipy', 'matplotlib', 'PIL', 'Pillow',
    'IPython', 'jupyter', 'notebook', 'sklearn', 'scikit-learn',
    'numpy.f2py', 'test', 'tests', 'flask', 'django', 'jinja2',
    'cryptography', 'paramiko', 'boto3', 'botocore',
    'setuptools', 'distutils', 'pip', 'pkg_resources',
    'xmlrpc', 'multiprocessing', 'concurrent',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('calor_systems_schema.sql', '.'),  # schema next to exe
    ],
    hiddenimports=['customtkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CalorReconciler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CalorReconciler',
)
