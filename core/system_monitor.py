import logging
import os
import sys
import time
import traceback
from logging.handlers import RotatingFileHandler
import threading
from typing import Optional
import psutil

class SystemMonitor:
    """系统监控与异常自修复"""
    
    def __init__(self, log_dir: str = "logs", db = None):
        self.log_dir = log_dir
        self.db = db
        os.makedirs(log_dir, exist_ok=True)
        
        # 初始化日志系统
        self._setup_logging()
        
        # 监控状态
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 系统阈值
        self.cpu_threshold = 80.0  # CPU使用率阈值%
        self.memory_threshold = 85.0  # 内存使用率阈值%
        self.disk_threshold = 90.0  # 磁盘使用率阈值%
        self.restart_on_memory_leak = True
        
        # 状态回调
        self.on_high_cpu_callback = None
        self.on_high_memory_callback = None
        self.on_low_disk_callback = None
        self.on_restart_required_callback = None
        
        # 性能历史
        self.cpu_history = []
        self.memory_history = []
        self.disk_history = []
        
        # 进程信息
        self.process = psutil.Process()
        
        # 异常计数
        self.error_count = 0
        self.max_error_count = 10
        self.error_window = 300  # 5分钟窗口
        
    def _setup_logging(self):
        """配置日志系统"""
        # 根日志配置
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 清除已有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 运行日志（轮转，10MB一个文件，保留30个）
        run_handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'run.log'),
            maxBytes=10*1024*1024,
            backupCount=30,
            encoding='utf-8'
        )
        run_handler.setLevel(logging.INFO)
        run_handler.setFormatter(formatter)
        root_logger.addHandler(run_handler)
        
        # 错误日志
        error_handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'error.log'),
            maxBytes=10*1024*1024,
            backupCount=30,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
        
        # 控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 全局异常捕获
        sys.excepthook = self._handle_exception
        
        logging.info("系统监控初始化完成")
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """全局异常处理"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_msg = "未捕获的异常: " + ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.error(error_msg)
        
        # 记录到数据库
        if self.db:
            self.db.insert_error_log(
                level="CRITICAL",
                message=str(exc_value),
                stack_trace=error_msg,
                module="system"
            )
        
        # 错误计数
        self.error_count += 1
        if self.error_count >= self.max_error_count:
            logging.critical(f"错误次数过多（{self.error_count}次），系统需要重启")
            if self.on_restart_required_callback:
                self.on_restart_required_callback("too_many_errors")
    
    def set_callbacks(self, on_high_cpu=None, on_high_memory=None, 
                     on_low_disk=None, on_restart_required=None):
        """设置状态回调"""
        self.on_high_cpu_callback = on_high_cpu
        self.on_high_memory_callback = on_high_memory
        self.on_low_disk_callback = on_low_disk
        self.on_restart_required_callback = on_restart_required
    
    def start(self):
        """启动监控"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logging.info("系统监控已启动")
    
    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logging.info("系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        last_error_check = time.time()
        
        while self.is_running:
            try:
                # 采集系统状态
                cpu_usage = self.process.cpu_percent(interval=0.1)
                memory_info = self.process.memory_info()
                memory_usage = psutil.virtual_memory().percent
                disk_usage = psutil.disk_usage('/').percent
                
                # 保存历史
                self.cpu_history.append((time.time(), cpu_usage))
                self.memory_history.append((time.time(), memory_usage))
                self.disk_history.append((time.time(), disk_usage))
                
                # 限制历史长度
                if len(self.cpu_history) > 1000:
                    self.cpu_history = self.cpu_history[-1000:]
                if len(self.memory_history) > 1000:
                    self.memory_history = self.memory_history[-1000:]
                if len(self.disk_history) > 1000:
                    self.disk_history = self.disk_history[-1000:]
                
                # CPU过高检查
                if cpu_usage > self.cpu_threshold:
                    warning_msg = f"CPU使用率过高: {cpu_usage:.1f}% (阈值: {self.cpu_threshold}%)"
                    logging.warning(warning_msg)
                    if self.on_high_cpu_callback:
                        self.on_high_cpu_callback(cpu_usage)
                
                # 内存过高检查
                if memory_usage > self.memory_threshold:
                    warning_msg = f"内存使用率过高: {memory_usage:.1f}% (阈值: {self.memory_threshold}%)"
                    logging.warning(warning_msg)
                    
                    # 检查内存泄漏：内存持续增长
                    if len(self.memory_history) >= 10:
                        mem_trend = [m[1] for m in self.memory_history[-10:]]
                        if all(mem_trend[i] <= mem_trend[i+1] for i in range(9)) and mem_trend[-1] > self.memory_threshold + 5:
                            logging.critical("检测到内存泄漏，需要重启")
                            if self.restart_on_memory_leak and self.on_restart_required_callback:
                                self.on_restart_required_callback("memory_leak")
                    
                    if self.on_high_memory_callback:
                        self.on_high_memory_callback(memory_usage)
                
                # 磁盘空间检查
                if disk_usage > self.disk_threshold:
                    warning_msg = f"磁盘空间不足: {disk_usage:.1f}% (阈值: {self.disk_threshold}%)"
                    logging.warning(warning_msg)
                    if self.on_low_disk_callback:
                        self.on_low_disk_callback(disk_usage)
                
                # 定期清理错误计数
                if time.time() - last_error_check > self.error_window:
                    self.error_count = max(0, self.error_count - 1)
                    last_error_check = time.time()
                
                # 休眠
                time.sleep(5)
                
            except Exception as e:
                logging.error(f"监控循环错误: {e}", exc_info=True)
                time.sleep(1)
    
    def get_system_status(self) -> dict:
        """获取系统状态"""
        try:
            cpu_usage = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            
            return {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'disk_usage': disk_usage,
                'memory_rss': memory_info.rss / (1024 * 1024),  # MB
                'memory_vms': memory_info.vms / (1024 * 1024),  # MB
                'thread_count': self.process.num_threads(),
                'uptime': time.time() - self.process.create_time(),
                'error_count': self.error_count
            }
        except Exception as e:
            logging.error(f"获取系统状态失败: {e}")
            return {}
    
    def get_performance_history(self, minutes: int = 5) -> dict:
        """获取最近N分钟的性能历史"""
        cutoff_time = time.time() - minutes * 60
        
        cpu_data = [t for t in self.cpu_history if t[0] >= cutoff_time]
        memory_data = [t for t in self.memory_history if t[0] >= cutoff_time]
        disk_data = [t for t in self.disk_history if t[0] >= cutoff_time]
        
        return {
            'cpu': [{'time': t[0], 'value': t[1]} for t in cpu_data],
            'memory': [{'time': t[0], 'value': t[1]} for t in memory_data],
            'disk': [{'time': t[0], 'value': t[1]} for t in disk_data]
        }
    
    def log_operation(self, operator: str, action: str, details: dict = None):
        """记录操作日志"""
        logging.info(f"操作: {operator} - {action} - {details}")
        if self.db:
            self.db.insert_operation_log(operator, action, details)
    
    def log_error(self, level: str, message: str, stack_trace: str = None, module: str = None):
        """记录错误日志"""
        log_method = getattr(logging, level.lower(), logging.error)
        log_method(f"{message} {stack_trace or ''}")
        
        if self.db:
            self.db.insert_error_log(level, message, stack_trace, module)
    
    def export_logs(self, export_path: str, log_type: str = "all", 
                   start_time: float = None, end_time: float = None) -> bool:
        """导出日志"""
        try:
            log_files = []
            if log_type in ["all", "run"]:
                log_files.append(os.path.join(self.log_dir, 'run.log'))
            if log_type in ["all", "error"]:
                log_files.append(os.path.join(self.log_dir, 'error.log'))
            
            with open(export_path, 'w', encoding='utf-8') as outfile:
                for log_file in log_files:
                    if not os.path.exists(log_file):
                        continue
                    
                    with open(log_file, 'r', encoding='utf-8') as infile:
                        for line in infile:
                            # 时间过滤
                            if start_time or end_time:
                                try:
                                    time_str = line.split(' - ')[0]
                                    log_time = time.mktime(time.strptime(time_str, '%Y-%m-%d %H:%M:%S'))
                                    if start_time and log_time < start_time:
                                        continue
                                    if end_time and log_time > end_time:
                                        continue
                                except:
                                    pass  # 格式不对的行直接保留
                            
                            outfile.write(line)
            
            return True
        except Exception as e:
            logging.error(f"导出日志失败: {e}")
            return False
    
    def cleanup_old_logs(self, days: int = 30):
        """清理旧日志"""
        try:
            cutoff_time = time.time() - days * 86400
            
            for filename in os.listdir(self.log_dir):
                filepath = os.path.join(self.log_dir, filename)
                if os.path.isfile(filepath):
                    if os.path.getmtime(filepath) < cutoff_time:
                        os.remove(filepath)
                        logging.info(f"删除旧日志: {filename}")
            
            return True
        except Exception as e:
            logging.error(f"清理旧日志失败: {e}")
            return False
    
    def perform_maintenance(self):
        """执行系统维护"""
        logging.info("开始系统维护")
        
        # 清理旧日志
        self.cleanup_old_logs(30)
        
        # 清理数据库旧数据
        if self.db:
            self.db.clear_old_data(30)
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        logging.info("系统维护完成")
        return True