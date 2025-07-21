"""
日志系统优化建议
用于改进股票数据处理应用的日志记录
"""

import logging
import logging.handlers
from datetime import datetime
import json
import os

class StockDataLogger:
    """股票数据专用日志记录器"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.setup_loggers()
    
    def setup_loggers(self):
        """设置不同类型的日志记录器"""
        
        # 主应用日志
        self.app_logger = self._create_logger(
            'app', 
            f'{self.log_dir}/app.log',
            logging.INFO
        )
        
        # 数据获取日志
        self.data_logger = self._create_logger(
            'data', 
            f'{self.log_dir}/data.log',
            logging.DEBUG
        )
        
        # 错误日志
        self.error_logger = self._create_logger(
            'error', 
            f'{self.log_dir}/error.log',
            logging.ERROR
        )
    
    def _create_logger(self, name, filename, level):
        """创建日志记录器"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
        
        # 文件处理器（带轮转）
        file_handler = logging.handlers.RotatingFileHandler(
            filename, maxBytes=10*1024*1024, backupCount=5
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def log_data_fetch(self, source, stock_code, data_points, success=True):
        """记录数据获取情况"""
        status = "成功" if success else "失败"
        self.data_logger.info(
            f"数据获取{status} - 来源: {source}, "
            f"股票: {stock_code}, "
            f"数据点: {data_points}"
        )
    
    def log_api_rate_limit(self, api_name, remaining_requests):
        """记录API频率限制状态"""
        self.app_logger.warning(
            f"API频率限制 - {api_name}, "
            f"剩余请求数: {remaining_requests}"
        )
    
    def log_error_with_context(self, error, context):
        """记录带上下文的错误"""
        self.error_logger.error(
            f"错误: {str(error)}, "
            f"上下文: {json.dumps(context, ensure_ascii=False)}"
        )

# 全局日志实例
stock_logger = StockDataLogger()