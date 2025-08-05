#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K线数据API重构
提供标准的K线数据接口，支持AKSHARE和TUSHARE双数据源
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging
import traceback
import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# TODO: KlineDataManager需要实现或从其他模块导入
# from kline_refactor import KlineDataManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建蓝图
kline_api = Blueprint('kline_api', __name__)

# 初始化K线数据管理器
# 这里需要配置Tushare token，可以从环境变量或配置文件读取
TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN', 'your_tushare_token_here')
# TODO: 需要实现KlineDataManager类
# kline_manager = KlineDataManager(tushare_token=TUSHARE_TOKEN if TUSHARE_TOKEN != 'your_tushare_token_here' else None)

@kline_api.route('/api/kline/daily/<symbol>')
def get_daily_kline(symbol):
    """
    获取日K线数据 - 暂时禁用，避免kline_manager未定义错误
    """
    return jsonify({
        'success': False,
        'message': '此接口暂时不可用，请使用 /api/stock/<symbol>/daily_history'
    }), 503

@kline_api.route('/api/kline/realtime/<symbol>')
def get_realtime_kline(symbol):
    """
    获取实时K线数据 - 暂时禁用，避免kline_manager未定义错误
    """
    return jsonify({
        'success': False,
        'message': '此接口暂时不可用，请使用 /api/stock/<symbol>/realtime'
    }), 503

@kline_api.route('/api/kline/indicators/<symbol>')
def get_technical_indicators(symbol):
    """
    获取技术指标数据
    
    Args:
        symbol: 股票代码
        
    Query Parameters:
        days: 获取天数，默认100
        indicators: 指标列表，逗号分隔，如 macd,kdj,rsi
        
    Returns:
        JSON: 技术指标数据
    """
    try:
        days = int(request.args.get('days', 100))
        limit = int(request.args.get('limit', 100))  # 支持limit参数
        indicators = request.args.get('indicators', 'macd,kdj,rsi').split(',')
        
        logger.info(f"获取技术指标: symbol={symbol}, days={days}, indicators={indicators}")
        
        # 导入app.py中的函数
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # 获取股票历史数据 - 调用现有的API
        import requests
        import json
        
        # 构建内部API调用URL
        base_url = 'http://127.0.0.1:8080'
        history_url = f"{base_url}/api/stock/{symbol}/daily_history?days={max(days, limit)}"
        
        try:
            response = requests.get(history_url, timeout=30)
            if response.status_code != 200:
                raise Exception(f"获取历史数据失败: HTTP {response.status_code}")
            
            history_data = response.json()
            if not history_data.get('success'):
                raise Exception(f"获取历史数据失败: {history_data.get('message', '未知错误')}")
            
            kline_data = history_data['data']
            if not kline_data:
                raise Exception("历史数据为空")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"内部API调用失败: {e}")
            raise Exception(f"获取历史数据失败: {str(e)}")
        
        # 转换为DataFrame进行技术指标计算
        import pandas as pd
        df = pd.DataFrame(kline_data)
        
        # 确保数据类型正确
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['vol'] = pd.to_numeric(df['vol'], errors='coerce')
        
        # 按日期排序
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 计算技术指标 - 使用app.py中的函数
        from app import calculate_macd, calculate_kdj, calculate_rsi, calculate_ema15
        
        # 计算各项技术指标
        if 'macd' in [i.strip().lower() for i in indicators]:
            df = calculate_macd(df)
        if 'kdj' in [i.strip().lower() for i in indicators]:
            df = calculate_kdj(df)
        if 'rsi' in [i.strip().lower() for i in indicators]:
            df = calculate_rsi(df)
        if 'ema15' in [i.strip().lower() for i in indicators]:
            df = calculate_ema15(df)
        
        # 限制返回的数据量
        if len(df) > limit:
            df = df.tail(limit)
        
        # 处理NaN值，避免JSON序列化问题
        import numpy as np
        df = df.replace({np.nan: None})
        df = df.where(pd.notna(df), None)
        
        # 转换回字典格式
        result_kline_data = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'kline_data': result_kline_data,
                'total_count': len(result_kline_data),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        logger.error(f"获取技术指标失败: {symbol}, 错误: {e}")
        return jsonify({
            'success': False,
            'message': f'获取技术指标失败: {str(e)}'
        }), 500

@kline_api.route('/api/kline/status')
def get_kline_status():
    """
    获取K线数据源状态
    
    Returns:
        JSON: 各数据源的状态信息
    """
    try:
        # 检查各数据源状态
        akshare_status = check_akshare_status()
        tushare_status = check_tushare_status()
        
        status_info = {
            'service_status': 'running',
            'akshare_available': akshare_status,
            'tushare_available': tushare_status,
            'preferred_source': 'akshare' if akshare_status else 'tushare' if tushare_status else 'none',
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify({
            'success': True,
            'data': status_info
        })
        
    except Exception as e:
        logger.error(f"获取K线状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取状态失败: {str(e)}'
        }), 500

def convert_to_tushare_code(symbol):
    """
    将股票代码转换为Tushare格式
    
    Args:
        symbol: 股票代码，如 000001
        
    Returns:
        str: Tushare格式代码，如 000001.SZ
    """
    if '.' in symbol:
        return symbol
    
    # 根据代码前缀判断交易所
    if symbol.startswith('6'):
        return f"{symbol}.SH"  # 上海交易所
    elif symbol.startswith(('0', '3')):
        return f"{symbol}.SZ"  # 深圳交易所
    else:
        return f"{symbol}.SZ"  # 默认深圳

def calculate_kline_stats(kline_data):
    """
    计算K线统计信息
    
    Args:
        kline_data: K线数据列表
        
    Returns:
        dict: 统计信息
    """
    if not kline_data:
        return {}
    
    try:
        closes = [float(item['close']) for item in kline_data if 'close' in item]
        volumes = [float(item.get('vol', 0)) for item in kline_data]
        
        if not closes:
            return {}
        
        return {
            'max_price': max(closes),
            'min_price': min(closes),
            'avg_price': sum(closes) / len(closes),
            'total_volume': sum(volumes),
            'avg_volume': sum(volumes) / len(volumes) if volumes else 0,
            'price_change': closes[-1] - closes[0] if len(closes) > 1 else 0,
            'price_change_percent': ((closes[-1] - closes[0]) / closes[0] * 100) if len(closes) > 1 and closes[0] != 0 else 0
        }
    except Exception as e:
        logger.error(f"计算统计信息失败: {e}")
        return {}

def check_akshare_status():
    """检查AKSHARE状态"""
    try:
        import akshare as ak
        # 尝试获取一条测试数据
        df = ak.stock_zh_a_hist(symbol='000001', period='daily', start_date='20240101', end_date='20240102')
        return not df.empty
    except Exception as e:
        logger.warning(f"AKSHARE状态检查失败: {e}")
        return False

def check_tushare_status():
    """检查TUSHARE状态"""
    try:
        # 暂时返回False，避免kline_manager未定义错误
        return False
        # if not kline_manager.pro:
        #     return False
        # # 尝试获取一条测试数据
        # df = kline_manager.pro.daily(ts_code='000001.SZ', start_date='20240101', end_date='20240102')
        # return df is not None and not df.empty
    except Exception as e:
        logger.warning(f"TUSHARE状态检查失败: {e}")
        return False

# 错误处理
@kline_api.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': '接口不存在'
    }), 404

@kline_api.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': '服务器内部错误'
    }), 500