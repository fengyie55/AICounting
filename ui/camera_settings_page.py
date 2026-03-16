from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                            QComboBox, QSpinBox, QGroupBox, QMessageBox, QCheckBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import cv2
import yaml
import os

class CameraSettingsPage(QWidget):
    """
    摄像头管理设置页面
    """
    def __init__(self, config_path="config/settings.yaml"):
        super().__init__()
        self.config_path = config_path
        self.load_config()
        
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_preview)
        
        self.init_ui()
        self.detect_cameras()
    
    def load_config(self):
        """
        加载配置文件
        """
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
    
    def save_config(self):
        """
        保存配置文件
        """
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
    
    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        
        # 摄像头检测
        detect_group = QGroupBox("摄像头检测")
        detect_layout = QVBoxLayout(detect_group)
        
        self.camera_combo = QComboBox()
        detect_layout.addWidget(self.camera_combo)
        
        refresh_btn = QPushButton("刷新摄像头列表")
        refresh_btn.clicked.connect(self.detect_cameras)
        detect_layout.addWidget(refresh_btn)
        
        layout.addWidget(detect_group)
        
        # 摄像头参数配置
        params_group = QGroupBox("参数配置")
        params_layout = QVBoxLayout(params_group)
        
        # 分辨率
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("分辨率:"))
        self.res_combo = QComboBox()
        res_layout.addWidget(self.res_combo)
        params_layout.addLayout(res_layout)
        
        # 帧率
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("帧率:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 60)
        self.fps_spin.setValue(self.config['video'].get('fps', 30))
        fps_layout.addWidget(self.fps_spin)
        params_layout.addLayout(fps_layout)
        
        # 自动曝光
        exposure_layout = QHBoxLayout()
        exposure_layout.addWidget(QLabel("自动曝光:"))
        self.auto_exposure_check = QCheckBox()
        self.auto_exposure_check.setChecked(True)
        exposure_layout.addWidget(self.auto_exposure_check)
        params_layout.addLayout(exposure_layout)
        
        # 自动白平衡
        wb_layout = QHBoxLayout()
        wb_layout.addWidget(QLabel("自动白平衡:"))
        self.auto_wb_check = QCheckBox()
        self.auto_wb_check.setChecked(True)
        wb_layout.addWidget(self.auto_wb_check)
        params_layout.addLayout(wb_layout)
        
        apply_btn = QPushButton("应用配置")
        apply_btn.clicked.connect(self.apply_settings)
        params_layout.addWidget(apply_btn)
        
        save_btn = QPushButton("保存为默认配置")
        save_btn.clicked.connect(self.save_default_settings)
        params_layout.addWidget(save_btn)
        
        layout.addWidget(params_group)
        
        # 实时预览
        preview_group = QGroupBox("实时预览")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedHeight(400)
        self.preview_label.setStyleSheet("background-color: black;")
        preview_layout.addWidget(self.preview_label)
        
        # 控制按钮
        preview_btn_layout = QHBoxLayout()
        
        self.start_preview_btn = QPushButton("开始预览")
        self.start_preview_btn.clicked.connect(self.start_preview)
        preview_btn_layout.addWidget(self.start_preview_btn)
        
        self.stop_preview_btn = QPushButton("停止预览")
        self.stop_preview_btn.clicked.connect(self.stop_preview)
        self.stop_preview_btn.setEnabled(False)
        preview_btn_layout.addWidget(self.stop_preview_btn)
        
        self.take_snapshot_btn = QPushButton("拍照")
        self.take_snapshot_btn.clicked.connect(self.take_snapshot)
        preview_btn_layout.addWidget(self.take_snapshot_btn)
        
        preview_layout.addLayout(preview_btn_layout)
        
        hint_label = QLabel("<i>提示：调整摄像头角度和焦距后，建议点击'保存为默认配置'，下次启动自动生效。</i>")
        hint_label.setWordWrap(True)
        preview_layout.addWidget(hint_label)
        
        layout.addWidget(preview_group)
        
        # 加伸缩项
        layout.addStretch()
    
    def detect_cameras(self):
        """
        检测可用摄像头
        """
        self.camera_combo.clear()
        
        # 检测摄像头
        cameras = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                try:
                    backend = cap.getBackendName()
                    name = f"摄像头 {i} ({backend})"
                except:
                    name = f"摄像头 {i}"
                cameras.append((i, name))
                cap.release()
        
        for idx, name in cameras:
            self.camera_combo.addItem(name, idx)
        
        # 加载当前配置的摄像头
        current_source = self.config['video']['source']
        for i in range(self.camera_combo.count()):
            if self.camera_combo.itemData(i) == current_source:
                self.camera_combo.setCurrentIndex(i)
                break
        
        if cameras:
            self.load_resolutions(self.camera_combo.currentData())
    
    def load_resolutions(self, camera_idx):
        """
        加载摄像头支持的分辨率
        """
        self.res_combo.clear()
        
        # 常见分辨率
        common_resolutions = [
            (1920, 1080),
            (1280, 720),
            (800, 600),
            (640, 480),
            (320, 240)
        ]
        
        available = []
        cap = cv2.VideoCapture(camera_idx)
        if cap.isOpened():
            for w, h in common_resolutions:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if abs(actual_w - w) < 10 and abs(actual_h - h) < 10:
                    available.append((w, h))
            cap.release()
        
        if not available:
            available = [(640, 480)]
        
        for w, h in available:
            self.res_combo.addItem(f"{w}x{h}", (w, h))
        
        # 设置当前分辨率
        current_w = self.config['video']['width']
        current_h = self.config['video']['height']
        for i in range(self.res_combo.count()):
            w, h = self.res_combo.itemData(i)
            if w == current_w and h == current_h:
                self.res_combo.setCurrentIndex(i)
                break
    
    def apply_settings(self):
        """
        应用当前设置到摄像头
        """
        camera_idx = self.camera_combo.currentData()
        if camera_idx is None:
            QMessageBox.warning(self, "提示", "请先选择摄像头")
            return
        
        # 停止当前预览
        was_running = self.timer.isActive()
        if was_running:
            self.stop_preview()
        
        # 打开摄像头并应用设置
        cap = cv2.VideoCapture(camera_idx)
        if not cap.isOpened():
            QMessageBox.critical(self, "错误", "无法打开摄像头")
            return
        
        # 应用分辨率
        res_data = self.res_combo.currentData()
        if res_data:
            w, h = res_data
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        
        # 应用帧率
        fps = self.fps_spin.value()
        cap.set(cv2.CAP_PROP_FPS, fps)
        
        # 应用曝光设置
        if self.auto_exposure_check.isChecked():
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # 自动曝光
        else:
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # 手动曝光
        
        # 应用白平衡设置
        if self.auto_wb_check.isChecked():
            cap.set(cv2.CAP_PROP_AUTO_WB, 1)
        else:
            cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        
        cap.release()
        
        QMessageBox.information(self, "成功", "摄像头配置已应用")
        
        # 如果之前在预览，重新启动
        if was_running:
            self.start_preview()
    
    def save_default_settings(self):
        """
        保存当前设置为默认配置
        """
        camera_idx = self.camera_combo.currentData()
        if camera_idx is None:
            QMessageBox.warning(self, "提示", "请先选择摄像头")
            return
        
        res_data = self.res_combo.currentData()
        if not res_data:
            QMessageBox.warning(self, "提示", "请选择分辨率")
            return
        
        w, h = res_data
        fps = self.fps_spin.value()
        
        # 更新配置
        self.config['video']['source'] = camera_idx
        self.config['video']['width'] = w
        self.config['video']['height'] = h
        self.config['video']['fps'] = fps
        
        try:
            self.save_config()
            QMessageBox.information(self, "成功", "默认配置已保存，重启后生效")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def start_preview(self):
        """
        开始预览
        """
        camera_idx = self.camera_combo.currentData()
        if camera_idx is None:
            QMessageBox.warning(self, "提示", "请先选择摄像头")
            return
        
        self.cap = cv2.VideoCapture(camera_idx)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "错误", "无法打开摄像头")
            return
        
        # 应用当前设置
        res_data = self.res_combo.currentData()
        if res_data:
            w, h = res_data
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        
        fps = self.fps_spin.value()
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        self.timer.start(30)  # ~30 FPS
        
        self.start_preview_btn.setEnabled(False)
        self.stop_preview_btn.setEnabled(True)
    
    def stop_preview(self):
        """
        停止预览
        """
        self.timer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        self.start_preview_btn.setEnabled(True)
        self.stop_preview_btn.setEnabled(False)
        self.preview_label.clear()
    
    def update_preview(self):
        """
        更新预览画面
        """
        if self.cap is None or not self.cap.isOpened():
            return
        
        ret, frame = self.cap.read()
        if ret:
            # 转换为Qt图像
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 缩放显示
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled_pixmap)
    
    def take_snapshot(self):
        """
        拍照保存
        """
        if self.cap is None or not self.cap.isOpened():
            QMessageBox.warning(self, "提示", "请先开始预览")
            return
        
        ret, frame = self.cap.read()
        if not ret:
            QMessageBox.warning(self, "错误", "拍照失败")
            return
        
        # 保存图片
        save_dir = "data/snapshots"
        os.makedirs(save_dir, exist_ok=True)
        import time
        timestamp = int(time.time())
        save_path = os.path.join(save_dir, f"snapshot_{timestamp}.jpg")
        cv2.imwrite(save_path, frame)
        
        QMessageBox.information(self, "成功", f"照片已保存到: {save_path}")
    
    def closeEvent(self, event):
        """
        关闭事件
        """
        self.stop_preview()
        event.accept()
