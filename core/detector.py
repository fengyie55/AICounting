import cv2
import numpy as np
import yaml
import os

class ObjectDetector:
    def __init__(self, config_path="config/settings.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 模拟模型加载
        self.conf_threshold = self.config['detection']['conf_threshold']
        self.iou_threshold = self.config['detection']['iou_threshold']
        self.device = self.config['detection']['device']
        self.img_size = self.config['detection']['img_size']
        
        # 模拟类别名称
        self.class_names = {0: 'person', 1: 'car', 2: 'truck'}
    
    def detect(self, frame):
        """
        检测目标
        :param frame: 输入图像
        :return: 检测结果 [x1, y1, x2, y2, conf, cls]
        """
        # 模拟检测结果
        return np.empty((0, 6))
    
    def draw_detections(self, frame, detections, track_ids=None):
        """
        在图像上绘制检测框
        :param frame: 输入图像
        :param detections: 检测结果
        :param track_ids: 跟踪ID列表
        :return: 绘制后的图像
        """
        if len(detections) == 0:
            return frame
        
        for i, det in enumerate(detections):
            x1, y1, x2, y2, conf, cls = det
            cls = int(cls)
            
            # 随机颜色
            color = (0, 255, 0)
            
            # 绘制矩形框
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            
            # 绘制标签
            label = f"{self.class_names[cls]} {conf:.2f}"
            if track_ids is not None and i < len(track_ids):
                label = f"ID:{track_ids[i]} {label}"
            
            cv2.putText(frame, label, (int(x1), int(y1)-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return frame
    
    def load_model(self, model_path):
        """
        加载新模型
        :param model_path: 模型路径
        """
        if os.path.exists(model_path):
            # 模拟加载模型
            return True
        return False
    
    def get_class_names(self):
        """
        获取类别名称列表
        """
        return list(self.class_names.values())
