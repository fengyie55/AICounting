#!/usr/bin/env python3
# -*- coding: utf-8 -*-

block_cipher = None

# 自动收集所有数据文件
def get_data_files(dir_path):
    import os
    datas = []
    if not os.path.exists(dir_path):
        return datas
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if not file.endswith('.pyc') and not file.endswith('.pyo'):
                datas.append((os.path.join(root, file), root))
    return datas

datas = []
datas.extend(get_data_files('config'))

# 只包含必要的依赖项
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'cv2',
        'numpy',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'pandas',
        'openpyxl',
        'yaml',
        'PIL',
        'tqdm',
        'psutil',
        'flask',
        'flask_cors',
        'waitress',
        'sqlalchemy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'ultralytics',
        'scipy',
        'pymodbus',
        'serial',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AI视觉计数系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
