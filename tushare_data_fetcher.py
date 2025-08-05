#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare数据获取器
严格按照官方文档 https://tushare.pro/document/2?doc_id=27 的输出参数格式
"""

import tushare as ts
import pandas as pd
import os
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TushareDataFetcher:
    def __init__(self, pro_api=None):
        """初始化Tushare API"""
        if pro_api is not None:
            self.pro = pro_api
        else:
            self.token = os.getenv('TUSHARE_TOKEN')
            if not self.token:
                raise ValueError("请设置TUSHARE_TOKEN环境变量")
            
            ts.set_token(self.token)
            self.pro = ts.pro_api()
        logger.info("Tushare API初始化完成")
    
    def get_daily_data(self, ts_code, start_date=None, end_date=None, days=None):
        """
        获取A股日线行情数据
        严格按照Tushare官方文档的输出参数格式
        
        Args:
            ts_code (str): 股票代码，如 '300354.SZ'
            start_date (str): 开始日期 YYYYMMDD
            end_date (str): 结束日期 YYYYMMDD  
            days (int): 获取最近N天数据（如果指定，则忽略start_date和end_date）
            
        Returns:
            pd.DataFrame: 包含以下字段的数据框
                - ts_code: 股票代码
                - trade_date: 交易日期
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - pre_close: 昨收价【除权价，前复权】
                - change: 涨跌额
                - pct_chg: 涨跌幅
                - vol: 成交量（手）
                - amount: 成交额（千元）
        """
        try:
            logger.info(f"获取股票数据: {ts_code}")
            
            # 如果指定了天数，计算开始日期
            if days:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')  # 乘以2确保有足够的交易日
            
            # 调用Tushare API
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df.empty:
                logger.warning(f"未获取到股票 {ts_code} 的数据")
                return pd.DataFrame()
            
            # 按交易日期排序（从早到晚）
            df = df.sort_values('trade_date')
            
            # 如果指定了天数，取最近的N天
            if days and len(df) > days:
                df = df.tail(days)
            
            logger.info(f"成功获取 {len(df)} 条数据，日期范围: {df['trade_date'].iloc[0]} 到 {df['trade_date'].iloc[-1]}")
            
            # 验证数据格式
            required_columns = [
                'ts_code', 'trade_date', 'open', 'high', 'low', 'close',
                'pre_close', 'change', 'pct_chg', 'vol', 'amount'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"缺少必要字段: {missing_columns}")
                return pd.DataFrame()
            
            # 确保数据类型正确
            numeric_columns = ['open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 检查数据完整性
            logger.info(f"数据样例:")
            logger.info(f"最新数据: {df.iloc[-1].to_dict()}")
            
            return df
            
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return pd.DataFrame()
    
    def get_stock_basic_info(self, ts_code):
        """获取股票基本信息"""
        try:
            # 获取股票基本信息
            basic_info = self.pro.stock_basic(ts_code=ts_code)
            if not basic_info.empty:
                return basic_info.iloc[0].to_dict()
            return {}
        except Exception as e:
            logger.error(f"获取股票基本信息失败: {e}")
            return {}

# 全局实例
_fetcher = None

def get_fetcher():
    """获取全局Tushare数据获取器实例"""
    global _fetcher
    if _fetcher is None:
        _fetcher = TushareDataFetcher()
    return _fetcher

def get_stock_daily_data(ts_code, days=None):
    """便捷函数：获取股票日线数据"""
    fetcher = get_fetcher()
    return fetcher.get_daily_data(ts_code, days=days)

def get_stock_info(ts_code):
    """便捷函数：获取股票基本信息"""
    fetcher = get_fetcher()
    return fetcher.get_stock_basic_info(ts_code)