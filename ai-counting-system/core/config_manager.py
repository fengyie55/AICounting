import yaml
import os
import time
from typing import Dict, Any, Optional
import hashlib

class ConfigManager:
    """配置管理器，支持权限控制、参数校验、配置备份"""
    
    def __init__(self, config_path="config/settings.yaml"):
        self.config_path = config_path
        self.default_config_path = "config/settings.default.yaml"
        self.backup_dir = "config/backups/"
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # 权限配置
        self.roles = {
            'operator': ['view', 'export', 'reset'],
            'admin': ['view', 'export', 'reset', 'modify_config', 'calibrate', 'manage_users']
        }
        
        # 用户配置
        self.users = {
            'admin': {
                'password_hash': self._hash_password('admin123'),  # 默认密码
                'role': 'admin',
                'created_at': time.time()
            },
            'operator': {
                'password_hash': self._hash_password('operator123'),  # 默认密码
                'role': 'operator',
                'created_at': time.time()
            }
        }
        
        # 当前登录用户
        self.current_user: Optional[Dict] = None
        
        # 加载配置
        self.config = self._load_config()
        self._save_default_config()
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                # 合并默认配置
                default_config = self._get_default_config()
                config = self._merge_config(default_config, config)
                return config
            else:
                # 使用默认配置
                default_config = self._get_default_config()
                self._save_config(default_config)
                return default_config
        except Exception as e:
            print(f"加载配置失败: {e}，使用默认配置")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'system': {
                'version': '2.0.0',
                'language': 'zh-CN',
                'theme': 'light',
                'auto_start': False,
                'auto_login': False,
                'session_timeout': 30  # 分钟
            },
            'detection': {
                'model_path': 'models/yolov8n.pt',
                'conf_threshold': 0.5,
                'iou_threshold': 0.5,
                'device': 'cpu',
                'img_size': 640,
                'auto_adjust_threshold': True  # 自动调整阈值
            },
            'tracker': {
                'track_thresh': 0.5,
                'track_buffer': 30,
                'match_thresh': 0.8,
                'frame_rate': 30,
                'max_track_id': 10000
            },
            'counter': {
                'count_lines': [
                    {
                        'id': 0,
                        'position': 0.5,
                        'direction': 'both',
                        'enabled': True,
                        'name': '计数线1'
                    },
                    {
                        'id': 1,
                        'position': 0.3,
                        'direction': 'both',
                        'enabled': False,
                        'name': '计数线2'
                    },
                    {
                        'id': 2,
                        'position': 0.7,
                        'direction': 'both',
                        'enabled': False,
                        'name': '计数线3'
                    }
                ],
                'debounce_frames': 5,
                'duplicate_timeout': 1000,
                'region_tolerance': 5,
                'multi_line_mode': 'independent'  # independent / sequential
            },
            'training': {
                'epochs': 20,
                'batch_size': 2,
                'img_size': 640,
                'workers': 2,
                'auto_annotate': True,
                'save_path': 'models/custom/',
                'augmentation': True
            },
            'video': {
                'source': 0,
                'fps': 30,
                'width': 1280,
                'height': 720,
                'save_video': False,
                'save_path': 'data/videos/',
                'auto_exposure': True,
                'auto_gain': True,
                'auto_white_balance': True
            },
            'data': {
                'save_count': True,
                'save_interval': 1,  # 实时保存（秒）
                'export_path': 'data/exports/',
                'shift_hours': [8, 16, 24],
                'auto_backup': True,
                'backup_interval': 3600  # 自动备份间隔（秒）
            },
            'alarm': {
                'enabled': True,
                'sound_enabled': True,
                'popup_enabled': True,
                'led_enabled': False,
                'no_material_timeout': 30,  # 无料报警超时（秒）
                'blocked_threshold': 2.0,  # 堵料阈值（平均计数率倍数）
                'low_count_rate_threshold': 10,  # 低计数率阈值（个/分钟）
                'alarm_cooldown': 60  # 报警冷却时间（秒）
            },
            'protocols': {
                'modbus': {
                    'enabled': False,
                    'mode': 'tcp',
                    'port': 502,
                    'baudrate': 9600,
                    'parity': 'N',
                    'stopbits': 1
                },
                'http': {
                    'enabled': False,
                    'port': 8080,
                    'api_key': ''
                },
                'tcp': {
                    'enabled': False,
                    'port': 9000
                }
            },
            'maintenance': {
                'auto_maintenance': True,
                'maintenance_time': '03:00',  # 自动维护时间
                'log_retention_days': 30,
                'data_retention_days': 90
            }
        }
    
    def _merge_config(self, default: Dict, custom: Dict) -> Dict:
        """合并配置，递归更新"""
        for key, value in default.items():
            if key not in custom:
                custom[key] = value
            elif isinstance(value, dict) and isinstance(custom[key], dict):
                custom[key] = self._merge_config(value, custom[key])
        return custom
    
    def _save_config(self, config: Dict):
        """保存配置到文件"""
        try:
            # 先备份当前配置
            self._backup_config()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            self.config = config
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def _save_default_config(self):
        """保存默认配置文件"""
        if not os.path.exists(self.default_config_path):
            try:
                with open(self.default_config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self._get_default_config(), f, default_flow_style=False, allow_unicode=True)
            except Exception as e:
                print(f"保存默认配置失败: {e}")
    
    def _backup_config(self):
        """备份配置文件"""
        if os.path.exists(self.config_path):
            try:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(self.backup_dir, f"settings_{timestamp}.yaml")
                import shutil
                shutil.copy2(self.config_path, backup_path)
                
                # 只保留最近10个备份
                backups = sorted([f for f in os.listdir(self.backup_dir) if f.startswith('settings_')])
                if len(backups) > 10:
                    for old_backup in backups[:-10]:
                        os.remove(os.path.join(self.backup_dir, old_backup))
                        
            except Exception as e:
                print(f"备份配置失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置项（需要管理员权限）"""
        if not self.has_permission('modify_config'):
            return False, "需要管理员权限"
        
        keys = key.split('.')
        config = self.config
        try:
            for k in keys[:-1]:
                config = config[k]
            config[keys[-1]] = value
            return self._save_config(self.config), "保存成功"
        except (KeyError, TypeError):
            return False, "配置项不存在"
    
    def update_config(self, updates: Dict) -> tuple[bool, str]:
        """批量更新配置"""
        if not self.has_permission('modify_config'):
            return False, "需要管理员权限"
        
        try:
            def update_recursive(config, updates):
                for key, value in updates.items():
                    if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                        update_recursive(config[key], value)
                    else:
                        config[key] = value
            
            update_recursive(self.config, updates)
            return self._save_config(self.config), "配置更新成功"
        except Exception as e:
            return False, f"更新配置失败: {e}"
    
    def reset_to_default(self) -> tuple[bool, str]:
        """重置为默认配置"""
        if not self.has_permission('modify_config'):
            return False, "需要管理员权限"
        
        try:
            default_config = self._get_default_config()
            self._save_config(default_config)
            return True, "已重置为默认配置"
        except Exception as e:
            return False, f"重置配置失败: {e}"
    
    def login(self, username: str, password: str) -> tuple[bool, str]:
        """用户登录"""
        if username not in self.users:
            return False, "用户名不存在"
        
        user = self.users[username]
        if user['password_hash'] != self._hash_password(password):
            return False, "密码错误"
        
        self.current_user = {
            'username': username,
            'role': user['role'],
            'login_time': time.time()
        }
        return True, f"登录成功，欢迎 {username}"
    
    def logout(self):
        """用户登出"""
        self.current_user = None
    
    def change_password(self, username: str, old_password: str, new_password: str) -> tuple[bool, str]:
        """修改密码"""
        if username not in self.users:
            return False, "用户名不存在"
        
        user = self.users[username]
        if user['password_hash'] != self._hash_password(old_password):
            return False, "旧密码错误"
        
        # 密码强度校验
        if len(new_password) < 6:
            return False, "密码长度至少6位"
        
        user['password_hash'] = self._hash_password(new_password)
        return True, "密码修改成功"
    
    def has_permission(self, permission: str) -> bool:
        """检查当前用户是否有指定权限"""
        if not self.current_user:
            return False
        
        role = self.current_user['role']
        return permission in self.roles.get(role, [])
    
    def get_current_user(self) -> Optional[Dict]:
        """获取当前登录用户"""
        if not self.current_user:
            return None
        
        # 检查会话超时
        if time.time() - self.current_user['login_time'] > self.get('system.session_timeout', 30) * 60:
            self.logout()
            return None
        
        return self.current_user
    
    def calibrate_system(self, frame) -> tuple[bool, str, Dict]:
        """一键校准系统参数"""
        if not self.has_permission('calibrate'):
            return False, "需要管理员权限", {}
        
        try:
            import cv2
            import numpy as np
            
            # 计算亮度
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            avg_brightness = gray.mean()
            
            # 自动调整检测阈值
            conf_threshold = 0.5
            if avg_brightness < 50 or avg_brightness > 200:
                conf_threshold = 0.4  # 光照不好时降低阈值
            
            # 自动计算最佳计数线位置（中间偏下）
            line_position = 0.6
            
            # 自动调整帧率
            fps = self.get('video.fps', 30)
            
            calibration_result = {
                'brightness': avg_brightness,
                'recommended_conf_threshold': conf_threshold,
                'recommended_line_position': line_position,
                'fps': fps
            }
            
            # 应用推荐参数
            self.set('detection.conf_threshold', conf_threshold)
            self.set('counter.count_lines[0].position', line_position)
            
            return True, "校准完成", calibration_result
            
        except Exception as e:
            return False, f"校准失败: {e}", {}
    
    def get_config_summary(self) -> Dict:
        """获取配置摘要（用于显示）"""
        return {
            'system': {
                'version': self.get('system.version'),
                'theme': self.get('system.theme'),
                'language': self.get('system.language')
            },
            'detection': {
                'model': os.path.basename(self.get('detection.model_path')),
                'conf_threshold': self.get('detection.conf_threshold'),
                'device': self.get('detection.device')
            },
            'counter': {
                'line_count': sum(1 for line in self.get('counter.count_lines') if line['enabled']),
                'debounce_frames': self.get('counter.debounce_frames'),
                'duplicate_timeout': self.get('counter.duplicate_timeout')
            },
            'video': {
                'source': self.get('video.source'),
                'resolution': f"{self.get('video.width')}x{self.get('video.height')}",
                'fps': self.get('video.fps')
            },
            'protocols': {
                'modbus_enabled': self.get('protocols.modbus.enabled'),
                'http_enabled': self.get('protocols.http.enabled'),
                'tcp_enabled': self.get('protocols.tcp.enabled')
            }
        }
    
    def export_config(self, export_path: str) -> bool:
        """导出配置文件"""
        try:
            import shutil
            shutil.copy2(self.config_path, export_path)
            return True
        except Exception as e:
            print(f"导出配置失败: {e}")
            return False
    
    def import_config(self, import_path: str) -> tuple[bool, str]:
        """导入配置文件"""
        if not self.has_permission('modify_config'):
            return False, "需要管理员权限"
        
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = yaml.safe_load(f)
            
            # 验证配置格式
            default_config = self._get_default_config()
            merged_config = self._merge_config(default_config, imported_config)
            
            self._save_config(merged_config)
            return True, "配置导入成功"
            
        except Exception as e:
            return False, f"导入配置失败: {e}"