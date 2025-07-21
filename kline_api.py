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
    获取日K线数据
    
    Args:
        symbol: 股票代码，如 000001
        
    Query Parameters:
        days: 获取天数，默认90
        source: 数据源，akshare/tushare/auto，默认auto
        
    Returns:
        JSON: K线数据
    """
    try:
        # 获取参数
        days = int(request.args.get('days', 90))
        source = request.args.get('source', 'auto')
        
        # 参数验证
        if days <= 0 or days > 500:
            return jsonify({
                'success': False,
                'message': '天数参数错误，应在1-500之间'
            }), 400
        
        logger.info(f"获取K线数据: symbol={symbol}, days={days}, source={source}")
        
        # 根据数据源获取数据（直接使用原始数据）
        if source == 'akshare':
            df = kline_manager.get_kline_data_akshare(symbol, days)
        elif source == 'tushare':
            # 转换股票代码格式
            ts_code = convert_to_tushare_code(symbol)
            df = kline_manager.get_kline_data_tushare(ts_code, days)
        else:  # auto
            ts_code = convert_to_tushare_code(symbol)
            df = kline_manager.get_kline_data_with_fallback(symbol, ts_code, days)
        
        if df.empty:
            return jsonify({
                'success': False,
                'message': f'未获取到股票 {symbol} 的K线数据'
            }), 404
        
        # 添加技术指标
        df = kline_manager.add_technical_indicators(df)
        
        # 转换为JSON格式
        kline_data = df.to_dict('records')
        
        # 计算统计信息
        latest_data = kline_data[-1] if kline_data else {}
        stats = calculate_kline_stats(kline_data)
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'kline_data': kline_data,
                'latest': latest_data,
                'stats': stats,
                'data_source': df.iloc[0]['data_source'] if not df.empty else 'unknown',
                'total_count': len(kline_data),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        logger.error(f"获取K线数据失败: {symbol}, 错误: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'获取K线数据失败: {str(e)}'
        }), 500

@kline_api.route('/api/kline/realtime/<symbol>')
def get_realtime_kline(symbol):
    """
    获取实时K线数据（分钟级）
    
    Args:
        symbol: 股票代码
        
    Returns:
        JSON: 实时K线数据
    """
    try:
        # 这里可以实现实时K线数据获取逻辑
        # 暂时返回日K线数据的最新一条作为示例
        
        logger.info(f"获取实时K线数据: symbol={symbol}")
        
        # 获取最新的日K线数据（直接使用原始数据）
        df = kline_manager.get_kline_data_akshare(symbol, days=1)
        
        if df.empty:
            return jsonify({
                'success': False,
                'message': f'未获取到股票 {symbol} 的实时数据'
            }), 404
        
        latest_data = df.iloc[-1].to_dict()
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'realtime_data': latest_data,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        logger.error(f"获取实时K线数据失败: {symbol}, 错误: {e}")
        return jsonify({
            'success': False,
            'message': f'获取实时K线数据失败: {str(e)}'
        }), 500

@kline_api.route('/api/kline/indicators/<symbol>')
def get_technical_indicators(symbol):
    """
    获取技术指标数据
    
    Args:
        symbol: 股票代码
        
    Query Parameters:
        days: 获取天数，默认90
        indicators: 指标列表，逗号分隔，如 boll,macd,kdj,rsi
        
    Returns:
        JSON: 技术指标数据
    """
    try:
        days = int(request.args.get('days', 90))
        indicators = request.args.get('indicators', 'boll,macd').split(',')
        
        logger.info(f"获取技术指标: symbol={symbol}, days={days}, indicators={indicators}")
        
        # 获取K线数据（直接使用原始数据）
        ts_code = convert_to_tushare_code(symbol)
        df = kline_manager.get_kline_data_with_fallback(symbol, ts_code, days)
        
        if df.empty:
            return jsonify({
                'success': False,
                'message': f'未获取到股票 {symbol} 的数据'
            }), 404
        
        # 计算技术指标
        df = kline_manager.add_technical_indicators(df)
        
        # 提取指定的技术指标
        result_data = {}
        
        for indicator in indicators:
            indicator = indicator.strip().lower()
            if indicator == 'boll':
                result_data['boll'] = {
                    'upper': df['boll_upper'].tolist(),
                    'mid': df['boll_mid'].tolist(),
                    'lower': df['boll_lower'].tolist()
                }
            elif indicator == 'macd':
                result_data['macd'] = {
                    'dif': df['macd_dif'].tolist(),
                    'dea': df['macd_dea'].tolist(),
                    'histogram': df['macd_histogram'].tolist()
                }
            elif indicator == 'kdj':
                result_data['kdj'] = {
                    'k': df['kdj_k'].tolist(),
                    'd': df['kdj_d'].tolist(),
                    'j': df['kdj_j'].tolist()
                }
            elif indicator == 'rsi':
                result_data['rsi'] = df['rsi'].tolist()
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'indicators': result_data,
                'dates': df['trade_date'].tolist(),
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
    获取K线数据服务状态
    
    Returns:
        JSON: 服务状态信息
    """
    try:
        # 检查数据源状态
        akshare_status = check_akshare_status()
        tushare_status = check_tushare_status()
        
        return jsonify({
            'success': True,
            'data': {
                'service_status': 'running',
                'akshare_available': akshare_status,
                'tushare_available': tushare_status,
                'preferred_source': 'akshare' if akshare_status else 'tushare' if tushare_status else 'none',
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取服务状态失败: {str(e)}'
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
        if not kline_manager.pro:
            return False
        # 尝试获取一条测试数据
        df = kline_manager.pro.daily(ts_code='000001.SZ', start_date='20240101', end_date='20240102')
        return df is not None and not df.empty
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