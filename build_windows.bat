@echo off
chcp 65001 >nul
echo ========================================
echo AICounting - Windows 编译脚本
echo ========================================
echo.

echo 1. 检查 Python 环境...
python --version
if errorlevel 1 (
    echo [错误] 找不到 Python，请安装 Python 3.8 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo 注意: 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo.
echo 2. 升级 pip...
python -m pip install --upgrade pip

echo.
echo 3. 安装依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)

echo.
echo 4. 准备模型文件...
if not exist "models\" (
    echo 创建 models 目录...
    mkdir models
)
if not exist "models\yolov8n.pt" (
    echo [信息] 正在下载 yolov8n.pt 模型文件...
    python -c "from ultralytics import YOLO; print('Downloading yolov8n.pt...'); model = YOLO('yolov8n.pt'); print('Download complete')"
    if exist "%USERPROFILE%\.ultralytics\cache\yolov8n.pt" (
        copy "%USERPROFILE%\.ultralytics\cache\yolov8n.pt" models\yolov8n.pt
        echo [信息] 模型已复制到 models/yolov8n.pt
    )
) else (
    echo [信息] models/yolov8n.pt 已存在，跳过下载
)

echo.
echo 5. 使用 PyInstaller 编译...
echo 这可能需要几分钟时间，请耐心等待...
pyinstaller main.spec --clean
if errorlevel 1 (
    echo.
    echo [错误] 编译失败!
    echo 请检查上面的错误信息，常见问题:
    echo  - 缺少依赖: 请确保执行了 pip install -r requirements.txt
    echo  - 模型文件不存在: 请检查 models/yolov8n.pt 是否存在
    echo  - Python版本太低: 需要 Python 3.8+
    pause
    exit /b 1
)

echo.
echo ========================================
echo 🎉 编译完成!
echo ========================================
echo.
echo 输出文件位置: dist\AI视觉计数系统.exe
echo 直接双击 dist\AI视觉计数系统.exe 即可运行
echo.
pause
