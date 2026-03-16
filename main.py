#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI视觉计数系统 - 工业版
版本: 2.0.0
功能: 工业级稳定计数系统，支持多计数线、ROI区域、多协议对接、7×24小时运行
"""

import sys
import os
import warnings
warnings.filterwarnings("ignore")

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui.main_window import MainWindow

# 导入新增核心模块
from core.database import DatabaseManager
from core.system_monitor import SystemMonitor
from core.config_manager import ConfigManager
from core.camera_manager import CameraManager
from core.multi_line_counter import MultiLineCounter
from core.preprocessor import ImagePreprocessor
from core.protocol_adapter import IndustrialProtocolAdapter
from core.product_manager import ProductManager
from core.mes_api import MESAPIServer

def check_dependencies():
    """
    检查依赖是否安装
    """
    required_packages = [
        'cv2',
        'numpy',
        'PyQt5',
        'pandas',
        'openpyxl',
        'yaml',
        'scipy',
        'PIL',
        'serial',
        'psutil',
        'pymodbus',
        'flask',
        'flask_cors',
        'waitress'
    ]
    
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"缺少依赖包: {', '.join(missing)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def create_directories():
    """
    创建必要的目录
    """
    directories = [
        'models',
        'models/custom',
        'data',
        'data/exports',
        'data/videos',
        'temp',
        'config',
        'config/backups',
        'logs'
    ]
    
    for d in directories:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"创建目录: {d}")

def init_core_modules():
    """
    初始化核心模块
    """
    # 配置管理器
    config_manager = ConfigManager()
    print("配置管理器初始化完成")
    
    # 数据库管理器
    db = DatabaseManager()
    print("数据库管理器初始化完成")
    
    # 系统监控
    system_monitor = SystemMonitor(db=db)
    system_monitor.start()
    print("系统监控启动完成")
    
    # 摄像头管理器
    video_config = config_manager.get('video')
    camera_manager = CameraManager(
        source=video_config['source'],
        width=video_config['width'],
        height=video_config['height'],
        fps=video_config['fps']
    )
    print("摄像头管理器初始化完成")
    
    # 图像预处理器
    preprocessor = ImagePreprocessor()
    print("图像预处理器初始化完成")
    
    # 目标检测器
    from core.detector import ObjectDetector
    detector = ObjectDetector()
    print("目标检测器初始化完成")
    
    # 多线计数器
    counter = MultiLineCounter(db=db)
    print("计数器初始化完成")
    
    # 产品管理器
    product_manager = ProductManager(db=db)
    print("产品管理器初始化完成")
    
    # 工业协议适配器
    protocol_adapter = IndustrialProtocolAdapter(
        db=db,
        counter=counter,
        camera_manager=camera_manager,
        system_monitor=system_monitor
    )
    
    # 配置协议
    modbus_config = config_manager.get('protocols.modbus')
    protocol_adapter.configure_modbus(**modbus_config)
    
    http_config = config_manager.get('protocols.http')
    protocol_adapter.configure_http(**http_config)
    
    tcp_config = config_manager.get('protocols.tcp')
    protocol_adapter.configure_tcp(**tcp_config)
    
    # 启动协议服务
    protocol_adapter.start_all()
    print("工业协议适配器初始化完成")
    
    # MES API服务器
    mes_config = config_manager.get('mes_api', {})
    mes_server = MESAPIServer(
        db=db,
        counter=counter,
        product_manager=product_manager,
        camera_manager=camera_manager
    )
    
    # 配置MES API
    mes_server.configure(
        host=mes_config.get('host', '0.0.0.0'),
        port=mes_config.get('port', 8000),
        api_key=mes_config.get('api_key', ''),
        enabled=mes_config.get('enabled', False)
    )
    
    # 配置推送
    mes_server.configure_push(
        enabled=mes_config.get('push_enabled', False),
        url=mes_config.get('push_url', ''),
        interval=mes_config.get('push_interval', 1)
    )
    
    # 设置回调
    mes_server.set_callbacks(
        on_reset=counter.reset,
        on_model_switch=lambda model_path: detector.load_model(model_path) if 'detector' in locals() else None,
        on_config_update=lambda config: config_manager.update(config)
    )
    
    # 启动MES API服务
    mes_server.start()
    print("MES API服务器初始化完成")
    
    # 自动创建批次
    import time
    if config_manager.get('batch.auto_create', True):
        current_batch = db.get_current_batch()
        if not current_batch:
            current_product = product_manager.get_current_product()
            batch_name = f"批次_{time.strftime('%Y%m%d_%H%M%S')}"
            product_id = current_product['id'] if current_product else None
            product_name = current_product['name'] if current_product else None
            batch_id = db.create_batch(
                name=batch_name,
                product_id=product_id,
                product_name=product_name,
                operator="system"
            )
            print(f"自动创建批次: {batch_name} (ID: {batch_id})")
    
    # 恢复上次计数状态
    last_state = db.load_system_state('counter_state')
    if last_state:
        try:
            counter.total_count = last_state.get('total_count', 0)
            counter.line_counts = last_state.get('line_counts', [0, 0, 0])
            counter.direction_counts = last_state.get('direction_counts', {'up': 0, 'down': 0})
            print(f"恢复上次计数状态: 总计{counter.total_count}个")
        except Exception as e:
            print(f"恢复计数状态失败: {e}")
    
    # 注册系统关闭回调
    def on_shutdown():
        print("正在关闭系统...")
        
        # 保存当前计数状态
        state = {
            'total_count': counter.total_count,
            'line_counts': counter.line_counts,
            'direction_counts': counter.direction_counts,
            'saved_at': db.load_system_state('last_save_time', 0)
        }
        db.save_system_state('counter_state', state)
        db.save_system_state('last_save_time', int(time.time() * 1000))
        
        # 停止所有服务
        protocol_adapter.stop_all()
        if 'mes_server' in locals():
            mes_server.stop()
        camera_manager.stop()
        system_monitor.stop()
        
        # 自动完成当前批次
        if config_manager.get('batch.auto_complete', True):
            current_batch = db.get_current_batch()
            if current_batch:
                db.complete_batch(current_batch['id'])
                print(f"自动完成批次: {current_batch['name']}")
        
        print("系统已安全关闭")
    
    return {
        'config_manager': config_manager,
        'db': db,
        'system_monitor': system_monitor,
        'camera_manager': camera_manager,
        'preprocessor': preprocessor,
        'counter': counter,
        'protocol_adapter': protocol_adapter,
        'product_manager': product_manager,
        'mes_server': mes_server,
        'on_shutdown': on_shutdown
    }

def main():
    """
    主函数
    """
    # 检查依赖
    if not check_dependencies():
        input("按回车键退出...")
        return
    
    # 创建目录
    create_directories()
    
    # 初始化核心模块
    core_modules = init_core_modules()
    
    # 启动应用
    app = QApplication(sys.argv)
    
    # 注册关闭事件
    app.aboutToQuit.connect(core_modules['on_shutdown'])
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 定期保存状态（每分钟一次）
    save_timer = QTimer()
    save_timer.timeout.connect(lambda: core_modules['db'].save_system_state(
        'counter_state',
        {
            'total_count': core_modules['counter'].total_count,
            'line_counts': core_modules['counter'].line_counts,
            'direction_counts': core_modules['counter'].direction_counts,
            'saved_at': int(time.time() * 1000)
        }
    ))
    save_timer.start(60000)  # 60秒
    
    # 定期执行系统维护（每天凌晨3点）
    import time
    def check_maintenance():
        now = time.localtime()
        if now.tm_hour == 3 and now.tm_min == 0:
            core_modules['system_monitor'].perform_maintenance()
    
    maintenance_timer = QTimer()
    maintenance_timer.timeout.connect(check_maintenance)
    maintenance_timer.start(60000)  # 每分钟检查一次
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()