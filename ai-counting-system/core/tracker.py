import numpy as np
from collections import deque
import yaml

class ByteTrack:
    def __init__(self, config_path="config/settings.yaml"):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.track_thresh = self.config['tracker']['track_thresh']
        self.track_buffer = self.config['tracker']['track_buffer']
        self.match_thresh = self.config['tracker']['match_thresh']
        self.frame_rate = self.config['tracker']['frame_rate']
        self.occlusion_threshold = self.config['tracker'].get('occlusion_threshold', 0.3)
        self.appearance_threshold = self.config['tracker'].get('appearance_threshold', 0.6)
        
        self.tracked_tracks = []
        self.lost_tracks = []
        self.removed_tracks = []
        self.max_time_lost = int(self.frame_rate / 30.0 * self.track_buffer)
        self.next_id = 1
        
        # ID复用池，避免ID无限增长
        self.id_pool = []
        self.max_reuse_id = 1000
        
        # 特征匹配器（用于减少ID切换）
        self.feature_matcher = cv2.SIFT_create()
        self.bf_matcher = cv2.BFMatcher()
        
        # 误报过滤配置
        self.min_aspect_ratio = self.config['tracker'].get('min_aspect_ratio', 0.2)
        self.max_aspect_ratio = self.config['tracker'].get('max_aspect_ratio', 5.0)
        self.min_area = self.config['tracker'].get('min_area', 100)
        self.max_area = self.config['tracker'].get('max_area', 100000)
    
    def update(self, detections, frame=None):
        """
        更新跟踪器
        :param detections: 检测结果 [x1, y1, x2, y2, score, cls]
        :param frame: 输入图像(可选)
        :return: 跟踪结果 [x1, y1, x2, y2, track_id, score, cls]
        """
        # 第一步：过滤无效检测
        valid_detections = []
        for det in detections:
            if self._is_valid_detection(det):
                valid_detections.append(det)
        detections = np.array(valid_detections) if valid_detections else np.empty((0, 6))
        
        if len(detections) == 0:
            # 没有检测结果，更新跟踪状态
            for track in self.tracked_tracks:
                track.mark_lost()
                self.lost_tracks.append(track)
            self.tracked_tracks = []
            return np.empty((0, 7))
        
        # 分离高置信度和低置信度检测
        high_detections = []
        low_detections = []
        for det in detections:
            if det[4] >= self.track_thresh:
                high_detections.append(det)
            else:
                low_detections.append(det)
        
        high_detections = np.array(high_detections) if high_detections else np.empty((0, 6))
        low_detections = np.array(low_detections) if low_detections else np.empty((0, 6))
        
        # 预测当前位置
        for track in self.tracked_tracks:
            track.predict()
        
        # 第一步匹配：高置信度检测和跟踪目标匹配
        matches, unmatched_tracks, unmatched_detections = self._match(
            self.tracked_tracks, high_detections)
        
        # 更新匹配成功的跟踪
        for track_idx, det_idx in matches:
            self.tracked_tracks[track_idx].update(high_detections[det_idx])
        
        # 第二步匹配：未匹配的跟踪和低置信度检测匹配，结合外观相似度
        remaining_tracks = [self.tracked_tracks[i] for i in unmatched_tracks]
        matches_l, unmatched_tracks_l, unmatched_detections_l = self._match(
            remaining_tracks, low_detections, thresh=0.5)
        
        # 二次验证：外观相似度检查
        verified_matches = []
        for track_idx, det_idx in matches_l:
            track = remaining_tracks[track_idx]
            det = low_detections[det_idx]
            appearance_sim = self._calculate_appearance_similarity(track, det, frame)
            if appearance_sim >= self.appearance_threshold:
                verified_matches.append((track_idx, det_idx))
        
        for track_idx, det_idx in verified_matches:
            remaining_tracks[track_idx].update(low_detections[det_idx])
        
        # 新增：跟踪ID持久化和防重复逻辑
        # 记录已经计数过的ID，避免重复计数
        if not hasattr(self, 'counted_ids'):
            self.counted_ids = set()
        
        # 限制ID池大小，防止内存泄漏
        if len(self.counted_ids) > 10000:
            self.counted_ids.clear()
        
        # 处理未匹配的跟踪目标
        for i in unmatched_tracks_l:
            track = remaining_tracks[i]
            track.mark_lost()
            self.lost_tracks.append(track)
        
        # 为未匹配的高置信度检测创建新跟踪，优先复用ID
        for i in unmatched_detections:
            det = high_detections[i]
            if det[4] >= self.track_thresh:
                # 尝试复用ID
                track_id = self._get_next_id()
                new_track = Track(track_id, det)
                self.tracked_tracks.append(new_track)
        
        # 更新丢失的跟踪
        for track in self.lost_tracks:
            if track.time_since_update > self.max_time_lost:
                track.mark_removed()
                self.removed_tracks.append(track)
        
        # 清理已删除的跟踪，回收ID
        removed_ids = []
        for track in self.lost_tracks:
            if track.time_since_update > self.max_time_lost:
                track.mark_removed()
                removed_ids.append(track.track_id)
                self.removed_tracks.append(track)
        
        # 回收ID
        for track_id in removed_ids:
            self._recycle_id(track_id)
        
        self.lost_tracks = [t for t in self.lost_tracks if not t.is_removed]
        self.removed_tracks = []
        
        # 返回当前激活的跟踪结果
        output_results = []
        for track in self.tracked_tracks:
            if not track.is_lost:
                x1, y1, x2, y2 = track.tlbr
                track_id = track.track_id
                score = track.score
                cls = track.cls
                output_results.append([x1, y1, x2, y2, track_id, score, cls])
        
        return np.array(output_results) if output_results else np.empty((0, 7))
    
    def _match(self, tracks, detections, thresh=None):
        """
        匹配跟踪目标和检测结果
        """
        if thresh is None:
            thresh = self.match_thresh
        
        if len(tracks) == 0 or len(detections) == 0:
            return [], list(range(len(tracks))), list(range(len(detections)))
        
        # 计算IOU矩阵
        iou_matrix = np.zeros((len(tracks), len(detections)), dtype=np.float32)
        for t_idx, track in enumerate(tracks):
            for d_idx, det in enumerate(detections):
                iou_matrix[t_idx, d_idx] = self._iou(track.tlbr, det[:4])
        
        # 匈牙利算法匹配
        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(-iou_matrix)
        
        matches = []
        unmatched_tracks = []
        unmatched_detections = []
        
        for t, d in zip(row_ind, col_ind):
            if iou_matrix[t, d] >= thresh:
                matches.append((t, d))
            else:
                unmatched_tracks.append(t)
                unmatched_detections.append(d)
        
        # 处理未匹配的
        for t in range(len(tracks)):
            if t not in row_ind:
                unmatched_tracks.append(t)
        
        for d in range(len(detections)):
            if d not in col_ind:
                unmatched_detections.append(d)
        
        return matches, unmatched_tracks, unmatched_detections
    
    def _calculate_appearance_similarity(self, track, detection, frame=None):
        """计算外观相似度，用于减少ID切换"""
        if frame is None:
            return 1.0
            
        # 提取目标区域
        x1, y1, x2, y2 = map(int, track.tlbr)
        track_patch = frame[max(0, y1):min(frame.shape[0], y2), 
                        max(0, x1):min(frame.shape[1], x2)]
        
        x1, y1, x2, y2 = map(int, detection[:4])
        det_patch = frame[max(0, y1):min(frame.shape[0], y2), 
                        max(0, x1):min(frame.shape[1], x2)]
        
        if track_patch.size == 0 or det_patch.size == 0:
            return 0.0
        
        # 直方图比较
        try:
            track_hist = cv2.calcHist([track_patch], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            det_hist = cv2.calcHist([det_patch], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            
            cv2.normalize(track_hist, track_hist, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(det_hist, det_hist, 0, 1, cv2.NORM_MINMAX)
            
            similarity = cv2.compareHist(track_hist, det_hist, cv2.HISTCMP_CORREL)
            return max(0, similarity)
        except:
            return 0.5
    
    def _is_valid_detection(self, detection):
        """过滤无效检测结果，减少误报"""
        x1, y1, x2, y2, score, cls = detection
        width = x2 - x1
        height = y2 - y1
        area = width * height
        
        # 面积过滤
        if area < self.min_area or area > self.max_area:
            return False
        
        # 宽高比过滤
        if width == 0 or height == 0:
            return False
        aspect_ratio = width / height if height > width else height / width
        if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
            return False
        
        return True
    
    def _iou(self, bbox1, bbox2):
        """
        计算两个边界框的IOU
        """
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        
        return intersection / (area1 + area2 - intersection + 1e-6)
    
    def _get_next_id(self):
        """获取下一个可用ID，优先复用已回收的ID"""
        if self.id_pool:
            return self.id_pool.pop(0)
        self.next_id += 1
        return self.next_id - 1
    
    def _recycle_id(self, track_id):
        """回收ID用于复用"""
        if track_id not in self.id_pool and len(self.id_pool) < self.max_reuse_id:
            self.id_pool.append(track_id)
    
    def reset(self):
        """
        重置跟踪器
        """
        self.tracked_tracks = []
        self.lost_tracks = []
        self.removed_tracks = []
        self.next_id = 1
        self.id_pool.clear()
        if hasattr(self, 'counted_ids'):
            self.counted_ids.clear()


class Track:
    def __init__(self, track_id, detection):
        self.track_id = track_id
        self.tlbr = detection[:4]  # x1, y1, x2, y2
        self.score = detection[4]
        self.cls = int(detection[5])
        self.vel = np.zeros(2)  # 速度
        self.time_since_update = 0
        self.is_lost = False
        self.is_removed = False
        
        # 历史位置
        self.positions = deque(maxlen=30)
        self.positions.append(self._get_center())
    
    def _get_center(self):
        """
        获取边界框中心坐标
        """
        return np.array([(self.tlbr[0] + self.tlbr[2]) / 2, 
                         (self.tlbr[1] + self.tlbr[3]) / 2])
    
    def predict(self):
        """
        预测下一帧位置
        """
        if len(self.positions) >= 2:
            # 计算速度
            self.vel = self.positions[-1] - self.positions[-2]
            
            # 预测新位置
            new_center = self._get_center() + self.vel
            w = self.tlbr[2] - self.tlbr[0]
            h = self.tlbr[3] - self.tlbr[1]
            
            self.tlbr = np.array([
                new_center[0] - w/2,
                new_center[1] - h/2,
                new_center[0] + w/2,
                new_center[1] + h/2
            ])
        
        self.time_since_update += 1
    
    def update(self, detection):
        """
        更新跟踪目标
        """
        self.tlbr = detection[:4]
        self.score = detection[4]
        self.cls = int(detection[5])
        self.time_since_update = 0
        self.is_lost = False
        self.positions.append(self._get_center())
    
    def mark_lost(self):
        """
        标记为丢失
        """
        self.is_lost = True
    
    def mark_removed(self):
        """
        标记为删除
        """
        self.is_removed = True
