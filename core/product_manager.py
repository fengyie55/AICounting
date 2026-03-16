import yaml
import os
import time
import datetime
from typing import List, Dict, Optional
from .database import DatabaseManager
import json

class ProductManager:
    """产品模型管理器，支持产品库的增删改查和模型切换"""
    
    def __init__(self, config_path="config/settings.yaml", db: DatabaseManager = None):
        self.config_path = config_path
        self.db = db
        self.products_file = "config/products.yaml"
        self.current_product_file = "config/current_product.yaml"
        
        # 确保配置目录存在
        os.makedirs(os.path.dirname(self.products_file), exist_ok=True)
        
        # 加载产品列表
        self.products = self._load_products()
        
        # 加载当前激活的产品
        self.current_product = self._load_current_product()
    
    def _load_products(self) -> List[Dict]:
        """加载产品列表"""
        if not os.path.exists(self.products_file):
            # 创建默认产品
            default_product = {
                'id': 'default',
                'name': '默认产品',
                'model': 'YOLOv8n',
                'model_path': 'models/yolov8n.pt',
                'specs': {},
                'create_time': int(time.time() * 1000),
                'update_time': int(time.time() * 1000),
                'is_active': False
            }
            self._save_products([default_product])
            return [default_product]
        
        try:
            with open(self.products_file, 'r', encoding='utf-8') as f:
                products = yaml.safe_load(f) or []
                return products
        except Exception as e:
            print(f"加载产品列表失败: {e}")
            return []
    
    def _save_products(self, products: List[Dict]):
        """保存产品列表"""
        try:
            with open(self.products_file, 'w', encoding='utf-8') as f:
                yaml.dump(products, f, allow_unicode=True)
            self.products = products
        except Exception as e:
            print(f"保存产品列表失败: {e}")
    
    def _load_current_product(self) -> Optional[Dict]:
        """加载当前激活的产品"""
        if not os.path.exists(self.current_product_file):
            if self.products:
                # 默认激活第一个产品
                self.activate_product(self.products[0]['id'])
                return self.products[0]
            return None
        
        try:
            with open(self.current_product_file, 'r', encoding='utf-8') as f:
                current = yaml.safe_load(f)
                if current and 'id' in current:
                    # 查找对应的产品信息
                    for product in self.products:
                        if product['id'] == current['id']:
                            return product
                return None
        except Exception as e:
            print(f"加载当前产品失败: {e}")
            return None
    
    def _save_current_product(self, product: Dict):
        """保存当前激活的产品"""
        try:
            with open(self.current_product_file, 'w', encoding='utf-8') as f:
                yaml.dump({
                    'id': product['id'],
                    'name': product['name'],
                    'activate_time': int(time.time() * 1000)
                }, f, allow_unicode=True)
            self.current_product = product
        except Exception as e:
            print(f"保存当前产品失败: {e}")
    
    def add_product(self, name: str, model: str, model_path: str, 
                   specs: Dict = None, remark: str = "") -> str:
        """
        添加新产品
        :param name: 产品名称
        :param model: 模型名称
        :param model_path: 模型文件路径
        :param specs: 产品规格参数
        :param remark: 备注
        :return: 产品ID
        """
        # 生成唯一ID
        product_id = f"prod_{int(time.time())}"
        
        product = {
            'id': product_id,
            'name': name,
            'model': model,
            'model_path': model_path,
            'specs': specs or {},
            'remark': remark,
            'create_time': int(time.time() * 1000),
            'update_time': int(time.time() * 1000),
            'is_active': False
        }
        
        products = self.products.copy()
        products.append(product)
        self._save_products(products)
        
        # 记录操作日志
        if self.db:
            self.db.insert_operation_log(
                operator="system",
                action="add_product",
                details={
                    'product_id': product_id,
                    'product_name': name,
                    'model_path': model_path
                }
            )
        
        return product_id
    
    def update_product(self, product_id: str, name: str = None, model: str = None, 
                      model_path: str = None, specs: Dict = None, remark: str = None) -> bool:
        """更新产品信息"""
        products = self.products.copy()
        for i, product in enumerate(products):
            if product['id'] == product_id:
                if name is not None:
                    product['name'] = name
                if model is not None:
                    product['model'] = model
                if model_path is not None:
                    product['model_path'] = model_path
                if specs is not None:
                    product['specs'] = specs
                if remark is not None:
                    product['remark'] = remark
                
                product['update_time'] = int(time.time() * 1000)
                products[i] = product
                self._save_products(products)
                
                # 如果是当前产品，更新缓存
                if self.current_product and self.current_product['id'] == product_id:
                    self.current_product = product
                
                # 记录操作日志
                if self.db:
                    self.db.insert_operation_log(
                        operator="system",
                        action="update_product",
                        details={
                            'product_id': product_id,
                            'product_name': name or product['name']
                        }
                    )
                
                return True
        return False
    
    def delete_product(self, product_id: str) -> bool:
        """删除产品"""
        # 不能删除当前激活的产品
        if self.current_product and self.current_product['id'] == product_id:
            return False
        
        products = [p for p in self.products if p['id'] != product_id]
        if len(products) == len(self.products):
            return False
        
        self._save_products(products)
        
        # 记录操作日志
        if self.db:
            self.db.insert_operation_log(
                operator="system",
                action="delete_product",
                details={
                    'product_id': product_id
                }
            )
        
        return True
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """获取产品信息"""
        for product in self.products:
            if product['id'] == product_id:
                return product
        return None
    
    def list_products(self) -> List[Dict]:
        """获取所有产品列表"""
        return self.products.copy()
    
    def activate_product(self, product_id: str) -> bool:
        """激活指定产品"""
        product = self.get_product(product_id)
        if not product:
            return False
        
        # 检查模型文件是否存在
        if not os.path.exists(product['model_path']):
            print(f"警告：模型文件不存在: {product['model_path']}，将使用默认模型")
        
        # 更新所有产品的激活状态
        products = self.products.copy()
        for p in products:
            p['is_active'] = (p['id'] == product_id)
        self._save_products(products)
        
        # 保存当前产品
        self._save_current_product(product)
        
        # 记录切换日志
        if self.db:
            self.db.insert_operation_log(
                operator="system",
                action="activate_product",
                details={
                    'product_id': product_id,
                    'product_name': product['name'],
                    'model_path': product['model_path']
                }
            )
        
        return True
    
    def get_current_product(self) -> Optional[Dict]:
        """获取当前激活的产品"""
        return self.current_product
    
    def get_current_model_path(self) -> str:
        """获取当前使用的模型路径"""
        if self.current_product:
            return self.current_product['model_path']
        return "models/yolov8n.pt"
    
    def get_switch_history(self, limit: int = 100) -> List[Dict]:
        """获取产品切换历史记录"""
        if not self.db:
            return []
        
        logs = self.db.get_logs(
            log_type="operation",
            limit=limit
        )
        
        # 筛选产品切换相关的日志
        switch_logs = []
        for log in logs:
            if log['action'] == 'activate_product':
                try:
                    details = json.loads(log['details']) if log['details'] else {}
                    switch_logs.append({
                        'timestamp': log['timestamp'],
                        'datetime': datetime.datetime.fromtimestamp(log['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S'),
                        'product_id': details.get('product_id', ''),
                        'product_name': details.get('product_name', ''),
                        'operator': log['operator']
                    })
                except:
                    continue
        
        return switch_logs
    
    def export_products(self, export_path: str) -> bool:
        """导出产品配置到文件"""
        try:
            export_data = {
                'export_time': int(time.time() * 1000),
                'products': self.products,
                'current_product': self.current_product
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                yaml.dump(export_data, f, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            print(f"导出产品配置失败: {e}")
            return False
    
    def import_products(self, import_path: str, overwrite: bool = False) -> bool:
        """从文件导入产品配置"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = yaml.safe_load(f)
            
            if 'products' not in import_data:
                return False
            
            imported_products = import_data['products']
            
            if overwrite:
                # 覆盖现有产品
                self._save_products(imported_products)
            else:
                # 合并产品（不覆盖现有ID）
                existing_ids = {p['id'] for p in self.products}
                new_products = [p for p in imported_products if p['id'] not in existing_ids]
                merged = self.products + new_products
                self._save_products(merged)
            
            # 如果有当前产品，尝试激活
            if 'current_product' in import_data and import_data['current_product']:
                current_id = import_data['current_product'].get('id')
                if current_id:
                    self.activate_product(current_id)
            
            return True
        except Exception as e:
            print(f"导入产品配置失败: {e}")
            return False
