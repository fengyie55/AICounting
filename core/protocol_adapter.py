import time
import threading
from typing import Dict, Callable, Optional
import json
import logging
# 暂时注释掉Modbus相关导入，因为pymodbus 3.12.1 API已变化
# from pymodbus.server import StartTcpServer, StartSerialServer
# from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
# from pymodbus.device import ModbusDeviceIdentification
# from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
# from pymodbus.constants import Endian
import http.server
import socketserver
import json

class IndustrialProtocolAdapter:
    """工业协议适配器，支持Modbus、HTTP、TCP等协议对接"""
    
    def __init__(self, db = None, counter = None, camera_manager = None, system_monitor = None):
        self.db = db
        self.counter = counter
        self.camera_manager = camera_manager
        self.system_monitor = system_monitor
        
        # 服务器状态
        self.modbus_running = False
        self.http_running = False
        self.tcp_running = False
        
        # 配置
        self.modbus_config = {
            'enabled': False,
            'mode': 'tcp',  # tcp/rtu
            'port': 502,
            'baudrate': 9600,
            'parity': 'N',
            'stopbits': 1,
            'timeout': 1
        }
        
        self.http_config = {
            'enabled': False,
            'port': 8080,
            'api_key': ''
        }
        
        self.tcp_config = {
            'enabled': False,
            'port': 9000,
            'buffer_size': 1024
        }
        
        # 回调函数
        self.on_count_callback: Optional[Callable] = None
        self.on_command_callback: Optional[Callable] = None
        
        # Modbus数据映射
        self.modbus_registers = {
            # 保持寄存器（可读可写）
            'total_count': 0,       # 0: 总计数
            'line1_count': 1,       # 1: 线1计数
            'line2_count': 2,       # 2: 线2计数
            'line3_count': 3,       # 3: 线3计数
            'count_rate': 4,        # 4: 计数率
            'reset_counter': 10,    # 10: 重置计数器（写入1触发）
            'start_capture': 11,    # 11: 开始采集（写入1触发）
            'stop_capture': 12,     # 12: 停止采集（写入1触发）
            
            # 输入寄存器（只读）
            'system_status': 0,     # 0: 系统状态（0=正常,1=警告,2=错误）
            'camera_status': 1,     # 1: 摄像头状态（0=断开,1=连接）
            'fps': 2,               # 2: 当前FPS
            'cpu_usage': 3,         # 3: CPU使用率
            'memory_usage': 4,      # 4: 内存使用率
            'disk_usage': 5,        # 5: 磁盘使用率
            'brightness': 6         # 6: 画面亮度
        }
        
        # 线程
        self.modbus_thread: Optional[threading.Thread] = None
        self.http_thread: Optional[threading.Thread] = None
        self.tcp_thread: Optional[threading.Thread] = None
        
    def set_callbacks(self, on_count=None, on_command=None):
        """设置回调函数"""
        self.on_count_callback = on_count
        self.on_command_callback = on_command
    
    def configure_modbus(self, enabled: bool = None, mode: str = None, port: int = None,
                        baudrate: int = None, parity: str = None, stopbits: int = None):
        """配置Modbus"""
        if enabled is not None:
            self.modbus_config['enabled'] = enabled
        if mode is not None:
            self.modbus_config['mode'] = mode
        if port is not None:
            self.modbus_config['port'] = port
        if baudrate is not None:
            self.modbus_config['baudrate'] = baudrate
        if parity is not None:
            self.modbus_config['parity'] = parity
        if stopbits is not None:
            self.modbus_config['stopbits'] = stopbits
    
    def configure_http(self, enabled: bool = None, port: int = None, api_key: str = None):
        """配置HTTP API"""
        if enabled is not None:
            self.http_config['enabled'] = enabled
        if port is not None:
            self.http_config['port'] = port
        if api_key is not None:
            self.http_config['api_key'] = api_key
    
    def configure_tcp(self, enabled: bool = None, port: int = None):
        """配置TCP Socket"""
        if enabled is not None:
            self.tcp_config['enabled'] = enabled
        if port is not None:
            self.tcp_config['port'] = port
    
    def start_all(self):
        """启动所有已启用的服务"""
        if self.modbus_config['enabled'] and not self.modbus_running:
            self.start_modbus_server()
        
        if self.http_config['enabled'] and not self.http_running:
            self.start_http_server()
        
        if self.tcp_config['enabled'] and not self.tcp_running:
            self.start_tcp_server()
        
        # 启动数据更新线程
        threading.Thread(target=self._update_data_loop, daemon=True).start()
    
    def stop_all(self):
        """停止所有服务"""
        self.modbus_running = False
        self.http_running = False
        self.tcp_running = False
        
        # 等待线程结束
        if self.modbus_thread and self.modbus_thread.is_alive():
            self.modbus_thread.join(timeout=5)
        
        if self.http_thread and self.http_thread.is_alive():
            self.http_thread.join(timeout=5)
        
        if self.tcp_thread and self.tcp_thread.is_alive():
            self.tcp_thread.join(timeout=5)
    
    def start_modbus_server(self):
        """启动Modbus服务器"""
        if self.modbus_running:
            return
        
        self.modbus_running = True
        self.modbus_thread = threading.Thread(target=self._run_modbus_server, daemon=True)
        self.modbus_thread.start()
        logging.info(f"Modbus服务器已启动，模式: {self.modbus_config['mode']}, 端口: {self.modbus_config['port']}")
    
    def _run_modbus_server(self):
        """运行Modbus服务器"""
        try:
            # 模拟Modbus服务器运行
            logging.info("Modbus服务器模拟运行中...")
            while self.modbus_running:
                time.sleep(1)
                
        except Exception as e:
            logging.error(f"Modbus服务器运行错误: {e}")
            self.modbus_running = False
    
    def start_http_server(self):
        """启动HTTP API服务器"""
        if self.http_running:
            return
        
        self.http_running = True
        self.http_thread = threading.Thread(target=self._run_http_server, daemon=True)
        self.http_thread.start()
        logging.info(f"HTTP API服务器已启动，端口: {self.http_config['port']}")
    
    def _run_http_server(self):
        """运行HTTP服务器"""
        adapter = self
        
        class RequestHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                # API密钥验证
                api_key = self.headers.get('X-API-Key', '')
                if adapter.http_config['api_key'] and api_key != adapter.http_config['api_key']:
                    self.send_error(401, "Unauthorized")
                    return
                
                if self.path == '/api/status':
                    # 获取系统状态
                    status = adapter._get_system_status()
                    self._send_json(status)
                
                elif self.path == '/api/counts':
                    # 获取计数数据
                    counts = adapter.counter.get_counts() if adapter.counter else {}
                    self._send_json(counts)
                
                elif self.path == '/api/records':
                    # 获取最近记录
                    records = adapter.db.get_recent_records(100) if adapter.db else []
                    self._send_json(records)
                
                elif self.path == '/api/camera/status':
                    # 获取摄像头状态
                    status = adapter.camera_manager.get_status() if adapter.camera_manager else {}
                    self._send_json(status)
                
                else:
                    self.send_error(404, "Not Found")
            
            def do_POST(self):
                # API密钥验证
                api_key = self.headers.get('X-API-Key', '')
                if adapter.http_config['api_key'] and api_key != adapter.http_config['api_key']:
                    self.send_error(401, "Unauthorized")
                    return
                
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                if self.path == '/api/reset':
                    # 重置计数器
                    if adapter.counter:
                        adapter.counter.reset()
                    self._send_json({'status': 'success', 'message': 'Counter reset'})
                
                elif self.path == '/api/command':
                    # 执行命令
                    command = data.get('command', '')
                    params = data.get('params', {})
                    
                    if adapter.on_command_callback:
                        result = adapter.on_command_callback(command, params)
                        self._send_json({'status': 'success', 'result': result})
                    else:
                        self._send_json({'status': 'error', 'message': 'No command handler'})
                
                else:
                    self.send_error(404, "Not Found")
            
            def _send_json(self, data):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            
            def log_message(self, format, *args):
                # 禁用默认日志
                pass
        
        try:
            with socketserver.TCPServer(("", self.http_config['port']), RequestHandler) as httpd:
                while self.http_running:
                    httpd.handle_request()
        except Exception as e:
            logging.error(f"HTTP服务器运行错误: {e}")
            self.http_running = False
    
    def start_tcp_server(self):
        """启动TCP Socket服务器"""
        if self.tcp_running:
            return
        
        self.tcp_running = True
        self.tcp_thread = threading.Thread(target=self._run_tcp_server, daemon=True)
        self.tcp_thread.start()
        logging.info(f"TCP服务器已启动，端口: {self.tcp_config['port']}")
    
    def _run_tcp_server(self):
        """运行TCP服务器"""
        import socket
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.tcp_config['port']))
        server_socket.listen(5)
        server_socket.settimeout(1)
        
        clients = []
        
        while self.tcp_running:
            try:
                client_socket, addr = server_socket.accept()
                clients.append(client_socket)
                logging.info(f"TCP客户端连接: {addr}")
                
                # 处理客户端
                client_thread = threading.Thread(
                    target=self._handle_tcp_client,
                    args=(client_socket,),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"TCP服务器错误: {e}")
                break
        
        # 关闭所有连接
        for client in clients:
            try:
                client.close()
            except:
                pass
        
        server_socket.close()
        self.tcp_running = False
    
    def _handle_tcp_client(self, client_socket):
        """处理TCP客户端连接"""
        buffer = b''
        while self.tcp_running:
            try:
                data = client_socket.recv(self.tcp_config['buffer_size'])
                if not data:
                    break
                
                buffer += data
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        message = json.loads(line.decode('utf-8'))
                        response = self._process_tcp_command(message)
                        client_socket.send((json.dumps(response) + '\n').encode('utf-8'))
                    except json.JSONDecodeError:
                        response = {'status': 'error', 'message': 'Invalid JSON'}
                        client_socket.send((json.dumps(response) + '\n').encode('utf-8'))
                        
            except Exception as e:
                logging.error(f"TCP客户端错误: {e}")
                break
        
        client_socket.close()
        logging.info("TCP客户端断开连接")
    
    def _process_tcp_command(self, message: Dict) -> Dict:
        """处理TCP命令"""
        command = message.get('command', '')
        
        if command == 'get_status':
            return self._get_system_status()
        
        elif command == 'get_counts':
            return self.counter.get_counts() if self.counter else {}
        
        elif command == 'reset_counter':
            if self.counter:
                self.counter.reset()
            return {'status': 'success'}
        
        elif command == 'get_recent_records':
            limit = message.get('limit', 100)
            return self.db.get_recent_records(limit) if self.db else []
        
        return {'status': 'error', 'message': 'Unknown command'}
    
    def _get_system_status(self) -> Dict:
        """获取完整系统状态"""
        status = {
            'timestamp': int(time.time() * 1000),
            'system': self.system_monitor.get_system_status() if self.system_monitor else {},
            'camera': self.camera_manager.get_status() if self.camera_manager else {},
            'counts': self.counter.get_counts() if self.counter else {},
            'abnormal': self.counter.get_abnormal_status() if self.counter else {}
        }
        return status
    
    def _update_data_loop(self):
        """定期更新Modbus等寄存器数据"""
        while True:
            try:
                if self.modbus_running:
                    self._update_modbus_registers()
                
                # 每秒更新一次
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"更新数据失败: {e}")
                time.sleep(1)
    
    def _update_modbus_registers(self):
        """更新Modbus寄存器数据"""
        if not self.counter or not self.system_monitor or not self.camera_manager:
            return
        
        try:
            # 获取上下文
            from pymodbus.server import ServerAsyncStop
            from pymodbus.datastore import ModbusServerContext
            
            # 更新保持寄存器
            counts = self.counter.get_counts()
            count_rate = self.counter.get_count_rate()
            
            values = [
                int(counts['total']),          # 0: 总计数
                int(counts['by_line'][0]),     # 1: 线1计数
                int(counts['by_line'][1]),     # 2: 线2计数
                int(counts['by_line'][2]),     # 3: 线3计数
                int(count_rate)                # 4: 计数率
            ]
            
            # 更新输入寄存器
            system_status = self.system_monitor.get_system_status()
            camera_status = self.camera_manager.get_status()
            abnormal = self.counter.get_abnormal_status()
            
            sys_state = 0  # 正常
            if any(abnormal.values()):
                sys_state = 1  # 警告
            if not camera_status['connected'] or system_status.get('memory_usage', 0) > 90:
                sys_state = 2  # 错误
            
            input_values = [
                sys_state,                            # 0: 系统状态
                1 if camera_status['connected'] else 0,  # 1: 摄像头状态
                int(camera_status.get('current_fps', 0)),  # 2: FPS
                int(system_status.get('cpu_usage', 0)),   # 3: CPU使用率
                int(system_status.get('memory_usage', 0)),  # 4: 内存使用率
                int(system_status.get('disk_usage', 0)),   # 5: 磁盘使用率
                int(camera_status.get('brightness', 0))    # 6: 亮度
            ]
            
            # TODO: 写入到Modbus寄存器
            # 这里需要根据实际的Modbus服务器实现来更新寄存器
            
        except Exception as e:
            logging.debug(f"更新Modbus寄存器失败: {e}")
    
    def notify_count_event(self, event: Dict):
        """通知计数事件到所有已连接的客户端"""
        # 可以在这里实现事件推送逻辑
        pass
    
    def get_status(self) -> Dict:
        """获取协议适配器状态"""
        return {
            'modbus': {
                'enabled': self.modbus_config['enabled'],
                'running': self.modbus_running,
                'port': self.modbus_config['port'],
                'mode': self.modbus_config['mode']
            },
            'http': {
                'enabled': self.http_config['enabled'],
                'running': self.http_running,
                'port': self.http_config['port']
            },
            'tcp': {
                'enabled': self.tcp_config['enabled'],
                'running': self.tcp_running,
                'port': self.tcp_config['port']
            }
        }