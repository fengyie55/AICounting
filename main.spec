# -*- mode: python ; coding: utf-8 -*-
# Fixed for V1.0.2 -解决常见编译错误

block_cipher = None

# 自动收集所有数据文件 - 包含整个config目录
import os
def get_data_files(dir_path):
    datas = []
    if not os.path.exists(dir_path):
        return datas
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if not file.endswith('.pyc') and not file.endswith('.pyo'):
                datas.append((os.path.join(root, file), root))
    return datas

datas = []
# 包含所有配置文件
datas.extend(get_data_files('config'))
# 如果models目录存在，包含所有模型文件
datas.extend(get_data_files('models'))
# 包含docs
datas.extend(get_data_files('docs'))

a = Analysis(
    ['main_v2.py'],  # 使用最新的 main_v2 作为入口
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # YOLO/ultralytics
        'ultralytics',
        'ultralytics.nn',
        'ultralytics.nn.tasks',
        'ultralytics.nn.modules',
        'ultralytics.data',
        'ultralytics.utils',
        'ultralytics.engine',
        'ultralytics.models',
        'ultralytics.trackers',
        # 核心依赖
        'cv2',
        'cv2.cv2',
        'numpy',
        # PyQt5
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        # 其他模块
        'pandas',
        'openpyxl',
        'yaml',
        '_yaml',
        'scipy',
        'PIL',
        'Pillow',
        'serial',
        'pyserial',
        'torch',
        'torchvision',
        'tqdm',
        'psutil',
        'pymodbus',
        'sqlalchemy',
        'pymysql',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    console=True,  # 设置为 True 可以看到错误输出，调试方便；发布时改为 False 隐藏控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 如果有图标可以取消注释下面一行
    # icon='docs/icon.ico'
)
