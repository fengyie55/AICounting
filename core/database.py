import sqlite3
import os
import time
import datetime
from typing import List, Dict, Optional, Any
import json
import logging

class DatabaseManager:
    """数据持久化管理，支持断电自动恢复"""
    
    def __init__(self, db_path: str = "data/counting.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._backup_path = f"{db_path}.backup"
        
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 计数记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS count_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    class_id INTEGER NOT NULL,
                    class_name TEXT,
                    timestamp INTEGER NOT NULL,
                    datetime TEXT NOT NULL,
                    shift INTEGER NOT NULL,
                    line_id INTEGER DEFAULT 0,
                    batch_id TEXT,
                    product_id TEXT,
                    product_name TEXT,
                    metadata TEXT
                )
            ''')
            
            # 批次表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    product_id TEXT,
                    product_name TEXT,
                    start_time INTEGER NOT NULL,
                    end_time INTEGER,
                    status TEXT NOT NULL,
                    operator TEXT,
                    remark TEXT,
                    created_at INTEGER NOT NULL
                )
            ''')
            
            # 系统状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            
            # 操作日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp INTEGER NOT NULL,
                    ip TEXT
                )
            ''')
            
            # 异常日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    stack_trace TEXT,
                    timestamp INTEGER NOT NULL,
                    module TEXT
                )
            ''')
            
            conn.commit()
    
    def insert_count_record(self, track_id: int, direction: str, class_id: int, 
                          class_name: str = "", timestamp: int = None, 
                          shift: int = 0, line_id: int = 0, batch_id: str = None,
                          product_id: str = None, product_name: str = None,
                          metadata: Dict = None) -> int:
        """插入计数记录"""
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        
        dt = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        metadata_str = json.dumps(metadata) if metadata else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO count_records 
                (track_id, direction, class_id, class_name, timestamp, datetime, shift, line_id, 
                 batch_id, product_id, product_name, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (track_id, direction, class_id, class_name, timestamp, dt, shift, line_id,
                  batch_id, product_id, product_name, metadata_str))
            conn.commit()
            
            # 自动备份
            self._auto_backup()
            
            return cursor.lastrowid
    
    def create_batch(self, name: str, product_id: str = None, product_name: str = None,
                    operator: str = None, remark: str = None) -> str:
        """创建新批次"""
        batch_id = f"batch_{int(time.time())}"
        timestamp = int(time.time() * 1000)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO batches 
                (id, name, product_id, product_name, start_time, status, operator, remark, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (batch_id, name, product_id, product_name, timestamp, 'running', operator, remark, timestamp))
            conn.commit()
        
        # 记录操作日志
        self.insert_operation_log(
            operator=operator or "system",
            action="create_batch",
            details={
                'batch_id': batch_id,
                'batch_name': name,
                'product_id': product_id
            }
        )
        
        return batch_id
    
    def complete_batch(self, batch_id: str) -> bool:
        """完成批次"""
        timestamp = int(time.time() * 1000)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE batches 
                SET status = 'completed', end_time = ?
                WHERE id = ?
            ''', (timestamp, batch_id))
            conn.commit()
            
            if cursor.rowcount > 0:
                # 记录操作日志
                self.insert_operation_log(
                    operator="system",
                    action="complete_batch",
                    details={'batch_id': batch_id}
                )
                return True
            return False
    
    def get_current_batch(self) -> Optional[Dict]:
        """获取当前运行中的批次"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM batches 
                WHERE status = 'running'
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def list_batches(self, limit: int = 100) -> List[Dict]:
        """获取批次列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM batches
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_count_statistics(self, start_time: int = None, end_time: int = None, 
                           shift: int = None, line_id: int = None, class_id: int = None,
                           batch_id: str = None, product_id: str = None) -> Dict:
        """获取计数统计"""
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        if shift is not None:
            conditions.append("shift = ?")
            params.append(shift)
        
        if line_id is not None:
            conditions.append("line_id = ?")
            params.append(line_id)
        
        if class_id is not None:
            conditions.append("class_id = ?")
            params.append(class_id)
        
        if batch_id is not None:
            conditions.append("batch_id = ?")
            params.append(batch_id)
        
        if product_id is not None:
            conditions.append("product_id = ?")
            params.append(product_id)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 统计总数
            cursor.execute(f'''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN direction = 'up' THEN 1 ELSE 0 END) as count_up,
                    SUM(CASE WHEN direction = 'down' THEN 1 ELSE 0 END) as count_down
                FROM count_records
                WHERE {where_clause}
            ''', params)
            
            result = cursor.fetchone()
            
            # 按类别统计
            cursor.execute(f'''
                SELECT class_id, class_name, COUNT(*) as count
                FROM count_records
                WHERE {where_clause}
                GROUP BY class_id, class_name
            ''', params)
            
            class_stats = {}
            for row in cursor.fetchall():
                class_stats[row['class_id']] = {
                    'name': row['class_name'],
                    'count': row['count']
                }
            
            return {
                'total': result['total'] or 0,
                'up': result['count_up'] or 0,
                'down': result['count_down'] or 0,
                'by_class': class_stats
            }
    
    def get_recent_records(self, limit: int = 100) -> List[Dict]:
        """获取最近的计数记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM count_records
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def save_system_state(self, key: str, value: Any):
        """保存系统状态"""
        timestamp = int(time.time() * 1000)
        value_str = json.dumps(value)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, value_str, timestamp))
            conn.commit()
    
    def load_system_state(self, key: str, default: Any = None) -> Any:
        """加载系统状态"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT value FROM system_state
                WHERE key = ?
            ''', (key,))
            
            result = cursor.fetchone()
            if result:
                return json.loads(result['value'])
            return default
    
    def insert_operation_log(self, operator: str, action: str, details: Dict = None, ip: str = None):
        """插入操作日志"""
        timestamp = int(time.time() * 1000)
        details_str = json.dumps(details) if details else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO operation_logs (operator, action, details, timestamp, ip)
                VALUES (?, ?, ?, ?, ?)
            ''', (operator, action, details_str, timestamp, ip))
            conn.commit()
    
    def insert_error_log(self, level: str, message: str, stack_trace: str = None, module: str = None):
        """插入错误日志"""
        timestamp = int(time.time() * 1000)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO error_logs (level, message, stack_trace, timestamp, module)
                VALUES (?, ?, ?, ?, ?)
            ''', (level, message, stack_trace, timestamp, module))
            conn.commit()
    
    def get_logs(self, log_type: str = "operation", start_time: int = None, 
                end_time: int = None, limit: int = 100) -> List[Dict]:
        """获取日志"""
        table_map = {
            "operation": "operation_logs",
            "error": "error_logs"
        }
        
        if log_type not in table_map:
            return []
        
        table = table_map[log_type]
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT * FROM {table}
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            ''', params + [limit])
            
            return [dict(row) for row in cursor.fetchall()]
    
    def _auto_backup(self):
        """自动备份数据库"""
        try:
            if os.path.exists(self.db_path):
                import shutil
                shutil.copy2(self.db_path, self._backup_path)
        except Exception as e:
            logging.error(f"数据库备份失败: {e}")
    
    def restore_from_backup(self) -> bool:
        """从备份恢复数据库"""
        try:
            if os.path.exists(self._backup_path):
                import shutil
                shutil.copy2(self._backup_path, self.db_path)
                return True
        except Exception as e:
            logging.error(f"数据库恢复失败: {e}")
        return False
    
    def export_to_excel(self, export_path: str, start_time: int = None, end_time: int = None,
                       batch_id: str = None, product_id: str = None, shift: int = None) -> bool:
        """导出数据到Excel"""
        try:
            import pandas as pd
            
            conditions = []
            params = []
            
            if start_time:
                conditions.append("timestamp >= ?")
                params.append(start_time)
            
            if end_time:
                conditions.append("timestamp <= ?")
                params.append(end_time)
            
            if batch_id is not None:
                conditions.append("batch_id = ?")
                params.append(batch_id)
            
            if product_id is not None:
                conditions.append("product_id = ?")
                params.append(product_id)
            
            if shift is not None:
                conditions.append("shift = ?")
                params.append(shift)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            with sqlite3.connect(self.db_path) as conn:
                # 导出计数记录
                df_records = pd.read_sql(f'''
                    SELECT id, track_id, direction, class_id, class_name, 
                           datetime, shift, line_id, metadata
                    FROM count_records
                    WHERE {where_clause}
                    ORDER BY timestamp DESC
                ''', conn, params=params)
                
                # 导出统计数据
                stats = self.get_count_statistics(start_time, end_time)
                df_stats = pd.DataFrame([{
                    '统计项': '总计数',
                    '数值': stats['total']
                }, {
                    '统计项': '向上计数',
                    '数值': stats['up']
                }, {
                    '统计项': '向下计数',
                    '数值': stats['down']
                }])
                
                # 写入Excel
                with pd.ExcelWriter(export_path) as writer:
                    df_records.to_excel(writer, sheet_name='计数记录', index=False)
                    df_stats.to_excel(writer, sheet_name='统计数据', index=False)
                
                return True
                
        except Exception as e:
            logging.error(f"导出Excel失败: {e}")
            return False
    
    def export_to_csv(self, export_path: str, start_time: int = None, end_time: int = None,
                     batch_id: str = None, product_id: str = None, shift: int = None) -> bool:
        """导出数据到CSV"""
        try:
            import pandas as pd
            
            conditions = []
            params = []
            
            if start_time:
                conditions.append("timestamp >= ?")
                params.append(start_time)
            
            if end_time:
                conditions.append("timestamp <= ?")
                params.append(end_time)
            
            if batch_id is not None:
                conditions.append("batch_id = ?")
                params.append(batch_id)
            
            if product_id is not None:
                conditions.append("product_id = ?")
                params.append(product_id)
            
            if shift is not None:
                conditions.append("shift = ?")
                params.append(shift)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            with sqlite3.connect(self.db_path) as conn:
                # 导出计数记录
                df_records = pd.read_sql(f'''
                    SELECT id, track_id, direction, class_id, class_name, 
                           datetime, shift, line_id, batch_id, product_id, product_name, metadata
                    FROM count_records
                    WHERE {where_clause}
                    ORDER BY timestamp DESC
                ''', conn, params=params)
                
                df_records.to_csv(export_path, index=False, encoding='utf-8-sig')
                return True
                
        except Exception as e:
            logging.error(f"导出CSV失败: {e}")
            return False
    
    def export_to_pdf(self, export_path: str, start_time: int = None, end_time: int = None,
                  batch_id: str = None, product_id: str = None, shift: int = None) -> bool:
        """导出数据到PDF"""
        try:
            import pandas as pd
            from fpdf import FPDF
            import matplotlib.pyplot as plt
            
            # 先获取统计数据
            stats = self.get_count_statistics(start_time, end_time, shift, None, None, batch_id, product_id)
            
            # 创建PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            
            # 标题
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt="AI视觉计数系统统计报告", ln=True, align='C')
            pdf.ln(10)
            
            # 基本信息
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(200, 10, txt="统计信息", ln=True)
            pdf.set_font("Arial", size=12)
            pdf.cell(100, 10, txt=f"总计数: {stats['total']}", ln=False)
            pdf.cell(100, 10, txt=f"向上计数: {stats['up']}", ln=True)
            pdf.cell(100, 10, txt=f"向下计数: {stats['down']}", ln=True)
            pdf.ln(10)
            
            # 按类别统计
            if stats['by_class']:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(200, 10, txt="按类别统计", ln=True)
                pdf.set_font("Arial", size=12)
                for cls_id, cls_info in stats['by_class'].items():
                    pdf.cell(100, 10, txt=f"{cls_info['name']}: {cls_info['count']}", ln=True)
            
            # 保存PDF
            pdf.output(export_path)
            return True
            
        except Exception as e:
            logging.error(f"导出PDF失败: {e}")
            return False
    
    def clear_old_data(self, days: int = 30):
        """清理指定天数前的旧数据"""
        cutoff_time = int((time.time() - days * 86400) * 1000)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM count_records WHERE timestamp < ?', (cutoff_time,))
            cursor.execute('DELETE FROM operation_logs WHERE timestamp < ?', (cutoff_time,))
            cursor.execute('DELETE FROM error_logs WHERE timestamp < ?', (cutoff_time,))
            conn.commit()