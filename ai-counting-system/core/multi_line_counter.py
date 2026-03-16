import cv2
import numpy as np
import yaml
import time
from collections import defaultdict, deque
import datetime
from typing import List, Tuple, Dict, Optional
from .database import DatabaseManager

class MultiLineCounter:
    """多计数线计数器，支持最多3条独立计数线"""
    
    def __init__(self, config_path="config/settings.yaml", db: DatabaseManager = None):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.db = db
        
        # 计数线配置（最多3条）
        self.count_lines = []
        self._init_count_lines()
        
        # 全局已计数ID集合，防止重复计数
        self._global_counted_ids = set()
        self._counted_id_history = deque(maxlen=10000)  # 限制内存使用
        
        # 计数统计
        self.total_count = 0
        self.line_counts = [0, 0, 0]  # 每条线的计数
        self.direction_counts = {'up': 0, 'down': 0}
        
        # 跟踪目标状态
        self.track_states = {}  # track_id: {state, last_pos, count_time, frame_count, line_states}
        
        # 三重防重复参数
        self.debounce_frames = self.config['counter']['debounce_frames']
        self.duplicate_timeout = self.config['counter']['duplicate_timeout']
        self.region_tolerance = 5  # 像素容错
        
        # ROI区域
        self.roi_mask: Optional[np.ndarray] = None
        self.roi_points: List[Tuple[int, int]] = []
        
        # 历史记录
        self.count_history = []
        
        # 班次统计
        self.shift_counts = defaultdict(int)
        self.current_shift = 0
        
        # 类名映射
        self.class_names = {}
        
        # 异常检测
        self.last_count_time = 0
        self.count_rate_history = deque(maxlen=60)  # 1分钟计数率历史
    
    def _init_count_lines(self):
        """初始化计数线"""
        # 从配置加载或使用默认值
        if 'count_lines' in self.config['counter']:
            self.count_lines = self.config['counter']['count_lines']
        else:
            # 默认单条计数线
            self.count_lines = [{
                'id': 0,
                'position': self.config['counter']['line_position'],
                'direction': self.config['counter']['direction'],
                'enabled': True,
                'name': '计数线1'
            }]
        
        # 确保最多3条计数线
        self.count_lines = self.count_lines[:3]
        while len(self.count_lines) < 3:
            self.count_lines.append({
                'id': len(self.count_lines),
                'position': 0.3 + len(self.count_lines) * 0.2,
                'direction': 'both',
                'enabled': False,
                'name': f'计数线{len(self.count_lines)+1}'
            })
    
    def set_count_line(self, line_id: int, position: float, direction: str = 'both', 
                      enabled: bool = True, name: str = None):
        """设置计数线参数"""
        if 0 <= line_id < len(self.count_lines):
            self.count_lines[line_id].update({
                'position': max(0, min(1, position)),
                'direction': direction,
                'enabled': enabled,
                'name': name or f'计数线{line_id+1}'
            })
            # 重置该线的计数
            self.line_counts[line_id] = 0
            return True
        return False
    
    def set_roi(self, points: List[Tuple[int, int]], frame_shape: Tuple[int, int]):
        """设置ROI区域（多边形顶点）"""
        if len(points) < 3:
            self.roi_mask = None
            self.roi_points = []
            return False
        
        self.roi_points = points
        h, w = frame_shape[:2]
        self.roi_mask = np.zeros((h, w), dtype=np.uint8)
        points_np = np.array(points, np.int32)
        cv2.fillPoly(self.roi_mask, [points_np], 255)
        return True
    
    def is_in_roi(self, point: Tuple[int, int]) -> bool:
        """检查点是否在ROI区域内"""
        if self.roi_mask is None:
            return True
        
        x, y = point
        h, w = self.roi_mask.shape
        if 0 <= y < h and 0 <= x < w:
            return self.roi_mask[y, x] == 255
        return False
    
    def update(self, track_results, frame_width: int, frame_height: int) -> Dict:
        """
        更新计数
        :param track_results: 跟踪结果 [x1, y1, x2, y2, track_id, score, cls]
        :param frame_width: 帧宽度
        :param frame_height: 帧高度
        :return: 计数事件列表
        """
        current_time = time.time() * 1000  # 毫秒
        count_events = []
        
        # 更新计数线坐标
        for line in self.count_lines:
            if line['enabled']:
                line['y'] = int(frame_height * line['position'])
                line['start'] = (0, line['y'])
                line['end'] = (frame_width, line['y'])
        
        for track in track_results:
            x1, y1, x2, y2, track_id, score, cls = track
            track_id = int(track_id)
            cls = int(cls)
            
            # 计算目标中心
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            
            # 检查是否在ROI区域内
            if not self.is_in_roi((center_x, center_y)):
                continue
            
            # 获取目标历史状态
            if track_id not in self.track_states:
                self.track_states[track_id] = {
                    'state': 'none',
                    'last_pos': center_y,
                    'count_time': 0,
                    'frame_count': 0,
                    'cls': cls,
                    'line_states': [{'crossed': False, 'last_pos': center_y} for _ in self.count_lines]
                }
                continue
            
            state = self.track_states[track_id]
            last_y = state['last_pos']
            current_y = center_y
            
            # 更新帧数
            state['frame_count'] += 1
            
            # 防抖：至少观察几帧再判断
            if state['frame_count'] < self.debounce_frames:
                state['last_pos'] = current_y
                for line_state in state['line_states']:
                    line_state['last_pos'] = current_y
                continue
            
            # 检查每条计数线
            for line_idx, line in enumerate(self.count_lines):
                if not line['enabled']:
                    continue
                
                line_state = state['line_states'][line_idx]
                line_y = line['y']
                direction = line['direction']
                
                # 已计数过的跳过
                if line_state['crossed']:
                    continue
                
                last_pos = line_state['last_pos']
                
                # 判断是否跨越计数线
                crossed = False
                cross_direction = None
                
                # 从上方到下方
                if last_pos < line_y - self.region_tolerance and current_y > line_y + self.region_tolerance:
                    crossed = True
                    cross_direction = 'down'
                # 从下方到上方
                elif last_pos > line_y + self.region_tolerance and current_y < line_y - self.region_tolerance:
                    crossed = True
                    cross_direction = 'up'
                
                if crossed:
                    # 三重防重复检查
                    # 1. 全局ID检查
                    if track_id in self._global_counted_ids:
                        line_state['crossed'] = True
                        continue
                    
                    # 2. 时间窗口检查
                    if current_time - state['count_time'] < self.duplicate_timeout:
                        continue
                    
                    # 3. 方向匹配检查
                    if direction != 'both' and cross_direction != direction:
                        continue
                    
                    # 计数有效
                    self._record_count(
                        track_id=track_id,
                        direction=cross_direction,
                        cls=cls,
                        line_id=line_idx,
                        timestamp=current_time,
                        score=score
                    )
                    
                    count_events.append({
                        'track_id': track_id,
                        'direction': cross_direction,
                        'class_id': cls,
                        'class_name': self.class_names.get(cls, str(cls)),
                        'line_id': line_idx,
                        'line_name': line['name'],
                        'timestamp': current_time,
                        'score': float(score)
                    })
                    
                    # 标记为已计数
                    line_state['crossed'] = True
                    state['count_time'] = current_time
                    self._global_counted_ids.add(track_id)
                    self._counted_id_history.append(track_id)
                    
                    # 限制已计数ID集合大小
                    if len(self._global_counted_ids) > 10000:
                        oldest_id = self._counted_id_history.popleft()
                        if oldest_id in self._global_counted_ids:
                            self._global_counted_ids.remove(oldest_id)
            
            # 更新最后位置
            state['last_pos'] = current_y
            for line_state in state['line_states']:
                line_state['last_pos'] = current_y
        
        # 计算计数率
        if count_events:
            self.last_count_time = current_time
            self.count_rate_history.append(len(count_events))
        
        return count_events
    
    def _record_count(self, track_id: int, direction: str, cls: int, line_id: int, 
                     timestamp: int, score: float):
        """记录计数事件"""
        # 更新统计
        self.total_count += 1
        self.line_counts[line_id] += 1
        self.direction_counts[direction] += 1
        
        shift = self._get_shift()
        self.shift_counts[shift] += 1
        
        # 记录到历史
        record = {
            'track_id': track_id,
            'direction': direction,
            'class_id': cls,
            'class_name': self.class_names.get(cls, str(cls)),
            'line_id': line_id,
            'line_name': self.count_lines[line_id]['name'],
            'timestamp': timestamp,
            'datetime': datetime.datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S'),
            'shift': shift,
            'score': float(score)
        }
        self.count_history.append(record)
        
        # 持久化到数据库
        if self.db:
            # 获取当前批次和产品信息
            current_batch = self.db.get_current_batch()
            batch_id = current_batch['id'] if current_batch else None
            
            current_product = getattr(self, 'current_product', None)
            product_id = current_product['id'] if current_product else None
            product_name = current_product['name'] if current_product else None
            
            self.db.insert_count_record(
                track_id=track_id,
                direction=direction,
                class_id=cls,
                class_name=self.class_names.get(cls, str(cls)),
                timestamp=timestamp,
                shift=shift,
                line_id=line_id,
                batch_id=batch_id,
                product_id=product_id,
                product_name=product_name,
                metadata={'score': float(score)}
            )
    
    def _get_shift(self) -> int:
        """获取当前班次"""
        now = datetime.datetime.now()
        hour = now.hour
        
        shift_hours = sorted(self.config['data']['shift_hours'])
        for i, shift_hour in enumerate(shift_hours):
            if hour < shift_hour:
                return i
        return 0
    
    def draw_count_lines(self, frame: np.ndarray) -> np.ndarray:
        """在帧上绘制计数线"""
        # 绘制ROI区域
        if self.roi_mask is not None and len(self.roi_points) >= 3:
            points_np = np.array(self.roi_points, np.int32)
            cv2.polylines(frame, [points_np], True, (255, 0, 0), 2)
            
            # 半透明填充
            overlay = frame.copy()
            cv2.fillPoly(overlay, [points_np], (255, 0, 0))
            frame = cv2.addWeighted(overlay, 0.2, frame, 0.8, 0)
        
        # 绘制计数线
        for line in self.count_lines:
            if line['enabled']:
                color = (0, 0, 255) if line['id'] == 0 else (0, 165, 255) if line['id'] == 1 else (0, 255, 255)
                cv2.line(frame, line['start'], line['end'], color, 2)
                
                # 绘制线名称
                text = f"{line['name']}: {self.line_counts[line['id']]}"
                cv2.putText(frame, text, (10, 60 + line['id'] * 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # 绘制计数信息
        text = f"Total: {self.total_count} | Up: {self.direction_counts['up']} | Down: {self.direction_counts['down']}"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        return frame
    
    def get_counts(self) -> Dict:
        """获取计数统计"""
        return {
            'total': self.total_count,
            'by_direction': self.direction_counts.copy(),
            'by_line': self.line_counts.copy(),
            'by_shift': self.shift_counts.copy(),
            'line_info': self.count_lines.copy(),
            'history': self.count_history.copy()
        }
    
    def get_count_rate(self) -> float:
        """获取当前计数率（个/分钟）"""
        if not self.count_rate_history:
            return 0.0
        return sum(self.count_rate_history) * (60 / len(self.count_rate_history))
    
    def reset(self):
        """重置计数器"""
        self.total_count = 0
        self.line_counts = [0, 0, 0]
        self.direction_counts = {'up': 0, 'down': 0}
        self.track_states = {}
        self.count_history = []
        self.shift_counts.clear()
        self._global_counted_ids.clear()
        self._counted_id_history.clear()
        self.count_rate_history.clear()
        
        # 记录重置操作
        if self.db:
            self.db.insert_operation_log(
                operator="system",
                action="reset_counter",
                details={"reason": "manual_reset"}
            )
    
    def set_class_names(self, class_names: Dict[int, str]):
        """设置类名映射"""
        self.class_names = class_names
    
    def get_abnormal_status(self) -> Dict:
        """获取异常状态"""
        current_time = time.time() * 1000
        status = {
            'no_material': False,
            'blocked': False,
            'low_count_rate': False
        }
        
        # 无料检测：连续30秒没有计数
        if current_time - self.last_count_time > 30000 and self.total_count > 0:
            status['no_material'] = True
        
        # 堵料检测：计数率超过平均的2倍
        count_rate = self.get_count_rate()
        if len(self.count_rate_history) >= 30:
            avg_rate = sum(self.count_rate_history) / len(self.count_rate_history)
            if count_rate > avg_rate * 2 and avg_rate > 0:
                status['blocked'] = True
        
        # 计数率过低：低于正常的50%
        if count_rate < 10 and self.total_count > 100:  # 假设正常至少10个/分钟
            status['low_count_rate'] = True
        
        return status