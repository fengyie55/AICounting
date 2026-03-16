from PyQt5.QtWidgets import (QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QMessageBox, QProgressBar, QGroupBox, QComboBox,
                            QSpinBox, QCheckBox, QFileDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
import cv2
import numpy as np
import os
import time

class ImageQualityChecker:
    """
    图片质量检测工具类
    """
    @staticmethod
    def check_quality(image):
        """
        检测图片质量
        :param image: OpenCV图像
        :return: (是否合格, 问题描述)
        """
        # 1. 检测清晰度（拉普拉斯方差）
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var < 50:
            return False, f"图片模糊 (清晰度: {laplacian_var:.1f} < 50)"
        
        # 2. 检测光照（平均亮度）
        avg_brightness = gray.mean()
        if avg_brightness < 50:
            return False, f"光照不足 (亮度: {avg_brightness:.1f} < 50)"
        if avg_brightness > 220:
            return False, f"光照过强 (亮度: {avg_brightness:.1f} > 220)"
        
        # 3. 检测画面完整性（是否有大面积纯色区域）
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1].mean()
        if saturation < 20:
            return False, f"画面过灰 (饱和度: {saturation:.1f} < 20)"
        
        # 4. 检测是否有明显物体（边缘检测）
        edges = cv2.Canny(gray, 50, 150)
        edge_density = edges.sum() / (image.shape[0] * image.shape[1] * 255)
        if edge_density < 0.05:
            return False, f"未检测到目标物体 (边缘密度: {edge_density:.3f} < 0.05)"
        
        return True, f"质量合格 (清晰度: {laplacian_var:.1f}, 亮度: {avg_brightness:.1f})"

class CameraManager:
    """
    摄像头管理工具类
    """
    @staticmethod
    def list_cameras(max_check=10):
        """
        检测所有可用摄像头
        :return: 摄像头列表 [(索引, 名称)]
        """
        cameras = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # 尝试获取摄像头名称
                try:
                    backend = cap.getBackendName()
                    name = f"摄像头 {i} ({backend})"
                except:
                    name = f"摄像头 {i}"
                cameras.append((i, name))
                cap.release()
        return cameras
    
    @staticmethod
    def get_camera_resolutions(camera_index):
        """
        获取摄像头支持的分辨率
        """
        # 常见分辨率
        common_resolutions = [
            (1920, 1080),
            (1280, 720),
            (800, 600),
            (640, 480),
            (320, 240)
        ]
        
        available = []
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            for w, h in common_resolutions:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if abs(actual_w - w) < 10 and abs(actual_h - h) < 10:
                    available.append((w, h))
            cap.release()
        
        return available if available else [(640, 480)]

class WelcomePage(QWizardPage):
    """
    欢迎页面
    """
    def __init__(self):
        super().__init__()
        self.setTitle("AI视觉计数系统 - 样本配置向导")
        self.setSubTitle("本向导将引导您完成样本配置，需要拍摄4张目标物体的照片。")
        
        layout = QVBoxLayout(self)
        
        intro_label = QLabel("""
        <h3>配置流程说明：</h3>
        <ol>
            <li>选择并配置您的USB摄像头</li>
            <li>调整摄像头角度和焦距，确保目标清晰可见</li>
            <li>按照提示拍摄4张不同角度/位置的目标照片</li>
            <li>系统将自动检测照片质量，不合格需要重拍</li>
            <li>完成后自动开始训练模型</li>
        </ol>
        
        <p style="color: #666;">整个过程大约需要3-5分钟，请确保摄像头连接正常。</p>
        """)
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)
        
        # 复选框确认
        self.confirm_check = QCheckBox("我已了解配置流程，准备开始")
        layout.addWidget(self.confirm_check)
        
        self.registerField("confirm*", self.confirm_check)

class CameraConfigPage(QWizardPage):
    """
    摄像头配置页面
    """
    def __init__(self):
        super().__init__()
        self.setTitle("步骤1：摄像头配置")
        self.setSubTitle("选择要使用的摄像头并配置参数。")
        
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_preview)
        
        layout = QVBoxLayout(self)
        
        # 摄像头选择
        camera_group = QGroupBox("摄像头选择")
        camera_layout = QVBoxLayout(camera_group)
        
        self.camera_combo = QComboBox()
        self.refresh_cameras()
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        camera_layout.addWidget(self.camera_combo)
        
        refresh_btn = QPushButton("刷新摄像头列表")
        refresh_btn.clicked.connect(self.refresh_cameras)
        camera_layout.addWidget(refresh_btn)
        
        layout.addWidget(camera_group)
        
        # 参数配置
        params_group = QGroupBox("摄像头参数")
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
        self.fps_spin.setValue(30)
        fps_layout.addWidget(self.fps_spin)
        params_layout.addLayout(fps_layout)
        
        apply_btn = QPushButton("应用配置")
        apply_btn.clicked.connect(self.apply_config)
        params_layout.addWidget(apply_btn)
        
        layout.addWidget(params_group)
        
        # 预览区域
        preview_group = QGroupBox("实时预览")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedHeight(300)
        self.preview_label.setStyleSheet("background-color: black;")
        preview_layout.addWidget(self.preview_label)
        
        hint_label = QLabel("<i>提示：调整摄像头角度，确保目标物体在画面中心位置。</i>")
        hint_label.setWordWrap(True)
        preview_layout.addWidget(hint_label)
        
        layout.addWidget(preview_group)
        
        self.registerField("camera_index", self.camera_combo, "currentIndex")
        self.registerField("resolution", self.res_combo, "currentText")
        self.registerField("fps", self.fps_spin)
    
    def refresh_cameras(self):
        """
        刷新摄像头列表
        """
        self.camera_combo.clear()
        cameras = CameraManager.list_cameras()
        for idx, name in cameras:
            self.camera_combo.addItem(name, idx)
        
        if cameras:
            self.load_resolutions(0)
    
    def load_resolutions(self, camera_idx):
        """
        加载摄像头支持的分辨率
        """
        self.res_combo.clear()
        resolutions = CameraManager.get_camera_resolutions(camera_idx)
        for w, h in resolutions:
            self.res_combo.addItem(f"{w}x{h}", (w, h))
    
    def on_camera_changed(self, index):
        """
        摄像头选择变化
        """
        if index >= 0:
            camera_idx = self.camera_combo.itemData(index)
            self.load_resolutions(camera_idx)
    
    def apply_config(self):
        """
        应用摄像头配置
        """
        if self.cap is not None:
            self.cap.release()
        
        camera_idx = self.camera_combo.currentData()
        if camera_idx is None:
            QMessageBox.warning(self, "提示", "请先选择摄像头")
            return
        
        self.cap = cv2.VideoCapture(camera_idx)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "错误", "无法打开摄像头")
            return
        
        # 设置分辨率
        res_data = self.res_combo.currentData()
        if res_data:
            w, h = res_data
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        
        # 设置帧率
        fps = self.fps_spin.value()
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        self.timer.start(30)  # ~30 FPS
        QMessageBox.information(self, "成功", "摄像头配置已应用")
    
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
    
    def cleanupPage(self):
        """
        页面清理
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.timer.stop()

class SampleCapturePage(QWizardPage):
    """
    样本拍摄页面
    """
    capture_finished = pyqtSignal(list)  # 拍摄完成信号，返回图片路径列表
    
    def __init__(self):
        super().__init__()
        self.setTitle("步骤2：拍摄样本照片")
        self.setSubTitle("按照提示拍摄4张不同角度的目标物体照片。")
        
        self.current_step = 0
        self.captured_images = []
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_preview)
        self.quality_checker = ImageQualityChecker()
        
        # 拍摄提示
        self.capture_hints = [
            "请将目标物体放在画面中心，拍摄正面照片",
            "请将目标物体稍微倾斜，拍摄侧面照片",
            "请将目标物体放在不同位置，拍摄另一角度照片",
            "请将目标物体放在光线不同的位置，拍摄最后一张照片"
        ]
        
        layout = QVBoxLayout(self)
        
        # 进度显示
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 4)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 提示信息
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.hint_label)
        
        # 预览区域
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedHeight(350)
        self.preview_label.setStyleSheet("background-color: black;")
        layout.addWidget(self.preview_label)
        
        # 质量检测结果
        self.quality_label = QLabel()
        self.quality_label.setWordWrap(True)
        self.quality_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.quality_label)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.capture_btn = QPushButton("拍摄照片")
        self.capture_btn.clicked.connect(self.capture_image)
        btn_layout.addWidget(self.capture_btn)
        
        self.upload_btn = QPushButton("上传照片")
        self.upload_btn.clicked.connect(self.upload_image)
        btn_layout.addWidget(self.upload_btn)
        
        self.retake_btn = QPushButton("重新拍摄")
        self.retake_btn.clicked.connect(self.retake_image)
        self.retake_btn.setEnabled(False)
        btn_layout.addWidget(self.retake_btn)
        
        layout.addLayout(btn_layout)
        
        # 已拍摄照片缩略图
        thumbs_group = QGroupBox("已拍摄照片")
        thumbs_layout = QHBoxLayout(thumbs_group)
        
        self.thumb_labels = []
        for i in range(4):
            label = QLabel()
            label.setFixedSize(80, 60)
            label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
            label.setAlignment(Qt.AlignCenter)
            label.setText(f"#{i+1}")
            self.thumb_labels.append(label)
            thumbs_layout.addWidget(label)
        
        layout.addWidget(thumbs_group)
        
        self.update_step()
    
    def initializePage(self):
        """
        页面初始化
        """
        # 获取上一页选择的摄像头
        camera_idx = self.field("camera_index")
        if camera_idx is None:
            camera_idx = 0
        
        self.cap = cv2.VideoCapture(int(camera_idx))
        if self.cap.isOpened():
            # 设置分辨率
            res_text = self.field("resolution")
            if res_text:
                w, h = map(int, res_text.split('x'))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            
            self.timer.start(30)
        else:
            QMessageBox.warning(self, "警告", "无法打开摄像头，将使用上传模式")
            self.capture_btn.setEnabled(False)
    
    def update_step(self):
        """
        更新当前步骤
        """
        self.hint_label.setText(self.capture_hints[self.current_step])
        self.progress_bar.setValue(self.current_step)
        self.retake_btn.setEnabled(False)
        
        if self.current_step >= 4:
            # 全部拍摄完成
            self.capture_btn.setEnabled(False)
            self.upload_btn.setEnabled(False)
            self.capture_finished.emit(self.captured_images)
            self.completeChanged.emit()
        else:
            self.capture_btn.setEnabled(True)
            self.upload_btn.setEnabled(True)
    
    def update_preview(self):
        """
        更新预览画面
        """
        if self.cap is None or not self.cap.isOpened():
            return
        
        ret, frame = self.cap.read()
        if ret:
            # 实时质量检测
            is_ok, msg = self.quality_checker.check_quality(frame)
            if is_ok:
                self.quality_label.setText(f"<span style='color: green;'>✓ {msg}</span>")
            else:
                self.quality_label.setText(f"<span style='color: red;'>✗ {msg}</span>")
            
            # 转换为Qt图像
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 缩放显示
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled_pixmap)
    
    def capture_image(self):
        """
        拍摄照片
        """
        if self.cap is None or not self.cap.isOpened():
            QMessageBox.warning(self, "提示", "摄像头未打开")
            return
        
        ret, frame = self.cap.read()
        if not ret:
            QMessageBox.warning(self, "错误", "拍摄失败")
            return
        
        self.process_captured_image(frame)
    
    def upload_image(self):
        """
        上传照片
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "选择照片", "", "图片文件 (*.jpg *.jpeg *.png)")
        if file_path:
            frame = cv2.imread(file_path)
            if frame is None:
                QMessageBox.warning(self, "错误", "无法读取图片")
                return
            self.process_captured_image(frame)
    
    def process_captured_image(self, frame):
        """
        处理拍摄的图片
        """
        # 质量检测
        is_ok, msg = self.quality_checker.check_quality(frame)
        if not is_ok:
            QMessageBox.warning(self, "照片质量不合格", f"{msg}\n请重新拍摄！")
            return
        
        # 保存图片
        save_dir = "data/samples"
        os.makedirs(save_dir, exist_ok=True)
        timestamp = int(time.time())
        save_path = os.path.join(save_dir, f"sample_{self.current_step+1}_{timestamp}.jpg")
        cv2.imwrite(save_path, frame)
        
        self.captured_images.append(save_path)
        
        # 更新缩略图
        pixmap = QPixmap(save_path)
        scaled_pixmap = pixmap.scaled(self.thumb_labels[self.current_step].size(), 
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumb_labels[self.current_step].setPixmap(scaled_pixmap)
        
        # 进入下一步
        self.current_step += 1
        self.update_step()
    
    def retake_image(self):
        """
        重新拍摄上一张
        """
        if self.current_step > 0:
            self.current_step -= 1
            # 删除最后一张图片
            if self.captured_images:
                last_path = self.captured_images.pop()
                if os.path.exists(last_path):
                    os.remove(last_path)
            
            # 重置缩略图
            self.thumb_labels[self.current_step].clear()
            self.thumb_labels[self.current_step].setText(f"#{self.current_step+1}")
            
            self.update_step()
    
    def isComplete(self):
        """
        是否完成
        """
        return len(self.captured_images) >= 4
    
    def cleanupPage(self):
        """
        页面清理
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.timer.stop()

class TrainingPage(QWizardPage):
    """
    训练页面
    """
    def __init__(self, trainer):
        super().__init__()
        self.trainer = trainer
        self.samples = []
        
        self.setTitle("步骤3：模型训练")
        self.setSubTitle("系统正在训练模型，请稍候...")
        
        layout = QVBoxLayout(self)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("准备开始训练...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        
        # 训练线程
        self.train_thread = None
    
    def initializePage(self):
        """
        页面初始化
        """
        # 获取拍摄的样本
        self.samples = self.wizard().page(self.wizard().currentId() - 1).captured_images
        
        # 开始训练
        self.start_training()
    
    def start_training(self):
        """
        开始训练
        """
        from core.trainer import FewShotTrainer
        
        class TrainThread(QThread):
            progress_updated = pyqtSignal(int)
            status_updated = pyqtSignal(str)
            finished = pyqtSignal(bool, str)
            
            def __init__(self, trainer, samples):
                super().__init__()
                self.trainer = trainer
                self.samples = samples
            
            def run(self):
                try:
                    self.status_updated.emit("正在自动标注图片...")
                    self.progress_updated.emit(10)
                    
                    # 自动标注
                    annotations = self.trainer.auto_annotate_images(self.samples, "target")
                    self.progress_updated.emit(30)
                    
                    self.status_updated.emit("验证标注结果...")
                    errors = self.trainer.validate_annotations(self.samples, annotations)
                    if errors:
                        for err in errors:
                            self.status_updated.emit(f"警告: {err}")
                    self.progress_updated.emit(40)
                    
                    self.status_updated.emit("准备训练数据集...")
                    self.trainer.prepare_dataset(self.samples, annotations, "target")
                    self.progress_updated.emit(50)
                    
                    self.status_updated.emit("训练模型中...")
                    model_path = self.trainer.train(self.samples, annotations, "target")
                    self.progress_updated.emit(100)
                    
                    self.status_updated.emit(f"训练完成！模型已保存到: {model_path}")
                    self.finished.emit(True, model_path)
                    
                except Exception as e:
                    self.status_updated.emit(f"训练失败: {str(e)}")
                    self.finished.emit(False, str(e))
        
        self.train_thread = TrainThread(self.trainer, self.samples)
        self.train_thread.progress_updated.connect(self.update_progress)
        self.train_thread.status_updated.connect(self.update_status)
        self.train_thread.finished.connect(self.train_finished)
        self.train_thread.start()
    
    def update_progress(self, value):
        """
        更新进度
        """
        self.progress_bar.setValue(value)
    
    def update_status(self, msg):
        """
        更新状态
        """
        self.status_label.setText(msg)
    
    def train_finished(self, success, result):
        """
        训练完成
        """
        if success:
            self.result_label.setText(f"<span style='color: green;'>✓ 模型训练成功！</span><br>模型路径: {result}")
        else:
            self.result_label.setText(f"<span style='color: red;'>✗ 训练失败: {result}</span>")
        
        self.completeChanged.emit()
    
    def isComplete(self):
        """
        是否完成
        """
        return self.train_thread is not None and not self.train_thread.isRunning()

class FinishPage(QWizardPage):
    """
    完成页面
    """
    def __init__(self):
        super().__init__()
        self.setTitle("配置完成")
        self.setSubTitle("样本配置已完成，系统已准备好开始计数。")
        
        layout = QVBoxLayout(self)
        
        finish_label = QLabel("""
        <h3>配置完成！</h3>
        <p>您已成功完成样本配置，模型已训练完成。</p>
        <p>现在您可以：</p>
        <ul>
            <li>返回主界面开始计数</li>
            <li>查看训练好的模型</li>
            <li>如果效果不理想，可以重新运行配置向导</li>
        </ul>
        
        <p style="color: #666;">提示：建议在正式使用前进行测试计数，确保准确率符合要求。</p>
        """)
        finish_label.setWordWrap(True)
        layout.addWidget(finish_label)

class SampleConfigWizard(QWizard):
    """
    样本配置向导主类
    """
    def __init__(self, parent=None, trainer=None):
        super().__init__(parent)
        self.trainer = trainer
        
        self.setWindowTitle("AI视觉计数系统 - 样本配置向导")
        self.setFixedSize(800, 700)
        
        # 添加页面
        self.addPage(WelcomePage())
        self.addPage(CameraConfigPage())
        self.addPage(SampleCapturePage())
        self.addPage(TrainingPage(self.trainer))
        self.addPage(FinishPage())
        
        # 设置按钮文本
        self.setButtonText(QWizard.NextButton, "下一步")
        self.setButtonText(QWizard.BackButton, "上一步")
        self.setButtonText(QWizard.FinishButton, "完成")
        self.setButtonText(QWizard.CancelButton, "取消")
    
    def get_samples(self):
        """
        获取拍摄的样本图片
        """
        return self.page(2).captured_images
