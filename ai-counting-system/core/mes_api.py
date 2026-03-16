import json
import time
import threading
import requests
from typing import Dict, List, Optional, Callable
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import waitress
from .database import DatabaseManager
from .multi_line_counter import MultiLineCounter
from .product_manager import ProductManager
from .camera_manager import CameraManager

class MESAPIServer:
    """MES系统对接API服务器，提供完整的RESTful接口"""
    
    def __init__(self, db: DatabaseManager = None, counter: MultiLineCounter = None, 
                 product_manager: ProductManager = None, camera_manager: CameraManager = None):
        self.db = db
        self.counter = counter
        self.product_manager = product_manager
        self.camera_manager = camera_manager
        
        # 配置
        self.host = "0.0.0.0"
        self.port = 8000
        self.api_key = ""
        self.enabled = False
        
        # 推送配置
        self.push_enabled = False
        self.push_url = ""
        self.push_interval = 1  # 推送间隔（秒）
        self.push_headers = {}
        self.push_thread: Optional[threading.Thread] = None
        self.running = False
        
        # 回调函数
        self.on_reset_callback: Optional[Callable] = None
        self.on_model_switch_callback: Optional[Callable] = None
        self.on_config_update_callback: Optional[Callable] = None
        
        # Flask应用
        self.app = Flask(__name__)
        CORS(self.app)
        self._register_routes()
    
    def _register_routes(self):
        """注册API路由"""
        app = self.app
        
        @app.before_request
        def verify_api_key():
            """API密钥验证"""
            if not self.api_key:
                return None
            
            request_key = request.headers.get('X-API-Key', '')
            if request_key != self.api_key:
                return jsonify({'status': 'error', 'message': 'Invalid API Key'}), 401
        
        @app.route('/api/v1/status', methods=['GET'])
        def get_system_status():
            """获取系统状态"""
            try:
                status = {
                    'timestamp': int(time.time() * 1000),
                    'system': {
                        'version': '2.0.0',
                        'status': 'running'
                    },
                    'count': self.counter.get_counts() if self.counter else {},
                    'count_rate': self.counter.get_count_rate() if self.counter else 0,
                    'product': self.product_manager.get_current_product() if self.product_manager else None,
                    'camera': self.camera_manager.get_status() if self.camera_manager else {},
                    'abnormal': self.counter.get_abnormal_status() if self.counter else {}
                }
                return jsonify({'status': 'success', 'data': status})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/counts', methods=['GET'])
        def get_counts():
            """获取计数数据"""
            try:
                start_time = request.args.get('start_time', type=int)
                end_time = request.args.get('end_time', type=int)
                shift = request.args.get('shift', type=int)
                line_id = request.args.get('line_id', type=int)
                class_id = request.args.get('class_id', type=int)
                
                if self.db:
                    stats = self.db.get_count_statistics(
                        start_time=start_time,
                        end_time=end_time,
                        shift=shift,
                        line_id=line_id,
                        class_id=class_id
                    )
                    return jsonify({'status': 'success', 'data': stats})
                else:
                    return jsonify({'status': 'error', 'message': 'Database not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/records', methods=['GET'])
        def get_records():
            """获取计数记录"""
            try:
                limit = request.args.get('limit', 100, type=int)
                start_time = request.args.get('start_time', type=int)
                end_time = request.args.get('end_time', type=int)
                
                if self.db:
                    # TODO: 支持时间范围查询
                    records = self.db.get_recent_records(limit=limit)
                    return jsonify({'status': 'success', 'data': records})
                else:
                    return jsonify({'status': 'error', 'message': 'Database not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/reset', methods=['POST'])
        def reset_counter():
            """重置计数器"""
            try:
                if self.counter:
                    self.counter.reset()
                    if self.on_reset_callback:
                        self.on_reset_callback()
                    return jsonify({'status': 'success', 'message': 'Counter reset successfully'})
                else:
                    return jsonify({'status': 'error', 'message': 'Counter not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/products', methods=['GET'])
        def get_products():
            """获取产品列表"""
            try:
                if self.product_manager:
                    products = self.product_manager.list_products()
                    return jsonify({'status': 'success', 'data': products})
                else:
                    return jsonify({'status': 'error', 'message': 'Product manager not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/products/activate', methods=['POST'])
        def activate_product():
            """激活产品"""
            try:
                data = request.get_json()
                product_id = data.get('product_id')
                
                if not product_id:
                    return jsonify({'status': 'error', 'message': 'product_id is required'}), 400
                
                if self.product_manager:
                    success = self.product_manager.activate_product(product_id)
                    if success:
                        # 触发模型切换回调
                        if self.on_model_switch_callback:
                            product = self.product_manager.get_product(product_id)
                            if product:
                                self.on_model_switch_callback(product['model_path'])
                        return jsonify({'status': 'success', 'message': 'Product activated successfully'})
                    else:
                        return jsonify({'status': 'error', 'message': 'Failed to activate product'}), 400
                else:
                    return jsonify({'status': 'error', 'message': 'Product manager not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/products/current', methods=['GET'])
        def get_current_product():
            """获取当前激活的产品"""
            try:
                if self.product_manager:
                    product = self.product_manager.get_current_product()
                    return jsonify({'status': 'success', 'data': product})
                else:
                    return jsonify({'status': 'error', 'message': 'Product manager not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/config', methods=['GET'])
        def get_config():
            """获取系统配置"""
            try:
                # TODO: 实现配置读取
                config = {
                    'detection': {
                        'conf_threshold': 0.5,
                        'iou_threshold': 0.5
                    },
                    'tracker': {
                        'track_thresh': 0.5
                    },
                    'counter': {
                        'debounce_frames': 5
                    }
                }
                return jsonify({'status': 'success', 'data': config})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/config', methods=['PUT'])
        def update_config():
            """更新系统配置"""
            try:
                data = request.get_json()
                
                # 触发配置更新回调
                if self.on_config_update_callback:
                    self.on_config_update_callback(data)
                
                return jsonify({'status': 'success', 'message': 'Config updated successfully'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/camera/status', methods=['GET'])
        def get_camera_status():
            """获取摄像头状态"""
            try:
                if self.camera_manager:
                    status = self.camera_manager.get_status()
                    return jsonify({'status': 'success', 'data': status})
                else:
                    return jsonify({'status': 'error', 'message': 'Camera manager not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/export', methods=['GET'])
        def export_data():
            """导出数据"""
            try:
                format = request.args.get('format', 'excel')
                start_time = request.args.get('start_time', type=int)
                end_time = request.args.get('end_time', type=int)
                
                if format not in ['excel', 'csv', 'pdf']:
                    return jsonify({'status': 'error', 'message': 'Unsupported format'}), 400
                
                # TODO: 实现导出功能
                return jsonify({'status': 'success', 'message': 'Export completed'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/logs', methods=['GET'])
        def get_logs():
            """获取系统日志"""
            try:
                log_type = request.args.get('type', 'operation')
                limit = request.args.get('limit', 100, type=int)
                
                if self.db:
                    logs = self.db.get_logs(log_type=log_type, limit=limit)
                    return jsonify({'status': 'success', 'data': logs})
                else:
                    return jsonify({'status': 'error', 'message': 'Database not available'}), 500
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @app.route('/api/v1/health', methods=['GET'])
        def health_check():
            """健康检查"""
            return jsonify({'status': 'success', 'message': 'API server is running'})
    
    def configure(self, host: str = None, port: int = None, api_key: str = None, enabled: bool = None):
        """配置API服务器"""
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        if api_key is not None:
            self.api_key = api_key
        if enabled is not None:
            self.enabled = enabled
    
    def configure_push(self, enabled: bool = None, url: str = None, interval: int = None, headers: Dict = None):
        """配置数据推送"""
        if enabled is not None:
            self.push_enabled = enabled
        if url is not None:
            self.push_url = url
        if interval is not None:
            self.push_interval = max(1, interval)
        if headers is not None:
            self.push_headers = headers
    
    def set_callbacks(self, on_reset=None, on_model_switch=None, on_config_update=None):
        """设置回调函数"""
        self.on_reset_callback = on_reset
        self.on_model_switch_callback = on_model_switch
        self.on_config_update_callback = on_config_update
    
    def start(self):
        """启动API服务器"""
        if not self.enabled:
            logging.info("MES API服务器未启用")
            return
        
        if self.running:
            return
        
        self.running = True
        
        # 启动API服务线程
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()
        logging.info(f"MES API服务器已启动，监听 {self.host}:{self.port}")
        
        # 启动推送线程
        if self.push_enabled and self.push_url:
            self.push_thread = threading.Thread(target=self._push_loop, daemon=True)
            self.push_thread.start()
            logging.info(f"MES数据推送已启用，目标地址: {self.push_url}, 间隔: {self.push_interval}秒")
    
    def stop(self):
        """停止API服务器"""
        self.running = False
        logging.info("MES API服务器已停止")
    
    def _run_server(self):
        """运行API服务器"""
        try:
            waitress.serve(
                self.app,
                host=self.host,
                port=self.port,
                threads=4,
                _quiet=True
            )
        except Exception as e:
            logging.error(f"MES API服务器运行错误: {e}")
            self.running = False
    
    def _push_loop(self):
        """数据推送循环"""
        last_push_time = 0
        last_count = 0
        
        while self.running and self.push_enabled:
            try:
                current_time = time.time()
                
                # 按间隔推送
                if current_time - last_push_time >= self.push_interval:
                    # 获取当前数据
                    status = {
                        'timestamp': int(current_time * 1000),
                        'count': self.counter.get_counts() if self.counter else {},
                        'count_rate': self.counter.get_count_rate() if self.counter else 0,
                        'product': self.product_manager.get_current_product() if self.product_manager else None,
                        'abnormal': self.counter.get_abnormal_status() if self.counter else {}
                    }
                    
                    # 只有当计数变化或者有异常时推送
                    current_count = status['count'].get('total', 0) if status['count'] else 0
                    has_abnormal = any(status['abnormal'].values()) if status['abnormal'] else False
                    
                    if current_count != last_count or has_abnormal:
                        self._push_data(status)
                        last_count = current_count
                        last_push_time = current_time
                
                time.sleep(0.1)
                
            except Exception as e:
                logging.error(f"推送数据错误: {e}")
                time.sleep(self.push_interval)
    
    def _push_data(self, data: Dict):
        """推送数据到MES系统"""
        try:
            headers = {
                'Content-Type': 'application/json',
                **self.push_headers
            }
            
            response = requests.post(
                self.push_url,
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code != 200:
                logging.warning(f"推送数据返回非200状态码: {response.status_code}, {response.text}")
            
        except requests.exceptions.RequestException as e:
            logging.error(f"推送数据请求失败: {e}")
    
    def push_event(self, event_type: str, event_data: Dict):
        """主动推送事件到MES系统"""
        if not self.push_enabled or not self.push_url:
            return
        
        try:
            data = {
                'type': event_type,
                'timestamp': int(time.time() * 1000),
                'data': event_data
            }
            
            headers = {
                'Content-Type': 'application/json',
                **self.push_headers
            }
            
            response = requests.post(
                self.push_url,
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code != 200:
                logging.warning(f"推送事件返回非200状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logging.error(f"推送事件请求失败: {e}")
    
    def get_status(self) -> Dict:
        """获取API服务器状态"""
        return {
            'enabled': self.enabled,
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'push_enabled': self.push_enabled,
            'push_url': self.push_url
        }
