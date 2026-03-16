#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import warnings
warnings.filterwarnings("ignore")

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

def check_dependencies():
    """
    检查依赖是否安装
    """
    required_packages = [
        'ultralytics',
        'cv2',
        'numpy',
        'PyQt5',
        'pandas',
        'openpyxl',
        'yaml',
        'scipy',
        'PIL',
        'serial'
    ]
    
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"缺少依赖包: {', '.join(missing)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def create_directories():
    """
    创建必要的目录
    """
    directories = [
        'models',
        'models/custom',
        'data',
        'data/exports',
        'data/videos',
        'temp'
    ]
    
    for d in directories:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"创建目录: {d}")

def main():
    """
    主函数
    """
    # 检查依赖
    if not check_dependencies():
        input("按回车键退出...")
        return
    
    # 创建目录
    create_directories()
    
    # 启动应用
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
