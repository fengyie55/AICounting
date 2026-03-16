# 编译错误排查指南

如果在 Windows 编译过程中遇到错误，请参考下面的解决方案：

## 常见错误

### 1. 找不到模块 (ModuleNotFoundError)

**错误示例**:
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案**:
- 确保运行了 `pip install -r requirements.txt`
- 如果缺某个模块，手动安装：`pip install 模块名`
- 使用修复后的 `main.spec`，它包含了所有需要的 hiddenimports

### 2. 找不到数据文件/配置文件

**错误示例**:
```
FileNotFoundError: config/settings.yaml not found
```

**解决方案**:
- 新版 `main.spec` 已经修复，会自动包含整个 `config/` 目录
- 确认编译前 `config/` 目录存在并且有所有 yaml 文件

### 3. 模型文件不存在

**错误示例**:
```
models/yolov8n.pt not found
```

**解决方案**:
- `build_windows.bat` 会自动下载模型
- 如果自动下载失败，手动下载：https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
- 放到 `models/yolov8n.pt`

### 4. 图标文件错误

**错误示例**:
```
docs/icon.ico not found
```

**解决方案**:
- 新版 `main.spec` 已经移除了图标引用，可以正常编译
- 如果你有图标文件，可以在 `main.spec` 最后取消图标那行的注释

### 5. 编译完成后运行闪退

**解决方案**:

1. **修改 `main.spec` 中的 `console=True`**（默认已经是 True）
2. **重新编译**
3. **从命令行运行 exe**，看具体错误输出：
   ```batch
   cd dist
   AI视觉计数系统.exe
   ```
4. 根据错误信息解决问题

### 6. 提示缺少 `VCRUNTIME140.dll`

**解决方案**:
- 安装 Visual C++ Redistributable
- 下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe

### 7. 杀毒软件误报

**解决方案**:
- PyInstaller 编译的 exe 可能被某些杀毒软件误报
- 将 `AI视觉计数系统.exe` 添加到白名单/信任列表

### 8. PyInstaller 内存不足编译很慢

**解决方案**:
- 关闭其他程序，释放内存
- 完整编译需要几分钟，取决于电脑性能，请耐心等待
- 如果还是出错，可以尝试添加 `--no-upx` 参数

## 编译成功但运行时找不到文件

编译成功后，确保目录结构是：
```
dist/AI视觉计数系统/
├── AI视觉计数系统.exe
├── config/
│   ├── settings.yaml
│   ├── products.yaml
│   └── current_product.yaml
└── models/
    └── yolov8n.pt
```

PyInstaller 默认会创建 `dist/AI视觉计数系统/` 目录，所有依赖文件都会在里面。

## 仍然有问题？

请收集以下信息：
1. 完整的错误截图
2. Python 版本 (`python --version`)
3. PyInstaller 版本 (`pyinstaller --version`)
