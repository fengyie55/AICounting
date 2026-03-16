# Windows 编译生成可执行文件指南

## 快速编译

### 方法一：使用自动编译脚本（推荐）

1. 在 Windows 电脑上克隆项目：
```batch
git clone https://github.com/fengyie55/AICounting.git
cd AICounting
```

2. 双击运行 `build_windows.bat`

3. 等待编译完成，编译好的 `AI视觉计数系统.exe` 会生成在 `dist/` 目录下

### 方法二：手动编译

1. 安装 Python 3.8 或更高版本

2. 安装依赖：
```batch
pip install -r requirements.txt
```

3. 创建 models 目录并下载模型：
```batch
mkdir models
```
YOLOv8n 会自动下载到 `models/yolov8n.pt`

4. 使用 PyInstaller 编译：
```batch
pyinstaller main.spec
```

5. 编译完成后，exe 文件位于 `dist/AI视觉计数系统.exe`

## 运行程序

编译完成后直接双击 `dist/AI视觉计数系统.exe` 即可运行，无需安装 Python 环境。

## 注意事项

1. **模型文件**: 首次编译会自动下载 yolov8n.pt (约 6MB)，需要网络连接
2. **防火墙**: Windows 可能会提示防火墙警告，允许网络访问即可
3. **杀毒软件**: 某些杀毒软件可能会误报 PyInstaller 编译的 exe，可以添加信任
4. **首次启动**: 首次启动需要一点时间加载模型，请耐心等待
5. **配置文件**: 确保 `config/` 目录与 exe 在同一目录下

## 项目结构

```
AICounting/
├── AI视觉计数系统.exe       (编译后的可执行文件)
├── config/                 (配置文件目录)
│   ├── settings.yaml
│   ├── products.yaml
│   └── current_product.yaml
├── models/                (模型文件目录)
│   └── yolov8n.pt
└── docs/                  (文档目录)
```

## 故障排除

**Q: 编译时提示缺少模块**
A: 运行 `pip install -r requirements.txt` 确保所有依赖安装完成

**Q: 运行时提示找不到配置文件**
A: 确保 `config/` 目录和 exe 在同一文件夹下

**Q: 运行时提示找不到模型**
A: 确保 `models/yolov8n.pt` 文件存在
