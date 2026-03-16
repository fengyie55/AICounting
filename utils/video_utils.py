import cv2
import numpy as np
import time
from threading import Thread
from queue import Queue

class VideoReader:
    """
    视频读取器，支持多线程读取，提高帧率
    """
    def __init__(self, source=0, width=1280, height=720):
        self.source = source
        self.width = width
        self.height = height
        
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        self.queue = Queue(maxsize=10)
        self.running = False
        self.thread = None
        
        # 读取第一帧
        self.grabbed, self.frame = self.cap.read()
    
    def start(self):
        """
        启动读取线程
        """
        if self.running:
            return
        
        self.running = True
        self.thread = Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        return self
    
    def _read_loop(self):
        """
        读取循环
        """
        while self.running:
            grabbed, frame = self.cap.read()
            if not grabbed:
                self.running = False
                break
            
            # 如果队列满了，丢弃最旧的帧
            if self.queue.full():
                try:
                    self.queue.get_nowait()
                except:
                    pass
            
            self.queue.put(frame)
        
        self.cap.release()
    
    def read(self):
        """
        读取帧
        """
        if not self.running and self.queue.empty():
            return False, None
        
        try:
            frame = self.queue.get(timeout=1)
            return True, frame
        except:
            return False, None
    
    def stop(self):
        """
        停止读取
        """
        self.running = False
        if self.thread:
            self.thread.join()
    
    def is_opened(self):
        """
        检查是否打开
        """
        return self.cap.isOpened() and self.running
    
    def get_fps(self):
        """
        获取视频帧率
        """
        return self.cap.get(cv2.CAP_PROP_FPS)


class VideoWriter:
    """
    视频写入器
    """
    def __init__(self, save_path, fps=30, width=1280, height=720):
        self.save_path = save_path
        self.fps = fps
        self.width = width
        self.height = height
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(save_path, fourcc, fps, (width, height))
        
        self.queue = Queue(maxsize=100)
        self.running = False
        self.thread = None
    
    def start(self):
        """
        启动写入线程
        """
        if self.running:
            return
        
        self.running = True
        self.thread = Thread(target=self._write_loop, daemon=True)
        self.thread.start()
        return self
    
    def _write_loop(self):
        """
        写入循环
        """
        while self.running or not self.queue.empty():
            try:
                frame = self.queue.get(timeout=1)
                self.writer.write(frame)
            except:
                continue
        
        self.writer.release()
    
    def write(self, frame):
        """
        写入帧
        """
        if not self.running:
            return False
        
        if self.queue.full():
            return False
        
        self.queue.put(frame)
        return True
    
    def stop(self):
        """
        停止写入
        """
        self.running = False
        if self.thread:
            self.thread.join()


def draw_text(frame, text, position, font_scale=1, color=(0, 255, 0), thickness=2):
    """
    在图像上绘制文字，带背景
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    
    x, y = position
    # 绘制背景
    cv2.rectangle(frame, (x, y - text_height - baseline), 
                  (x + text_width, y + baseline), (0, 0, 0), -1)
    # 绘制文字
    cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)
    
    return frame


def draw_roi(frame, roi_points, color=(0, 255, 0), thickness=2):
    """
    绘制感兴趣区域
    """
    if len(roi_points) < 2:
        return frame
    
    points = np.array(roi_points, np.int32)
    cv2.polylines(frame, [points], True, color, thickness)
    return frame


def resize_frame(frame, max_width=1280, max_height=720):
    """
    缩放帧到指定大小
    """
    h, w = frame.shape[:2]
    
    if w <= max_width and h <= max_height:
        return frame
    
    scale = min(max_width / w, max_height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


class FPSCounter:
    """
    FPS计数器
    """
    def __init__(self, average_frames=30):
        self.average_frames = average_frames
        self.frame_times = []
        self.last_time = time.time()
    
    def update(self):
        """
        更新计数
        """
        current_time = time.time()
        self.frame_times.append(current_time - self.last_time)
        self.last_time = current_time
        
        if len(self.frame_times) > self.average_frames:
            self.frame_times.pop(0)
    
    def get_fps(self):
        """
        获取当前FPS
        """
        if len(self.frame_times) == 0:
            return 0
        
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0
