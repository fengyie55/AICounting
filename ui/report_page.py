from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                            QTableWidget, QTableWidgetItem, QDateEdit, QGroupBox,
                            QFileDialog, QMessageBox, QHeaderView)
from PyQt5.QtCore import QDate
import datetime
import pandas as pd
import os

from utils.excel_exporter import ExcelExporter

class ReportPage(QWidget):
    def __init__(self, counter):
        super().__init__()
        self.counter = counter
        self.exporter = ExcelExporter()
        
        self.init_ui()
    
    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        
        # 统计信息
        stat_group = QGroupBox("今日统计")
        stat_layout = QHBoxLayout(stat_group)
        
        self.total_today_label = QLabel("<h3>今日总计数: 0</h3>")
        stat_layout.addWidget(self.total_today_label)
        
        self.shift1_label = QLabel("<h3>早班: 0</h3>")
        stat_layout.addWidget(self.shift1_label)
        
        self.shift2_label = QLabel("<h3>中班: 0</h3>")
        stat_layout.addWidget(self.shift2_label)
        
        self.shift3_label = QLabel("<h3>晚班: 0</h3>")
        stat_layout.addWidget(self.shift3_label)
        
        layout.addWidget(stat_group)
        
        # 时间筛选
        filter_group = QGroupBox("数据筛选")
        filter_layout = QHBoxLayout(filter_group)
        
        filter_layout.addWidget(QLabel("开始日期:"))
        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.start_date)
        
        filter_layout.addWidget(QLabel("结束日期:"))
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.end_date)
        
        self.query_btn = QPushButton("查询")
        self.query_btn.clicked.connect(self.query_data)
        filter_layout.addWidget(self.query_btn)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_data)
        filter_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(filter_group)
        
        # 数据表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["时间", "ID", "方向", "类别", "班次"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        
        self.export_excel_btn = QPushButton("导出Excel")
        self.export_excel_btn.clicked.connect(self.export_excel)
        export_layout.addWidget(self.export_excel_btn)
        
        self.export_csv_btn = QPushButton("导出CSV")
        self.export_csv_btn.clicked.connect(self.export_csv)
        export_layout.addWidget(self.export_csv_btn)
        
        self.clear_data_btn = QPushButton("清空历史数据")
        self.clear_data_btn.clicked.connect(self.clear_data)
        export_layout.addWidget(self.clear_data_btn)
        
        layout.addLayout(export_layout)
        
        # 初始化数据
        self.refresh_data()
    
    def refresh_data(self):
        """
        刷新数据
        """
        # 更新统计信息
        counts = self.counter.get_counts()
        self.total_today_label.setText(f"<h3>总计数: {counts['total']}</h3>")
        
        shift_counts = counts['shift']
        self.shift1_label.setText(f"<h3>早班: {shift_counts.get(0, 0)}</h3>")
        self.shift2_label.setText(f"<h3>中班: {shift_counts.get(1, 0)}</h3>")
        self.shift3_label.setText(f"<h3>晚班: {shift_counts.get(2, 0)}</h3>")
        
        # 更新表格
        self.update_table(counts['history'])
    
    def query_data(self):
        """
        查询指定时间范围的数据
        """
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        
        # 转换为时间戳
        start_ts = datetime.datetime.combine(start_date, datetime.time.min).timestamp() * 1000
        end_ts = datetime.datetime.combine(end_date, datetime.time.max).timestamp() * 1000
        
        # 查询数据
        data = self.counter.get_statistics(start_ts, end_ts)
        
        # 更新表格
        self.update_table(data['records'])
        
        QMessageBox.information(self, "查询完成", f"共找到 {len(data['records'])} 条记录")
    
    def update_table(self, records):
        """
        更新表格数据
        """
        self.table.setRowCount(len(records))
        
        for i, record in enumerate(reversed(records)):  # 最新的在前
            self.table.setItem(i, 0, QTableWidgetItem(record['datetime']))
            self.table.setItem(i, 1, QTableWidgetItem(str(record['track_id'])))
            self.table.setItem(i, 2, QTableWidgetItem("向上" if record['direction'] == 'up' else "向下"))
            self.table.setItem(i, 3, QTableWidgetItem(str(record['class'])))
            self.table.setItem(i, 4, QTableWidgetItem(self._shift_to_str(record['shift'])))
    
    def _shift_to_str(self, shift):
        """
        班次转换为字符串
        """
        if shift == 0:
            return "早班"
        elif shift == 1:
            return "中班"
        elif shift == 2:
            return "晚班"
        else:
            return "未知"
    
    def export_excel(self):
        """
        导出为Excel
        """
        if not self.counter.count_history:
            QMessageBox.warning(self, "提示", "没有数据可以导出")
            return
        
        # 选择保存路径
        default_name = f"计数数据_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "保存Excel文件", default_name, 
                                                  "Excel文件 (*.xlsx)")
        if file_path:
            try:
                self.exporter.export_to_excel(self.counter.count_history, file_path)
                QMessageBox.information(self, "成功", f"数据已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def export_csv(self):
        """
        导出为CSV
        """
        if not self.counter.count_history:
            QMessageBox.warning(self, "提示", "没有数据可以导出")
            return
        
        # 选择保存路径
        default_name = f"计数数据_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(self, "保存CSV文件", default_name, 
                                                  "CSV文件 (*.csv)")
        if file_path:
            try:
                df = pd.DataFrame(self.counter.count_history)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "成功", f"数据已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def clear_data(self):
        """
        清空历史数据
        """
        reply = QMessageBox.question(self, "确认", "确定要清空所有历史数据吗？此操作不可恢复！",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.counter.reset()
            self.refresh_data()
            QMessageBox.information(self, "成功", "数据已清空")
