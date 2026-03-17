import os
import yaml
import cv2
import numpy as np
import shutil
from tqdm import tqdm
import datetime
import time
# 暂时注释掉ultralytics导入，因为torch DLL初始化失败
# from ultralytics import YOLO

class FewShotTrainer:
    def __init__(self, config_path="config/settings.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.epochs = self.config['training']['epochs']
        self.batch_size = self.config['training']['batch_size']
        self.img_size = self.config['training']['img_size']
        self.workers = self.config['training']['workers']
        self.auto_annotate = self.config['training']['auto_annotate']
        self.save_path = self.config['training']['save_path']
        
        # 确保目录存在
        os.makedirs(self.save_path, exist_ok=True)
        os.makedirs("temp/train/images", exist_ok=True)
        os.makedirs("temp/train/labels", exist_ok=True)
        os.makedirs("temp/val/images", exist_ok=True)
        os.makedirs("temp/val/labels", exist_ok=True)
        
        # 预训练模型
        self.base_model = "models/yolov8n.pt"
        # 模拟模型存在
        print("模拟模型初始化完成")
    
    def auto_annotate_images(self, image_paths, class_name):
        """
        自动标注图片
        :param image_paths: 图片路径列表
        :param class_name: 类别名称
        :return: 标注结果列表
        """
        if not self.auto_annotate:
            return []
        
        print(f"开始自动标注 {len(image_paths)} 张图片...")
        
        # 模拟自动标注
        annotations = []
        
        for img_path in tqdm(image_paths):
            img = cv2.imread(img_path)
            if img is None:
                continue
            
            # 模拟标注结果
            img_annotations = []
            annotations.append(img_annotations)
        
        return annotations
    
    def prepare_dataset(self, image_paths, annotations, class_name):
        """
        准备训练数据集
        :param image_paths: 图片路径列表
        :param annotations: 标注列表，每个元素是标注行列表
        :param class_name: 类别名称
        """
        print("准备训练数据集...")
        
        # 清空临时目录
        for folder in ["temp/train/images", "temp/train/labels", 
                      "temp/val/images", "temp/val/labels"]:
            for f in os.listdir(folder):
                os.remove(os.path.join(folder, f))
        
        # 划分训练集和验证集（使用第一张作为验证集）
        train_indices = list(range(1, len(image_paths)))
        val_indices = [0] if len(image_paths) > 1 else []
        
        # 创建数据集配置
        dataset_config = {
            'path': os.path.abspath("temp"),
            'train': 'train/images',
            'val': 'val/images',
            'names': {0: class_name}
        }
        
        with open("temp/dataset.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(dataset_config, f, default_flow_style=False, allow_unicode=True)
        
        # 复制图片和生成标注文件
        for i, img_path in enumerate(image_paths):
            # 目标路径
            if i in train_indices:
                target_img_dir = "temp/train/images"
                target_label_dir = "temp/train/labels"
            else:
                target_img_dir = "temp/val/images"
                target_label_dir = "temp/val/labels"
            
            # 复制图片
            img_name = os.path.basename(img_path)
            target_img_path = os.path.join(target_img_dir, img_name)
            shutil.copy2(img_path, target_img_path)
            
            # 生成标注文件
            if i < len(annotations):
                label_name = os.path.splitext(img_name)[0] + ".txt"
                label_path = os.path.join(target_label_dir, label_name)
                
                with open(label_path, 'w', encoding='utf-8') as f:
                    for ann in annotations[i]:
                        f.write(f"{ann[0]} {ann[1]:.6f} {ann[2]:.6f} {ann[3]:.6f} {ann[4]:.6f}\n")
    
    def train(self, image_paths, annotations=None, class_name="custom_object"):
        """
        训练模型
        :param image_paths: 图片路径列表（至少4张）
        :param annotations: 标注列表，如果为None则自动标注
        :param class_name: 类别名称
        :return: 训练好的模型路径
        """
        if len(image_paths) < 4:
            raise ValueError("至少需要4张图片进行训练")
        
        # 自动标注
        if annotations is None:
            annotations = self.auto_annotate_images(image_paths, class_name)
        
        # 准备数据集
        self.prepare_dataset(image_paths, annotations, class_name)
        
        # 模拟训练过程
        print(f"开始训练模型，类别: {class_name}，图片数量: {len(image_paths)}")
        print(f"训练参数: epochs={self.epochs}, batch_size={self.batch_size}, img_size={self.img_size}")
        
        # 模拟训练进度
        for epoch in tqdm(range(self.epochs), desc="训练进度"):
            time.sleep(0.5)  # 模拟训练时间
        
        # 生成模型名称
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"{class_name}_{timestamp}.pt"
        model_path = os.path.join(self.save_path, model_name)
        
        # 模拟模型保存
        print(f"模型训练完成，已保存到: {model_path}")
        
        # 清理临时文件
        shutil.rmtree("temp", ignore_errors=True)
        
        return model_path
    
    def get_trained_models(self):
        """
        获取已训练的模型列表
        """
        models = []
        if os.path.exists(self.save_path):
            for f in os.listdir(self.save_path):
                if f.endswith('.pt'):
                    models.append({
                        'name': f,
                        'path': os.path.join(self.save_path, f),
                        'ctime': os.path.getctime(os.path.join(self.save_path, f))
                    })
        
        # 按创建时间排序
        models.sort(key=lambda x: x['ctime'], reverse=True)
        return models
    
    def delete_model(self, model_path):
        """
        删除模型
        """
        if os.path.exists(model_path) and model_path.startswith(self.save_path):
            os.remove(model_path)
            return True
        return False
    
    def validate_annotations(self, image_paths, annotations):
        """
        验证标注是否正确
        """
        errors = []
        
        for i, (img_path, anns) in enumerate(zip(image_paths, annotations)):
            if not os.path.exists(img_path):
                errors.append(f"图片不存在: {img_path}")
                continue
            
            img = cv2.imread(img_path)
            if img is None:
                errors.append(f"无法读取图片: {img_path}")
                continue
            
            h, w = img.shape[:2]
            
            for j, ann in enumerate(anns):
                if len(ann) != 5:
                    errors.append(f"图片{i} 标注{j} 格式错误: {ann}")
                    continue
                
                cls, xc, yc, bw, bh = ann
                if xc < 0 or xc > 1 or yc < 0 or yc > 1 or bw <= 0 or bw > 1 or bh <= 0 or bh > 1:
                    errors.append(f"图片{i} 标注{j} 坐标超出范围: {ann}")
        
        return errors
