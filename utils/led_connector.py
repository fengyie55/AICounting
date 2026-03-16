import serial
import time
import yaml
import threading
from queue import Queue

class LEDConnector:
    def __init__(self, config_path="config/settings.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.enabled = self.config['led']['enabled']
        self.port = self.config['led']['port']
        self.baud_rate = self.config['led']['baud_rate']
        self.update_interval = self.config['led']['update_interval']
        
        self.ser = None
        self.connected = False
        self.queue = Queue()
        self.running = False
        self.thread = None
        
        if self.enabled:
            self.connect()
    
    def connect(self):
        """
        连接LED看板
        """
        if not self.enabled:
            return False
        
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
            
            if self.ser.is_open:
                self.connected = True
                self.running = True
                self.thread = threading.Thread(target=self._send_loop, daemon=True)
                self.thread.start()
                print(f"LED看板连接成功: {self.port}")
                return True
            else:
                print(f"LED看板连接失败: 无法打开端口 {self.port}")
                return False
                
        except Exception as e:
            print(f"LED看板连接错误: {str(e)}")
            self.connected = False
            return False
    
    def disconnect(self):
        """
        断开连接
        """
        self.running = False
        if self.thread:
            self.thread.join()
        
        if self.ser and self.ser.is_open:
            self.ser.close()
        
        self.connected = False
        print("LED看板已断开连接")
    
    def update_count(self, total, up=0, down=0):
        """
        更新计数显示
        :param total: 总计数
        :param up: 向上计数
        :param down: 向下计数
        """
        if not self.enabled or not self.connected:
            return
        
        # 将数据加入发送队列
        data = {
            'total': total,
            'up': up,
            'down': down,
            'timestamp': time.time()
        }
        self.queue.put(data)
    
    def _send_loop(self):
        """
        发送数据循环
        """
        last_send_time = 0
        
        while self.running and self.connected:
            try:
                current_time = time.time() * 1000
                
                # 按间隔发送
                if current_time - last_send_time >= self.update_interval:
                    # 获取最新的数据
                    latest_data = None
                    while not self.queue.empty():
                        latest_data = self.queue.get()
                    
                    if latest_data:
                        self._send_data(latest_data)
                        last_send_time = current_time
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"LED发送错误: {str(e)}")
                time.sleep(1)
    
    def _send_data(self, data):
        """
        发送数据到LED看板
        这里根据实际LED看板的协议进行修改
        """
        try:
            # 示例协议：发送ASCII字符串 "TOTAL,UP,DOWN\r\n"
            message = f"T{data['total']},U{data['up']},D{data['down']}\r\n"
            self.ser.write(message.encode('ascii'))
            print(f"已发送到LED: {message.strip()}")
            
        except Exception as e:
            print(f"发送数据失败: {str(e)}")
            self.connected = False
    
    def send_custom_message(self, message):
        """
        发送自定义消息
        """
        if not self.enabled or not self.connected:
            return False
        
        try:
            self.ser.write(f"MSG:{message}\r\n".encode('gbk'))
            return True
        except Exception as e:
            print(f"发送自定义消息失败: {str(e)}")
            return False
    
    def clear_display(self):
        """
        清空显示
        """
        if not self.enabled or not self.connected:
            return False
        
        try:
            self.ser.write(b"CLR\r\n")
            return True
        except Exception as e:
            print(f"清空显示失败: {str(e)}")
            return False
    
    def is_connected(self):
        """
        检查是否已连接
        """
        return self.connected
    
    def reconnect(self):
        """
        重新连接
        """
        self.disconnect()
        return self.connect()
