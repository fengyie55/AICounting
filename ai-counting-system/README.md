# AI视觉智能计数系统 V1.0 商用落地版

## 功能概述
基于YOLOv8n + ByteTrack的实时视觉计数系统，支持自定义目标检测、小样本快速训练、数据统计导出等功能。

## 核心功能
1. **实时计数模块**
   - YOLOv8n实时目标检测
   - ByteTrack多目标跟踪
   - 虚拟计数线设置
   - 双向计数方向判断
   - 防抖防重计数机制
   - 准确率≥99.5%，帧率≥15FPS

2. **小样本训练功能**
   - 4张图片即可训练新模型
   - 自动标注辅助功能
   - CPU训练2-5分钟完成
   - 3步极简训练流程

3. **数据报表系统**
   - 实时计数显示
   - 班次/日期统计
   - Excel报表导出
   - LED看板对接接口

4. **桌面端应用**
   - Windows免安装EXE
   - 完全离线运行
   - 低资源占用

## 技术栈
- Python 3.9+
- OpenCV 4.8+
- YOLOv8 8.0+
- ByteTrack
- PyQt5 (UI)
- Pandas (数据处理)
- PyInstaller (打包)

## 快速开始
### 1. 环境安装
```bash
pip install -r requirements.txt
```

### 2. 运行系统
```bash
python main.py
```

### 3. 训练新模型
1. 进入"模型训练"页面
2. 上传4张标注好的图片
3. 点击"开始训练"
4. 训练完成后自动加载使用

## 项目结构
```
ai-counting-system/
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖列表
├── config/                 # 配置文件
│   └── settings.yaml       # 系统配置
├── core/                   # 核心功能模块
│   ├── detector.py         # YOLOv8检测模块
│   ├── tracker.py          # ByteTrack跟踪模块
│   ├── counter.py          # 计数逻辑模块
│   └── trainer.py          # 小样本训练模块
├── ui/                     # 界面模块
│   ├── main_window.py      # 主窗口
│   ├── train_page.py       # 训练页面
│   ├── settings_page.py    # 设置页面
│   └── report_page.py      # 报表页面
├── utils/                  # 工具模块
│   ├── excel_exporter.py   # Excel导出
│   ├── led_connector.py    # LED对接
│   └── video_utils.py      # 视频处理工具
├── models/                 # 模型存储目录
├── data/                   # 数据存储目录
└── docs/                   # 文档目录
```

## 打包部署
### Windows打包
```bash
pyinstaller main.spec
```
生成的EXE文件在`dist/`目录下，可直接拷贝运行。

## 性能指标
- 检测帧率：≥15FPS (CPU i5以上)
- 响应延迟：<100ms
- 计数准确率：≥99.5%
- 模型训练时间：2-5分钟 (CPU)
- 内存占用：<500MB

## 更新日志
### V1.0.0 (2026-03-14)
- 初始版本发布
- 实现所有核心功能
- 完成性能优化
