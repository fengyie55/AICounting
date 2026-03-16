import cv2
import numpy as np
import yaml
import time
from collections import defaultdict
import datetime

class ObjectCounter:
    def __init__(self, config_path="config/settings.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.line_position = self.config['counter']['line_position']
        self.direction = self.config['counter']['direction']
        self.debounce_frames = self.config['counter']['debounce_frames']
        self.duplicate_timeout = self.config['counter']['duplicate_timeout']
        
        # 计数统计
        self.count_up = 0
        self.count_down = 0
        self.total_count = 0
        
        # 跟踪目标状态
        self.track_states = {}  # track_id: {state, last_pos, count_time, frame_count}
        
        # 全局已计数ID集合，防止重复计数
        self._global_counted_ids = set()
        
        # 计数线坐标
        self.line_y = 0
        self.line_start = (0, 0)
        self.line_end = (0, 0)
        
        # 历史记录
        self.count_history = []
        
        # 班次统计
        self.shift_counts = defaultdict(int)
        self.current_shift = 0
    
    def set_line_position(self, position, frame_height):
        """
        设置计数线位置
        :param position: 0-1之间的数值，相对于视频高度
        :param frame_height: 视频帧高度
        """
        self.line_position = max(0, min(1, position))
        self.line_y = int(frame_height * self.line_position)
    
    def update(self, track_results, frame_width, frame_height):
        """
        更新计数
        :param track_results: 跟踪结果 [x1, y1, x2, y2, track_id, score, cls]
        :param frame_width: 帧宽度
        :param frame_height: 帧高度
        """
        # 更新计数线坐标
        if self.line_y == 0:
            self.set_line_position(self.line_position, frame_height)
        
        self.line_start = (0, self.line_y)
        self.line_end = (frame_width, self.line_y)
        
        current_time = time.time() * 1000  # 毫秒
        
        for track in track_results:
            x1, y1, x2, y2, track_id, score, cls = track
            track_id = int(track_id)
            
            # 计算目标中心
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # 获取目标历史状态
            if track_id not in self.track_states:
                self.track_states[track_id] = {
                    'state': 'none',  # none, above, below, counted
                    'last_pos': center_y,
                    'count_time': 0,
                    'frame_count': 0,
                    'cls': int(cls)
                }
            else:
                state = self.track_states[track_id]
                last_y = state['last_pos']
                current_y = center_y
                
                # 更新帧数
                state['frame_count'] += 1
                
                # 防抖：至少观察几帧再判断
                if state['frame_count'] < self.debounce_frames:
                    state['last_pos'] = current_y
                    continue
                
                # 判断方向
                if state['state'] == 'none':
                    # 初始化状态
                    if current_y < self.line_y:
                        state['state'] = 'above'
                    elif current_y > self.line_y:
                        state['state'] = 'below'
                
                elif state['state'] == 'above':
                    # 从上方移动到下方
                    if current_y > self.line_y:
                        # 双重防重复检查：超时 + 全局ID跟踪
                        if (current_time - state['count_time'] > self.duplicate_timeout and 
                            track_id not in self._global_counted_ids):
                            if self.direction in ['down', 'both']:
                                self.count_down += 1
                                self.total_count += 1
                                self._record_count(track_id, 'down', int(cls), current_time)
                                self._global_counted_ids.add(track_id)  # 标记为已计数
                            state['state'] = 'counted'
                            state['count_time'] = current_time
                
                elif state['state'] == 'below':
                    # 从下方移动到上方
                    if current_y < self.line_y:
                        # 双重防重复检查：超时 + 全局ID跟踪
                        if (current_time - state['count_time'] > self.duplicate_timeout and 
                            track_id not in self._global_counted_ids):
                            if self.direction in ['up', 'both']:
                                self.count_up += 1
                                self.total_count += 1
                                self._record_count(track_id, 'up', int(cls), current_time)
                                self._global_counted_ids.add(track_id)  # 标记为已计数
                            state['state'] = 'counted'
                            state['count_time'] = current_time
                
                # 更新最后位置
                state['last_pos'] = current_y
    
    def _record_count(self, track_id, direction, cls, timestamp):
        """
        记录计数事件
        """
        record = {
            'track_id': track_id,
            'direction': direction,
            'class': cls,
            'timestamp': timestamp,
            'datetime': datetime.datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S'),
            'shift': self._get_shift()
        }
        self.count_history.append(record)
        self.shift_counts[self._get_shift()] += 1
    
    def _get_shift(self):
        """
        获取当前班次
        """
        now = datetime.datetime.now()
        hour = now.hour
        
        shift_hours = sorted(self.config['data']['shift_hours'])
        for i, shift_hour in enumerate(shift_hours):
            if hour < shift_hour:
                return i
        return 0
    
    def draw_count_line(self, frame):
        """
        在帧上绘制计数线
        """
        cv2.line(frame, self.line_start, self.line_end, (0, 0, 255), 2)
        
        # 绘制计数信息
        text = f"Total: {self.total_count} | Up: {self.count_up} | Down: {self.count_down}"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        return frame
    
    def get_counts(self):
        """
        获取计数统计
        """
        return {
            'total': self.total_count,
            'up': self.count_up,
            'down': self.count_down,
            'shift': self.shift_counts.copy(),
            'history': self.count_history.copy()
        }
    
    def reset(self):
        """
        重置计数器
        """
        self.count_up = 0
        self.count_down = 0
        self.total_count = 0
        self.track_states = {}
        self.count_history = []
        self.shift_counts.clear()
        self._global_counted_ids.clear()  # 清空已计数ID
    
    def get_statistics(self, start_time=None, end_time=None):
        """
        获取指定时间范围内的统计数据
        """
        if start_time is None and end_time is None:
            return self.get_counts()
        
        filtered = []
        for record in self.count_history:
            ts = record['timestamp']
            if (start_time is None or ts >= start_time) and (end_time is None or ts <= end_time):
                filtered.append(record)
        
        count_up = sum(1 for r in filtered if r['direction'] == 'up')
        count_down = sum(1 for r in filtered if r['direction'] == 'down')
        
        return {
            'total': len(filtered),
            'up': count_up,
            'down': count_down,
            'records': filtered
        }
