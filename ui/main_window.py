import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QTabWidget, QStatusBar, QMessageBox,
                            QFileDialog, QSlider)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import yaml
import time

from core.detector import ObjectDetector
from core.tracker import ByteTrack
from core.counter import ObjectCounter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 加载配置
        with open("config/settings.yaml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 初始化核心模块
        self.detector = ObjectDetector()
        self.tracker = ByteTrack()
        self.counter = ObjectCounter()
        
        # 视频相关
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.running = False
        
        # 初始化UI
        self.init_ui()
        
        # 状态
        self.statusBar().showMessage("就绪")
    
    def init_ui(self):
        """
        初始化界面
        """
        self.setWindowTitle(f"AI视觉智能计数系统 V{self.config['system']['version']}")
        self.setGeometry(100, 100, 1280, 800)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧视频区域
        left_layout = QVBoxLayout()
        
        # 视频显示标签
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setMinimumSize(800, 600)
        left_layout.addWidget(self.video_label)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始检测")
        self.start_btn.clicked.connect(self.start_detection)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止检测")
        self.stop_btn.clicked.connect(self.stop_detection)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        self.open_btn = QPushButton("打开视频")
        self.open_btn.clicked.connect(self.open_video)
        control_layout.addWidget(self.open_btn)
        
        self.reset_btn = QPushButton("重置计数")
        self.reset_btn.clicked.connect(self.reset_counter)
        control_layout.addWidget(self.reset_btn)
        
        left_layout.addLayout(control_layout)
        
        # 计数线调节
        line_layout = QHBoxLayout()
        line_layout.addWidget(QLabel("计数线位置:"))
        self.line_slider = QSlider(Qt.Horizontal)
        self.line_slider.setRange(10, 90)
        self.line_slider.setValue(int(self.config['counter']['line_position'] * 100))
        self.line_slider.valueChanged.connect(self.update_line_position)
        line_layout.addWidget(self.line_slider)
        left_layout.addLayout(line_layout)
        
        main_layout.addLayout(left_layout, stretch=3)
        
        # 右侧信息区域
        right_layout = QVBoxLayout()
        
        # 计数信息
        info_group = QWidget()
        info_layout = QVBoxLayout(info_group)
        
        self.total_label = QLabel("<h2>总计数: 0</h2>")
        info_layout.addWidget(self.total_label)
        
        self.up_label = QLabel("<h3>向上: 0</h3>")
        info_layout.addWidget(self.up_label)
        
        self.down_label = QLabel("<h3>向下: 0</h3>")
        info_layout.addWidget(self.down_label)
        
        self.fps_label = QLabel("帧率: 0 FPS")
        info_layout.addWidget(self.fps_label)
        
        right_layout.addWidget(info_group)
        
        # 功能标签页
        self.tabs = QTabWidget()
        
        # 导入训练页面
        from ui.train_page import TrainPage
        self.train_page = TrainPage(self.detector)
        self.tabs.addTab(self.train_page, "模型训练")
        
        from ui.settings_page import SettingsPage
        self.settings_page = SettingsPage()
        self.tabs.addTab(self.settings_page, "系统设置")
        
        from ui.camera_settings_page import CameraSettingsPage
        self.camera_page = CameraSettingsPage()
        self.tabs.addTab(self.camera_page, "摄像头管理")
        
        from ui.report_page import ReportPage
        self.report_page = ReportPage(self.counter)
        self.tabs.addTab(self.report_page, "数据报表")
        
        right_layout.addWidget(self.tabs, stretch=1)
        
        main_layout.addLayout(right_layout, stretch=1)
    
    def start_detection(self):
        """
        开始检测
        """
        if self.cap is None:
            # 默认打开摄像头
            self.cap = cv2.VideoCapture(self.config['video']['source'])
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['video']['width'])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['video']['height'])
        
        if not self.cap.isOpened():
            QMessageBox.critical(self, "错误", "无法打开视频源")
            return
        
        self.running = True
        self.timer.start(30)  # ~30 FPS
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage("检测中...")
        
        # 重置跟踪器
        self.tracker.reset()
    
    def stop_detection(self):
        """
        停止检测
        """
        self.running = False
        self.timer.stop()
        
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("已停止")
    
    def open_video(self):
        """
        打开视频文件
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "选择视频文件", "", 
                                                  "视频文件 (*.mp4 *.avi *.mov *.mkv)")
        if file_path:
            if self.running:
                self.stop_detection()
            
            self.cap = cv2.VideoCapture(file_path)
            if self.cap.isOpened():
                self.statusBar().showMessage(f"已加载视频: {file_path}")
            else:
                QMessageBox.critical(self, "错误", "无法打开视频文件")
    
    def update_frame(self):
        """
        更新视频帧
        """
        if not self.running or self.cap is None:
            return
        
        start_time = time.time()
        
        ret, frame = self.cap.read()
        if not ret:
            # 视频结束
            self.stop_detection()
            return
        
        # 检测
        detections = self.detector.detect(frame)
        
        # 跟踪
        track_results = self.tracker.update(detections)
        
        # 计数
        frame_height, frame_width = frame.shape[:2]
        self.counter.update(track_results, frame_width, frame_height)
        
        # 绘制结果
        frame = self.detector.draw_detections(frame, detections, 
                                             track_results[:, 4].astype(int) if len(track_results) > 0 else None)
        frame = self.counter.draw_count_line(frame)
        
        # 转换为Qt图像
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # 缩放显示
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)
        
        # 更新计数信息
        counts = self.counter.get_counts()
        self.total_label.setText(f"<h2>总计数: {counts['total']}</h2>")
        self.up_label.setText(f"<h3>向上: {counts['up']}</h3>")
        self.down_label.setText(f"<h3>向下: {counts['down']}</h3>")
        
        # 计算帧率
        fps = 1.0 / (time.time() - start_time)
        self.fps_label.setText(f"帧率: {fps:.1f} FPS")
    
    def update_line_position(self, value):
        """
        更新计数线位置
        """
        position = value / 100.0
        self.counter.set_line_position(position, self.config['video']['height'])
    
    def reset_counter(self):
        """
        重置计数器
        """
        self.counter.reset()
        self.tracker.reset()
        self.statusBar().showMessage("计数已重置")
    
    def closeEvent(self, event):
        """
        关闭事件
        """
        if self.running:
            self.stop_detection()
        
        event.accept()
