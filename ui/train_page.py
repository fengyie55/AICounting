from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                            QLineEdit, QListWidget, QListWidgetItem, QProgressBar,
                            QFileDialog, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
import os
import cv2

from core.trainer import FewShotTrainer
from ui.sample_config_wizard import SampleConfigWizard

class TrainThread(QThread):
    """
    训练线程
    """
    progress_updated = pyqtSignal(int)
    train_finished = pyqtSignal(bool, str)
    log_updated = pyqtSignal(str)
    
    def __init__(self, trainer, image_paths, class_name):
        super().__init__()
        self.trainer = trainer
        self.image_paths = image_paths
        self.class_name = class_name
    
    def run(self):
        try:
            self.log_updated.emit("开始训练...")
            self.progress_updated.emit(10)
            
            # 自动标注
            self.log_updated.emit("正在自动标注图片...")
            annotations = self.trainer.auto_annotate_images(self.image_paths, self.class_name)
            self.progress_updated.emit(30)
            
            # 验证标注
            self.log_updated.emit("验证标注...")
            errors = self.trainer.validate_annotations(self.image_paths, annotations)
            if errors:
                for err in errors:
                    self.log_updated.emit(f"警告: {err}")
            self.progress_updated.emit(40)
            
            # 准备数据集
            self.log_updated.emit("准备训练数据集...")
            self.trainer.prepare_dataset(self.image_paths, annotations, self.class_name)
            self.progress_updated.emit(50)
            
            # 训练
            self.log_updated.emit(f"开始训练模型 (共 {self.trainer.epochs} 轮)...")
            model_path = self.trainer.train(self.image_paths, annotations, self.class_name)
            self.progress_updated.emit(100)
            
            self.log_updated.emit(f"训练完成！模型已保存到: {model_path}")
            self.train_finished.emit(True, model_path)
            
        except Exception as e:
            self.log_updated.emit(f"训练失败: {str(e)}")
            self.train_finished.emit(False, str(e))

class TrainPage(QWidget):
    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self.trainer = FewShotTrainer()
        self.selected_images = []
        
        self.init_ui()
        self.load_models()
    
    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        
        # 引导式配置按钮
        wizard_group = QGroupBox("快速样本配置")
        wizard_layout = QVBoxLayout(wizard_group)
        
        wizard_hint = QLabel("""
        <p style="font-size: 14px;">推荐使用引导式配置向导，系统将一步步引导您完成摄像头配置、样本拍摄和模型训练，无需手动调整参数。</p>
        <p style="color: #666;">整个过程大约需要3-5分钟，操作简单，自动保障样本质量。</p>
        """)
        wizard_hint.setWordWrap(True)
        wizard_layout.addWidget(wizard_hint)
        
        self.start_wizard_btn = QPushButton("🚀 开始引导式配置")
        self.start_wizard_btn.setStyleSheet("font-size: 16px; padding: 10px; background-color: #3498db; color: white;")
        self.start_wizard_btn.clicked.connect(self.start_config_wizard)
        wizard_layout.addWidget(self.start_wizard_btn)
        
        layout.addWidget(wizard_group)
        
        # 高级模式（默认折叠）
        advanced_group = QGroupBox("高级模式（手动配置）")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)
        advanced_layout = QVBoxLayout(advanced_group)
        
        # 步骤1：选择训练图片
        step1_group = QGroupBox("步骤1：上传训练图片 (至少4张)")
        step1_layout = QVBoxLayout(step1_group)
        
        # 图片列表
        self.image_list = QListWidget()
        self.image_list.setSelectionMode(QListWidget.SingleSelection)
        self.image_list.itemClicked.connect(self.preview_image)
        step1_layout.addWidget(self.image_list)
        
        # 图片预览
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedHeight(200)
        self.preview_label.setStyleSheet("border: 1px solid #ccc;")
        step1_layout.addWidget(self.preview_label)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.add_img_btn = QPushButton("添加图片")
        self.add_img_btn.clicked.connect(self.add_images)
        btn_layout.addWidget(self.add_img_btn)
        
        self.remove_img_btn = QPushButton("移除选中")
        self.remove_img_btn.clicked.connect(self.remove_image)
        btn_layout.addWidget(self.remove_img_btn)
        
        self.clear_img_btn = QPushButton("清空列表")
        self.clear_img_btn.clicked.connect(self.clear_images)
        btn_layout.addWidget(self.clear_img_btn)
        
        step1_layout.addLayout(btn_layout)
        advanced_layout.addWidget(step1_group)
        
        # 步骤2：设置类别名称
        step2_group = QGroupBox("步骤2：设置类别信息")
        step2_layout = QVBoxLayout(step2_group)
        
        class_layout = QHBoxLayout()
        class_layout.addWidget(QLabel("类别名称:"))
        self.class_name_input = QLineEdit()
        self.class_name_input.setPlaceholderText("请输入要识别的物体名称，例如：person, car, product")
        class_layout.addWidget(self.class_name_input)
        step2_layout.addLayout(class_layout)
        
        advanced_layout.addWidget(step2_group)
        
        # 步骤3：开始训练
        step3_group = QGroupBox("步骤3：开始训练")
        step3_layout = QVBoxLayout(step3_group)
        
        self.train_btn = QPushButton("开始训练 (预计2-5分钟)")
        self.train_btn.clicked.connect(self.start_training)
        step3_layout.addWidget(self.train_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        step3_layout.addWidget(self.progress_bar)
        
        # 日志
        self.log_label = QLabel("准备就绪")
        self.log_label.setWordWrap(True)
        step3_layout.addWidget(self.log_label)
        
        advanced_layout.addWidget(step3_group)
        
        layout.addWidget(advanced_group)
        
        # 模型管理
        model_group = QGroupBox("已训练模型")
        model_layout = QVBoxLayout(model_group)
        
        self.model_list = QListWidget()
        self.model_list.itemDoubleClicked.connect(self.load_selected_model)
        model_layout.addWidget(self.model_list)
        
        model_btn_layout = QHBoxLayout()
        self.load_model_btn = QPushButton("加载选中模型")
        self.load_model_btn.clicked.connect(self.load_selected_model)
        model_btn_layout.addWidget(self.load_model_btn)
        
        self.delete_model_btn = QPushButton("删除选中模型")
        self.delete_model_btn.clicked.connect(self.delete_selected_model)
        model_btn_layout.addWidget(self.delete_model_btn)
        
        self.refresh_model_btn = QPushButton("刷新列表")
        self.refresh_model_btn.clicked.connect(self.load_models)
        model_btn_layout.addWidget(self.refresh_model_btn)
        
        model_layout.addLayout(model_btn_layout)
        layout.addWidget(model_group)
    
    def start_config_wizard(self):
        """
        启动样本配置向导
        """
        wizard = SampleConfigWizard(self, self.trainer)
        if wizard.exec_() == QWizard.Accepted:
            # 向导完成，刷新模型列表
            self.load_models()
            QMessageBox.information(self, "完成", "样本配置已完成，模型已训练成功！")
    
    def add_images(self):
        """
        添加训练图片
        """
        file_paths, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", 
                                                    "图片文件 (*.jpg *.jpeg *.png *.bmp)")
        if file_paths:
            for path in file_paths:
                if path not in self.selected_images:
                    self.selected_images.append(path)
                    item = QListWidgetItem(os.path.basename(path))
                    item.setData(Qt.UserRole, path)
                    self.image_list.addItem(item)
            
            self.log_label.setText(f"已选择 {len(self.selected_images)} 张图片")
    
    def remove_image(self):
        """
        移除选中的图片
        """
        current_item = self.image_list.currentItem()
        if current_item:
            path = current_item.data(Qt.UserRole)
            if path in self.selected_images:
                self.selected_images.remove(path)
            
            row = self.image_list.row(current_item)
            self.image_list.takeItem(row)
            
            self.log_label.setText(f"已选择 {len(self.selected_images)} 张图片")
            self.preview_label.clear()
    
    def clear_images(self):
        """
        清空图片列表
        """
        self.image_list.clear()
        self.selected_images.clear()
        self.preview_label.clear()
        self.log_label.setText("图片列表已清空")
    
    def preview_image(self, item):
        """
        预览选中的图片
        """
        path = item.data(Qt.UserRole)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled_pixmap)
    
    def start_training(self):
        """
        开始训练
        """
        if len(self.selected_images) < 4:
            QMessageBox.warning(self, "提示", "至少需要4张图片才能进行训练")
            return
        
        class_name = self.class_name_input.text().strip()
        if not class_name:
            QMessageBox.warning(self, "提示", "请输入类别名称")
            return
        
        # 禁用按钮
        self.train_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # 创建训练线程
        self.train_thread = TrainThread(self.trainer, self.selected_images, class_name)
        self.train_thread.progress_updated.connect(self.update_progress)
        self.train_thread.train_finished.connect(self.train_finished)
        self.train_thread.log_updated.connect(self.update_log)
        self.train_thread.start()
    
    def update_progress(self, value):
        """
        更新进度条
        """
        self.progress_bar.setValue(value)
    
    def update_log(self, message):
        """
        更新日志
        """
        self.log_label.setText(message)
    
    def train_finished(self, success, result):
        """
        训练完成
        """
        self.train_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "成功", f"模型训练完成！\n模型路径: {result}")
            self.load_models()  # 刷新模型列表
        else:
            QMessageBox.critical(self, "失败", f"训练失败: {result}")
    
    def load_models(self):
        """
        加载已训练的模型列表
        """
        self.model_list.clear()
        models = self.trainer.get_trained_models()
        
        for model in models:
            item = QListWidgetItem(model['name'])
            item.setData(Qt.UserRole, model['path'])
            self.model_list.addItem(item)
    
    def load_selected_model(self):
        """
        加载选中的模型
        """
        current_item = self.model_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择一个模型")
            return
        
        model_path = current_item.data(Qt.UserRole)
        if self.detector.load_model(model_path):
            QMessageBox.information(self, "成功", f"模型已加载: {os.path.basename(model_path)}")
        else:
            QMessageBox.critical(self, "错误", "加载模型失败")
    
    def delete_selected_model(self):
        """
        删除选中的模型
        """
        current_item = self.model_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择一个模型")
            return
        
        model_path = current_item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "确认", f"确定要删除模型 {os.path.basename(model_path)} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.trainer.delete_model(model_path):
                row = self.model_list.row(current_item)
                self.model_list.takeItem(row)
                QMessageBox.information(self, "成功", "模型已删除")
            else:
                QMessageBox.critical(self, "错误", "删除模型失败")
