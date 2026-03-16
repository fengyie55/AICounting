import cv2
import time
import threading
import logging
from typing import Optional, Tuple, List
import numpy as np
from collections import deque

class CameraManager:
    """工业级摄像头管理，支持热插拔、自动重连、参数优化"""
    
    def __init__(self, source=0, width=1280, height=720, fps=30):
        self.source = source
        self.target_width = width
        self.target_height = height
        self.target_fps = fps
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.is_connected = False
        
        # 帧缓存
        self.frame_buffer = deque(maxlen=10)
        self.last_frame_time = 0
        self.fps_history = deque(maxlen=30)
        
        # 重连参数
        self.max_retry_attempts = 10
        self.retry_interval = 5  # 秒
        self.retry_count = 0
        
        # 监控线程
        self.monitor_thread: Optional[threading.Thread] = None
        self.capture_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # 硬件参数
        self.exposure = -1  # 自动
        self.gain = -1      # 自动
        self.white_balance = -1  # 自动
        
        # 状态回调
        self.on_disconnect_callback = None
        self.on_reconnect_callback = None
        self.on_fps_low_callback = None
        
        # 光照自适应
        self.brightness_history = deque(maxlen=10)
        self.auto_adjust_params = True
        
    def set_callbacks(self, on_disconnect=None, on_reconnect=None, on_fps_low=None):
        """设置状态回调函数"""
        self.on_disconnect_callback = on_disconnect
        self.on_reconnect_callback = on_reconnect
        self.on_fps_low_callback = on_fps_low
    
    def connect(self) -> bool:
        """连接摄像头"""
        try:
            with self.lock:
                if self.cap is not None:
                    self.cap.release()
                
                # 尝试不同的后端
                backends = [cv2.CAP_ANY, cv2.CAP_V4L2, cv2.CAP_DSHOW, cv2.CAP_FFMPEG]
                for backend in backends:
                    try:
                        self.cap = cv2.VideoCapture(self.source, backend)
                        if self.cap.isOpened():
                            break
                    except Exception:
                        continue
                
                if not self.cap or not self.cap.isOpened():
                    logging.error(f"无法打开摄像头: {self.source}")
                    self.is_connected = False
                    return False
                
                # 设置参数
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                
                # 应用硬件参数
                if self.exposure != -1:
                    self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
                if self.gain != -1:
                    self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
                if self.white_balance != -1:
                    self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, self.white_balance)
                
                # 读取测试帧
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    logging.error("无法读取摄像头帧")
                    self.cap.release()
                    self.cap = None
                    self.is_connected = False
                    return False
                
                self.actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
                
                logging.info(f"摄像头连接成功: {self.source}, "
                           f"分辨率: {self.actual_width}x{self.actual_height}, "
                           f"FPS: {self.actual_fps}")
                
                self.is_connected = True
                self.retry_count = 0
                return True
                
        except Exception as e:
            logging.error(f"连接摄像头失败: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开摄像头连接"""
        self.is_running = False
        self.is_connected = False
        
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=5)
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        with self.lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
        
        self.frame_buffer.clear()
        logging.info("摄像头已断开")
    
    def start(self):
        """启动摄像头捕获和监控"""
        if not self.is_connected:
            if not self.connect():
                logging.error("启动失败：无法连接摄像头")
                return False
        
        self.is_running = True
        
        # 启动捕获线程
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logging.info("摄像头已启动")
        return True
    
    def stop(self):
        """停止摄像头"""
        self.disconnect()
        logging.info("摄像头已停止")
    
    def _capture_loop(self):
        """帧捕获循环"""
        while self.is_running and self.is_connected:
            try:
                with self.lock:
                    if not self.cap or not self.cap.isOpened():
                        break
                    
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        time.sleep(0.001)
                        continue
                
                # 计算FPS
                current_time = time.time()
                if self.last_frame_time > 0:
                    fps = 1.0 / (current_time - self.last_frame_time)
                    self.fps_history.append(fps)
                self.last_frame_time = current_time
                
                # 光照自适应调整
                if self.auto_adjust_params:
                    self._adjust_illumination(frame)
                
                # 加入缓存
                self.frame_buffer.append((current_time, frame))
                
                # 控制速率
                time.sleep(max(0, 1.0/self.target_fps - 0.001))
                
            except Exception as e:
                logging.error(f"捕获帧失败: {e}")
                time.sleep(0.01)
    
    def _monitor_loop(self):
        """监控循环，检测连接状态和性能"""
        while self.is_running:
            try:
                # 检测连接状态
                if not self.is_connected or not self.cap or not self.cap.isOpened():
                    self._handle_disconnect()
                    time.sleep(self.retry_interval)
                    continue
                
                # 检测帧率
                if len(self.fps_history) >= 10:
                    avg_fps = sum(self.fps_history) / len(self.fps_history)
                    if avg_fps < self.target_fps * 0.5:  # 低于50%目标帧率
                        logging.warning(f"帧率过低: {avg_fps:.1f}/{self.target_fps}")
                        if self.on_fps_low_callback:
                            self.on_fps_low_callback(avg_fps)
                
                # 检测帧超时
                if time.time() - self.last_frame_time > 5:  # 5秒没帧
                    logging.warning("摄像头帧超时")
                    self._handle_disconnect()
                    time.sleep(self.retry_interval)
                    continue
                
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"监控循环错误: {e}")
                time.sleep(1)
    
    def _handle_disconnect(self):
        """处理断开连接"""
        if self.on_disconnect_callback:
            self.on_disconnect_callback()
        
        self.is_connected = False
        
        # 尝试重连
        while self.is_running and self.retry_count < self.max_retry_attempts:
            self.retry_count += 1
            logging.info(f"尝试重连摄像头 ({self.retry_count}/{self.max_retry_attempts})...")
            
            if self.connect():
                logging.info("摄像头重连成功")
                if self.on_reconnect_callback:
                    self.on_reconnect_callback()
                return
            
            time.sleep(self.retry_interval)
        
        logging.error(f"摄像头重连失败，已尝试{self.max_retry_attempts}次")
    
    def _adjust_illumination(self, frame):
        """光照自适应调整"""
        try:
            # 计算平均亮度
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            avg_brightness = gray.mean()
            self.brightness_history.append(avg_brightness)
            
            if len(self.brightness_history) < 5:
                return
            
            avg_brightness = sum(self.brightness_history) / len(self.brightness_history)
            
            # 亮度范围：50-200为正常
            with self.lock:
                if not self.cap or not self.cap.isOpened():
                    return
                
                if avg_brightness < 30:  # 太暗
                    current_exp = self.cap.get(cv2.CAP_PROP_EXPOSURE)
                    if current_exp < 10000:  # 增加曝光
                        self.cap.set(cv2.CAP_PROP_EXPOSURE, current_exp + 100)
                elif avg_brightness > 220:  # 太亮
                    current_exp = self.cap.get(cv2.CAP_PROP_EXPOSURE)
                    if current_exp > 10:  # 减少曝光
                        self.cap.set(cv2.CAP_PROP_EXPOSURE, current_exp - 100)
                        
        except Exception as e:
            logging.debug(f"光照调整失败: {e}")
    
    def get_frame(self, timeout: float = 0.1) -> Optional[Tuple[float, np.ndarray]]:
        """获取最新帧"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.frame_buffer:
                return self.frame_buffer[-1]
            time.sleep(0.001)
        return None
    
    def get_fps(self) -> float:
        """获取当前平均FPS"""
        if not self.fps_history:
            return 0.0
        return sum(self.fps_history) / len(self.fps_history)
    
    def get_brightness(self) -> float:
        """获取当前平均亮度"""
        if not self.brightness_history:
            return 0.0
        return sum(self.brightness_history) / len(self.brightness_history)
    
    def set_camera_params(self, exposure: int = -1, gain: int = -1, white_balance: int = -1):
        """设置摄像头硬件参数"""
        self.exposure = exposure
        self.gain = gain
        self.white_balance = white_balance
        self.auto_adjust_params = (exposure == -1 and gain == -1 and white_balance == -1)
        
        with self.lock:
            if self.cap and self.cap.isOpened():
                if exposure != -1:
                    self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
                if gain != -1:
                    self.cap.set(cv2.CAP_PROP_GAIN, gain)
                if white_balance != -1:
                    self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, white_balance)
    
    def get_camera_params(self) -> dict:
        """获取当前摄像头参数"""
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                return {}
            
            return {
                'exposure': self.cap.get(cv2.CAP_PROP_EXPOSURE),
                'gain': self.cap.get(cv2.CAP_PROP_GAIN),
                'white_balance': self.cap.get(cv2.CAP_PROP_WB_TEMPERATURE),
                'width': self.actual_width,
                'height': self.actual_height,
                'fps': self.get_fps(),
                'brightness': self.get_brightness()
            }
    
    def is_camera_connected(self) -> bool:
        """检查摄像头是否连接"""
        return self.is_connected and self.cap is not None and self.cap.isOpened()
    
    def get_status(self) -> dict:
        """获取摄像头状态"""
        return {
            'connected': self.is_camera_connected(),
            'source': self.source,
            'target_resolution': f"{self.target_width}x{self.target_height}",
            'actual_resolution': f"{getattr(self, 'actual_width', 0)}x{getattr(self, 'actual_height', 0)}",
            'target_fps': self.target_fps,
            'current_fps': self.get_fps(),
            'brightness': self.get_brightness(),
            'retry_count': self.retry_count,
            'buffer_size': len(self.frame_buffer)
        }