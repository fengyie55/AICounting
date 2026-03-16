from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                            QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
                            QGroupBox, QMessageBox)
import yaml
import os

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.config_path = "config/settings.yaml"
        self.load_config()
        self.init_ui()
    
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
        
        # 检测设置
        detect_group = QGroupBox("检测参数设置")
        detect_layout = QVBoxLayout(detect_group)
        
        # 置信度阈值
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("置信度阈值:"))
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.1, 1.0)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setValue(self.config['detection']['conf_threshold'])
        conf_layout.addWidget(self.conf_spin)
        detect_layout.addLayout(conf_layout)
        
        # IOU阈值
        iou_layout = QHBoxLayout()
        iou_layout.addWidget(QLabel("IOU阈值:"))
        self.iou_spin = QDoubleSpinBox()
        self.iou_spin.setRange(0.1, 1.0)
        self.iou_spin.setSingleStep(0.05)
        self.iou_spin.setValue(self.config['detection']['iou_threshold'])
        iou_layout.addWidget(self.iou_spin)
        detect_layout.addLayout(iou_layout)
        
        # 设备选择
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("运行设备:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "cuda", "mps"])
        self.device_combo.setCurrentText(self.config['detection']['device'])
        device_layout.addWidget(self.device_combo)
        detect_layout.addLayout(device_layout)
        
        layout.addWidget(detect_group)
        
        # 计数设置
        count_group = QGroupBox("计数参数设置")
        count_layout = QVBoxLayout(count_group)
        
        # 计数方向
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("计数方向:"))
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["both", "up", "down"])
        self.dir_combo.setCurrentText(self.config['counter']['direction'])
        dir_layout.addWidget(self.dir_combo)
        count_layout.addLayout(dir_layout)
        
        # 防抖帧数
        debounce_layout = QHBoxLayout()
        debounce_layout.addWidget(QLabel("防抖帧数:"))
        self.debounce_spin = QSpinBox()
        self.debounce_spin.setRange(1, 20)
        self.debounce_spin.setValue(self.config['counter']['debounce_frames'])
        debounce_layout.addWidget(self.debounce_spin)
        count_layout.addLayout(debounce_layout)
        
        # 重复计数超时
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("重复计数超时(ms):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(500, 5000)
        self.timeout_spin.setSingleStep(100)
        self.timeout_spin.setValue(self.config['counter']['duplicate_timeout'])
        timeout_layout.addWidget(self.timeout_spin)
        count_layout.addLayout(timeout_layout)
        
        layout.addWidget(count_group)
        
        # 训练设置
        train_group = QGroupBox("训练参数设置")
        train_layout = QVBoxLayout(train_group)
        
        # 训练轮数
        epoch_layout = QHBoxLayout()
        epoch_layout.addWidget(QLabel("训练轮数:"))
        self.epoch_spin = QSpinBox()
        self.epoch_spin.setRange(10, 100)
        self.epoch_spin.setValue(self.config['training']['epochs'])
        epoch_layout.addWidget(self.epoch_spin)
        train_layout.addLayout(epoch_layout)
        
        # 批次大小
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("批次大小:"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 8)
        self.batch_spin.setValue(self.config['training']['batch_size'])
        batch_layout.addWidget(self.batch_spin)
        train_layout.addLayout(batch_layout)
        
        # 自动标注
        auto_annotate_layout = QHBoxLayout()
        auto_annotate_layout.addWidget(QLabel("自动标注:"))
        self.auto_annotate_check = QCheckBox()
        self.auto_annotate_check.setChecked(self.config['training']['auto_annotate'])
        auto_annotate_layout.addWidget(self.auto_annotate_check)
        train_layout.addLayout(auto_annotate_layout)
        
        layout.addWidget(train_group)
        
        # 视频设置提示
        video_hint = QLabel("""
        <p style="color: #666;"><i>提示：摄像头参数配置已移到"摄像头管理"标签页，提供更友好的可视化配置界面。</i></p>
        """)
        video_hint.setWordWrap(True)
        layout.addWidget(video_hint)
        
        # LED设置
        led_group = QGroupBox("LED看板设置")
        led_layout = QVBoxLayout(led_group)
        
        # 启用LED
        led_enable_layout = QHBoxLayout()
        led_enable_layout.addWidget(QLabel("启用LED对接:"))
        self.led_enable_check = QCheckBox()
        self.led_enable_check.setChecked(self.config['led']['enabled'])
        led_enable_layout.addWidget(self.led_enable_check)
        led_layout.addLayout(led_enable_layout)
        
        # 串口
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("串口端口:"))
        self.port_input = QLineEdit(self.config['led']['port'])
        port_layout.addWidget(self.port_input)
        led_layout.addLayout(port_layout)
        
        # 波特率
        baud_layout = QHBoxLayout()
        baud_layout.addWidget(QLabel("波特率:"))
        self.baud_spin = QSpinBox()
        self.baud_spin.setRange(9600, 115200)
        self.baud_spin.setSingleStep(9600)
        self.baud_spin.setValue(self.config['led']['baud_rate'])
        baud_layout.addWidget(self.baud_spin)
        led_layout.addLayout(baud_layout)
        
        layout.addWidget(led_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton("恢复默认")
        self.reset_btn.clicked.connect(self.reset_settings)
        btn_layout.addWidget(self.reset_btn)
        
        layout.addLayout(btn_layout)
        
        # 加一个伸缩项
        layout.addStretch()
    
    def save_settings(self):
        """
        保存设置
        """
        # 更新配置
        self.config['detection']['conf_threshold'] = self.conf_spin.value()
        self.config['detection']['iou_threshold'] = self.iou_spin.value()
        self.config['detection']['device'] = self.device_combo.currentText()
        
        self.config['counter']['direction'] = self.dir_combo.currentText()
        self.config['counter']['debounce_frames'] = self.debounce_spin.value()
        self.config['counter']['duplicate_timeout'] = self.timeout_spin.value()
        
        self.config['training']['epochs'] = self.epoch_spin.value()
        self.config['training']['batch_size'] = self.batch_spin.value()
        self.config['training']['auto_annotate'] = self.auto_annotate_check.isChecked()
        
        self.config['led']['enabled'] = self.led_enable_check.isChecked()
        self.config['led']['port'] = self.port_input.text()
        self.config['led']['baud_rate'] = self.baud_spin.value()
        
        # 保存配置
        try:
            self.save_config()
            QMessageBox.information(self, "成功", "设置已保存，重启后生效")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def reset_settings(self):
        """
        恢复默认设置
        """
        reply = QMessageBox.question(self, "确认", "确定要恢复默认设置吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 重新加载默认配置
            self.load_config()
            
            # 更新界面
            self.conf_spin.setValue(self.config['detection']['conf_threshold'])
            self.iou_spin.setValue(self.config['detection']['iou_threshold'])
            self.device_combo.setCurrentText(self.config['detection']['device'])
            
            self.dir_combo.setCurrentText(self.config['counter']['direction'])
            self.debounce_spin.setValue(self.config['counter']['debounce_frames'])
            self.timeout_spin.setValue(self.config['counter']['duplicate_timeout'])
            
            self.epoch_spin.setValue(self.config['training']['epochs'])
            self.batch_spin.setValue(self.config['training']['batch_size'])
            self.auto_annotate_check.setChecked(self.config['training']['auto_annotate'])
            
            self.led_enable_check.setChecked(self.config['led']['enabled'])
            self.port_input.setText(self.config['led']['port'])
            self.baud_spin.setValue(self.config['led']['baud_rate'])
            
            QMessageBox.information(self, "成功", "已恢复默认设置")
