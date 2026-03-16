@echo off
chcp 65001
echo ======================================
echo AI视觉计数系统 打包脚本
echo ======================================

echo 正在检查依赖...
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo 正在创建临时目录...
if not exist "temp" mkdir temp
if not exist "dist" mkdir dist

echo.
echo 开始打包...
pyinstaller main.spec --clean

echo.
echo 复制必要文件...
copy "config/settings.yaml" "dist/config/"
if not exist "dist/models" mkdir "dist/models"
if exist "models/yolov8n.pt" copy "models/yolov8n.pt" "dist/models/"

echo.
echo ======================================
echo 打包完成！
echo 生成的EXE文件在 dist 目录下
echo ======================================
pause
