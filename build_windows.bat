@echo off
echo ========================================
echo AICounting - Windows 编译脚本
echo ========================================
echo.

echo 1. 检查 Python 环境...
python --version
if errorlevel 1 (
    echo 错误: 找不到 Python，请安装 Python 3.8+
    pause
    exit /b 1
)

echo.
echo 2. 安装依赖...
pip install -r requirements.txt
pip install pyinstaller
if errorlevel 1 (
    echo 错误: 依赖安装失败
    pause
    exit /b 1
)

echo.
echo 3. 下载 YOLOv8 模型...
if not exist "models\" mkdir models
if not exist "models\yolov8n.pt" (
    echo 正在下载 yolov8n.pt...
    python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
    copy "%USERPROFILE%\.ultralytics\cache\yolov8n.pt models\yolov8n.pt
)

echo.
echo 4. 使用 PyInstaller 编译...
pyinstaller main.spec
if errorlevel 1 (
    echo 错误: 编译失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo 编译完成！
echo 输出位置: dist\AI视觉计数系统.exe
echo ========================================
echo.
echo 编译好的文件在 dist 文件夹中
pause
