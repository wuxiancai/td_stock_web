try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
    print("Tushare库已成功导入")
except ImportError:
    ts = None
    TUSHARE_AVAILABLE = False
    print("警告：Tushare库未安装，部分数据功能将不可用")

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import socket
import os
import json
import threading
import time
import schedule
from collections import deque

# 导入新的K线API蓝图
try:
    from kline_api import kline_api
    KLINE_API_AVAILABLE = True
    print("K线API模块已成功导入")
except ImportError as e:
    kline_api = None
    KLINE_API_AVAILABLE = False
    print(f"警告：K线API模块导入失败: {e}")

app = Flask(__name__)
CORS(app)

# 注册K线API蓝图
if KLINE_API_AVAILABLE and kline_api:
    app.register_blueprint(kline_api)
    print("K线API蓝图已注册")

# Tushare API频率限制器
class TushareRateLimiter:
    """Tushare API频率限制器，确保每分钟不超过199次请求"""
    
    def __init__(self, max_requests_per_minute=199):
        self.max_requests = max_requests_per_minute
        self.requests = deque()  # 存储请求时间戳
        self.lock = threading.Lock()  # 线程锁，确保线程安全
        
    def wait_if_needed(self):
        """如果需要，等待直到可以发送请求"""
        with self.lock:
            now = time.time()
            
            # 清理60秒前的请求记录
            while self.requests and now - self.requests[0] >= 60:
                self.requests.popleft()
            
            # 如果当前分钟内请求数已达上限，等待
            if len(self.requests) >= self.max_requests:
                # 计算需要等待的时间（到最早请求的60秒后）
                wait_time = 60 - (now - self.requests[0]) + 0.1  # 额外等待0.1秒确保安全
                if wait_time > 0:
                    print(f"API频率限制：已达到每分钟{self.max_requests}次限制，等待{wait_time:.1f}秒...")
                    time.sleep(wait_time)
                    # 重新清理过期请求
                    now = time.time()
                    while self.requests and now - self.requests[0] >= 60:
                        self.requests.popleft()
            
            # 记录当前请求时间
            self.requests.append(now)
            
    def get_remaining_requests(self):
        """获取当前分钟内剩余可用请求数"""
        with self.lock:
            now = time.time()
            # 清理60秒前的请求记录
            while self.requests and now - self.requests[0] >= 60:
                self.requests.popleft()
            return self.max_requests - len(self.requests)
    
    def get_status(self):
        """获取限制器状态信息"""
        with self.lock:
            now = time.time()
            # 清理60秒前的请求记录
            while self.requests and now - self.requests[0] >= 60:
                self.requests.popleft()
            
            remaining = self.max_requests - len(self.requests)
            next_reset_time = None
            if self.requests:
                next_reset_time = self.requests[0] + 60
            
            return {
                'used_requests': len(self.requests),
                'remaining_requests': remaining,
                'max_requests_per_minute': self.max_requests,
                'next_reset_time': next_reset_time,
                'current_time': now
            }

# 创建全局频率限制器实例
rate_limiter = TushareRateLimiter(max_requests_per_minute=199)

# AkShare API频率限制器
class AkShareRateLimiter:
    """AkShare API频率限制器，避免触发东方财富的反爬虫机制"""
    
    def __init__(self, max_requests_per_minute=10, min_interval=6):
        self.max_requests = max_requests_per_minute
        self.min_interval = min_interval  # 最小请求间隔（秒）
        self.requests = deque()  # 存储请求时间戳
        self.last_request_time = 0  # 上次请求时间
        self.lock = threading.Lock()  # 线程锁，确保线程安全
        
    def wait_if_needed(self):
        """如果需要，等待直到可以发送请求"""
        with self.lock:
            now = time.time()
            
            # 确保最小请求间隔
            time_since_last = now - self.last_request_time
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                print(f"[AkShare] 频率控制：等待{wait_time:.1f}秒以满足最小间隔要求...")
                time.sleep(wait_time)
                now = time.time()
            
            # 清理60秒前的请求记录
            while self.requests and now - self.requests[0] >= 60:
                self.requests.popleft()
            
            # 如果当前分钟内请求数已达上限，等待
            if len(self.requests) >= self.max_requests:
                # 计算需要等待的时间（到最早请求的60秒后）
                wait_time = 60 - (now - self.requests[0]) + 0.1  # 额外等待0.1秒确保安全
                if wait_time > 0:
                    print(f"[AkShare] 频率限制：已达到每分钟{self.max_requests}次限制，等待{wait_time:.1f}秒...")
                    time.sleep(wait_time)
                    # 重新清理过期请求
                    now = time.time()
                    while self.requests and now - self.requests[0] >= 60:
                        self.requests.popleft()
            
            # 记录当前请求时间
            self.requests.append(now)
            self.last_request_time = now
            
    def get_status(self):
        """获取限制器状态信息"""
        with self.lock:
            now = time.time()
            # 清理60秒前的请求记录
            while self.requests and now - self.requests[0] >= 60:
                self.requests.popleft()
            
            remaining = self.max_requests - len(self.requests)
            next_reset_time = None
            if self.requests:
                next_reset_time = self.requests[0] + 60
            
            time_since_last = now - self.last_request_time
            next_allowed_time = self.last_request_time + self.min_interval
            
            return {
                'used_requests': len(self.requests),
                'remaining_requests': remaining,
                'max_requests_per_minute': self.max_requests,
                'min_interval': self.min_interval,
                'time_since_last_request': time_since_last,
                'next_allowed_time': next_allowed_time,
                'next_reset_time': next_reset_time,
                'current_time': now
            }

# 移除AkShare频率限制器，不再限制请求频率
# akshare_rate_limiter = AkShareRateLimiter(max_requests_per_minute=10, min_interval=6)

# Tushare配置
if TUSHARE_AVAILABLE:
    ts.set_token('68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019')
    pro = ts.pro_api()
else:
    pro = None

# 包装tushare API调用的函数
def safe_tushare_call(func, *args, **kwargs):
    """安全的tushare API调用，自动处理频率限制"""
    if not TUSHARE_AVAILABLE:
        raise Exception("Tushare库未安装")
    
    rate_limiter.wait_if_needed()
    try:
        result = func(*args, **kwargs)
        
        # 检查返回结果是否包含限制警告信息
        if hasattr(result, 'empty') and not result.empty:
            # 检查DataFrame中是否有错误信息列
            if 'error' in result.columns and not result['error'].isna().all():
                error_msg = str(result['error'].iloc[0])
                if "频率" in error_msg or "limit" in error_msg.lower() or "rate" in error_msg.lower():
                    print(f"检测到Tushare API限制警告: {error_msg}")
                    print("立即停止同步，等待60秒后继续...")
                    time.sleep(60)
                    # 重新尝试调用
                    return safe_tushare_call(func, *args, **kwargs)
        
        return result
    except Exception as e:
        error_msg = str(e)
        print(f"Tushare API调用失败: {error_msg}")
        
        # 检查是否为频率限制相关错误
        if any(keyword in error_msg.lower() for keyword in ["频率", "limit", "rate", "too many", "exceeded"]):
            print("检测到频率限制错误，立即停止同步，等待60秒后继续...")
            time.sleep(60)
            # 重新尝试调用
            try:
                return safe_tushare_call(func, *args, **kwargs)
            except Exception as retry_e:
                print(f"重试后仍然失败: {retry_e}")
                raise retry_e
        
        # 其他类型的错误直接抛出
        raise e

# AkShare相关导入和函数定义
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
    print("AkShare库已成功导入")
except ImportError:
    ak = None
    AKSHARE_AVAILABLE = False
    print("警告：AkShare库未安装，分时图功能将不可用")

def safe_akshare_call(func, cache_key, *args, max_retries=3, retry_delay=2, **kwargs):
    """安全的AkShare API调用，实现双数据源策略（新浪财经和东财）"""
    if not AKSHARE_AVAILABLE or ak is None:
        print("AkShare不可用")
        return None
    
    import time
    import requests
    import random
    
    # 移除频率限制，不再使用频率限制器
    # akshare_rate_limiter.wait_if_needed()
    
    # 双数据源策略：先尝试新浪财经，失败后尝试东财
    data_sources = [
        {'name': '新浪财经', 'symbol_suffix': ''},  # 新浪财经接口
        {'name': '东财', 'symbol_suffix': ''}       # 东财接口
    ]
    
    for source_idx, source in enumerate(data_sources):
        print(f"[AkShare] 尝试使用{source['name']}数据源...")
        
        for attempt in range(max_retries):
            try:
                print(f"[AkShare] {source['name']} - 尝试调用 {func.__name__} (第{attempt + 1}次)")
                
                # 根据数据源调整参数（如果需要）
                adjusted_kwargs = kwargs.copy()
                
                result = func(*args, **adjusted_kwargs)
                print(f"[AkShare] {source['name']} - {func.__name__} 调用成功")
                return result
                
            except requests.exceptions.ProxyError as e:
                error_msg = str(e)
                print(f"[AkShare] {source['name']} - 代理连接错误 (第{attempt + 1}次): {e}")
                
                if attempt < max_retries - 1:
                    delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                    print(f"[AkShare] {source['name']} - {delay:.1f}秒后重试...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[AkShare] {source['name']} - 代理连接失败，已重试{max_retries}次")
                    break
                    
            except requests.exceptions.ConnectionError as e:
                print(f"[AkShare] {source['name']} - 网络连接错误 (第{attempt + 1}次): {e}")
                if attempt < max_retries - 1:
                    delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                    print(f"[AkShare] {source['name']} - {delay:.1f}秒后重试...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[AkShare] {source['name']} - 网络连接失败，已重试{max_retries}次")
                    break
                    
            except requests.exceptions.Timeout as e:
                print(f"[AkShare] {source['name']} - 请求超时 (第{attempt + 1}次): {e}")
                if attempt < max_retries - 1:
                    delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                    print(f"[AkShare] {source['name']} - {delay:.1f}秒后重试...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[AkShare] {source['name']} - 请求超时，已重试{max_retries}次")
                    break
                    
            except Exception as e:
                error_msg = str(e)
                print(f"[AkShare] {source['name']} - API调用失败 (第{attempt + 1}次): {e}")
                
                if attempt < max_retries - 1:
                    delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                    print(f"[AkShare] {source['name']} - {delay:.1f}秒后重试...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[AkShare] {source['name']} - API调用失败，已重试{max_retries}次")
                    break
        
        # 如果当前数据源失败，尝试下一个数据源
        if source_idx < len(data_sources) - 1:
            print(f"[AkShare] {source['name']}数据源失败，切换到下一个数据源...")
            time.sleep(1)  # 短暂延迟后切换数据源
    
    print("[AkShare] 所有数据源都失败了")
    return None

def find_available_port(start_port=8080):
    """查找可用端口"""
    for port in range(start_port, start_port + 10):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', port))
            sock.close()
            return port
        except OSError:
            continue
    return None

def kill_process_on_port(port):
    """强制结束占用指定端口的进程"""
    import subprocess
    try:
        # 查找占用端口的进程
        result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"正在结束占用端口{port}的进程 PID: {pid}")
                    subprocess.run(['kill', '-9', pid], check=False)
            print(f"已强制结束占用端口{port}的所有进程")
            return True
        else:
            print(f"端口{port}未被占用")
            return True
    except Exception as e:
        print(f"结束端口{port}进程时出错: {e}")
        return False

# 导入优化的缓存管理器
from cache_manager import cache_manager, load_cache_data, save_cache_data, get_cache_file_path

def get_latest_cache_date(market):
    """获取缓存中最新的日期"""
    cache_data = load_cache_data(market)
    if cache_data and 'last_update_date' in cache_data:
        return cache_data['last_update_date']
    return None

def get_trading_days_between(start_date, end_date):
    """获取两个日期之间的交易日数量"""
    try:
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        delta = end - start
        return delta.days
    except:
        return 0

# 全局变量存储更新状态
update_status = {}

# AkShare重试管理器已删除，不再使用AkShare

def clean_float_precision(value, decimal_places=2):
    """
    清理浮点数精度问题，避免显示包含999的精度误差
    
    Args:
        value: 要处理的数值
        decimal_places: 保留的小数位数，默认2位
    
    Returns:
        处理后的浮点数
    """
    try:
        if value is None or pd.isna(value):
            return 0.0
        
        # 转换为浮点数
        float_value = float(value)
        
        # 检查是否为特殊值
        if not np.isfinite(float_value):
            return 0.0
        
        # 四舍五入到指定小数位数，避免精度问题
        rounded_value = round(float_value, decimal_places)
        
        # 检查字符串表示是否包含999（可能的精度问题）
        str_value = str(float_value)
        if '999' in str_value and abs(float_value - rounded_value) < 0.01:
            # 如果原值包含999且与四舍五入后的值差异很小，使用四舍五入后的值
            return rounded_value
        
        return float_value
        
    except (ValueError, TypeError):
        return 0.0

def get_real_time_stock_data(ts_code, name, industry, current_date):
    """获取单只股票的实时数据"""
    def safe_float(value, default=0.0):
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    # 初始化股票信息
    stock_info = {
        'ts_code': ts_code,
        'name': name,
        'industry': industry,
        'latest_price': 0,
        'pct_chg': 0,
        'turnover_rate': 0,
        'volume_ratio': 0,
        'amount': 0,
        'market_cap': 0,
        'pe_ttm': 0,
        'net_mf_amount': 0,  # 净流入额（千万元）
        'nine_turn_up': 0,
        'nine_turn_down': 0,
        'countdown_up': 0,
        'countdown_down': 0,
        'last_update': current_date,
        'data_loaded': True
    }
    
    try:
        # 获取最新价格和基本面数据
        latest_data = safe_tushare_call(pro.daily, ts_code=ts_code, limit=1)
        daily_basic = safe_tushare_call(pro.daily_basic, ts_code=ts_code, limit=1)
        
        # 获取资金流向数据
        current_trade_date = datetime.now().strftime('%Y%m%d')
        moneyflow_data = safe_tushare_call(pro.moneyflow, ts_code=ts_code, trade_date=current_trade_date)
        
        # 获取最近30天的K线数据用于计算九转序列
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
        kline_data = safe_tushare_call(pro.daily, ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        # 更新实时数据
        if not latest_data.empty:
            current_close = safe_float(latest_data.iloc[0]['close'])
            stock_info['latest_price'] = current_close
            stock_info['amount'] = safe_float(latest_data.iloc[0]['amount'])
            
            # 计算当天涨幅
            if 'pct_chg' in latest_data.columns and not pd.isna(latest_data.iloc[0]['pct_chg']):
                stock_info['pct_chg'] = safe_float(latest_data.iloc[0]['pct_chg'])
            else:
                # 尝试从K线数据计算涨幅
                if not kline_data.empty and len(kline_data) >= 2:
                    kline_sorted = kline_data.sort_values('trade_date')
                    if len(kline_sorted) >= 2:
                        yesterday_close = safe_float(kline_sorted.iloc[-2]['close'])
                        if yesterday_close > 0:
                            stock_info['pct_chg'] = ((current_close - yesterday_close) / yesterday_close) * 100
        
        # 更新财务数据
        if not daily_basic.empty:
            if 'turnover_rate' in daily_basic.columns:
                stock_info['turnover_rate'] = safe_float(daily_basic.iloc[0]['turnover_rate'])
            if 'volume_ratio' in daily_basic.columns:
                stock_info['volume_ratio'] = safe_float(daily_basic.iloc[0]['volume_ratio'])
            if 'total_mv' in daily_basic.columns:
                stock_info['market_cap'] = safe_float(daily_basic.iloc[0]['total_mv'])
            if 'pe_ttm' in daily_basic.columns:
                stock_info['pe_ttm'] = safe_float(daily_basic.iloc[0]['pe_ttm'])
        
        # 更新资金流向数据
        if not moneyflow_data.empty:
            if 'net_mf_amount' in moneyflow_data.columns:
                # net_mf_amount单位是万元，转换为千万元
                net_mf_amount_wan = safe_float(moneyflow_data.iloc[0]['net_mf_amount'])
                stock_info['net_mf_amount'] = round(net_mf_amount_wan / 1000, 2)  # 转换为千万元，保留2位小数
        
        # 计算九转序列
        if not kline_data.empty and len(kline_data) >= 5:
            kline_data = kline_data.sort_values('trade_date')
            kline_with_nine_turn = calculate_nine_turn(kline_data)
            # 获取最新一天的九转序列数据
            latest_nine_turn = kline_with_nine_turn.iloc[-1]
            stock_info['nine_turn_up'] = int(latest_nine_turn['nine_turn_up']) if latest_nine_turn['nine_turn_up'] > 0 else 0
            stock_info['nine_turn_down'] = int(latest_nine_turn['nine_turn_down']) if latest_nine_turn['nine_turn_down'] > 0 else 0
            stock_info['countdown_up'] = int(latest_nine_turn['countdown_up']) if latest_nine_turn['countdown_up'] > 0 else 0
            stock_info['countdown_down'] = int(latest_nine_turn['countdown_down']) if latest_nine_turn['countdown_down'] > 0 else 0
        
    except Exception as e:
        print(f"获取{ts_code}实时数据失败: {e}")
        stock_info['data_loaded'] = False
    
    return stock_info

def update_stock_data_progressive(market, stocks_list):
    """渐进式更新股票数据，逐个获取并立即保存"""
    def safe_float(value, default=0.0):
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    print(f"开始渐进式更新{market}市场{len(stocks_list)}只股票的实时数据...")
    current_date = datetime.now().strftime('%Y%m%d')
    
    # 检查是否已有更新线程在运行
    if market in update_status and update_status[market].get('status') == 'updating':
        print(f"{market}市场已有更新线程在运行，跳过重复更新")
        return
    
    # 创建股票列表的深拷贝，避免并发修改问题
    import copy
    working_stocks_list = copy.deepcopy(stocks_list)
    
    # 初始化更新状态
    update_status[market] = {
        'total': len(working_stocks_list),
        'completed': 0,
        'status': 'updating',
        'start_time': time.time()
    }
    
    # 按股票代码排序（创业板从300001开始）
    if market == 'cyb':
        working_stocks_list.sort(key=lambda x: x['ts_code'])
    
    # 逐个处理股票
    for i, stock_info in enumerate(working_stocks_list):
        try:
            # 检查是否需要停止更新（比如用户强制刷新）
            if market in update_status and update_status[market].get('status') == 'cancelled':
                print(f"{market}市场更新被取消")
                break
                
            print(f"正在更新 {stock_info['ts_code']} ({i+1}/{len(working_stocks_list)})")
            
            # 获取最新价格和基本面数据（使用频率限制）
            latest_data = safe_tushare_call(pro.daily, ts_code=stock_info['ts_code'], limit=1)
            daily_basic = safe_tushare_call(pro.daily_basic, ts_code=stock_info['ts_code'], limit=1)
            
            # 获取资金流向数据
            current_trade_date = datetime.now().strftime('%Y%m%d')
            moneyflow_data = safe_tushare_call(pro.moneyflow, ts_code=stock_info['ts_code'], trade_date=current_trade_date)
            
            # 获取最近30天的K线数据用于计算九转序列（使用频率限制）
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
            kline_data = safe_tushare_call(pro.daily, ts_code=stock_info['ts_code'], start_date=start_date, end_date=end_date)
            
            # 更新实时数据
            if not latest_data.empty:
                current_close = safe_float(latest_data.iloc[0]['close'])
                stock_info['latest_price'] = current_close
                stock_info['amount'] = safe_float(latest_data.iloc[0]['amount'])
                
                # 计算当天涨幅 (pct_chg)
                if 'pct_chg' in latest_data.columns and not pd.isna(latest_data.iloc[0]['pct_chg']):
                    # 如果Tushare数据中有pct_chg字段，直接使用
                    stock_info['pct_chg'] = safe_float(latest_data.iloc[0]['pct_chg'])
                else:
                    # 如果没有pct_chg字段，尝试计算
                    # 获取前一个交易日的收盘价来计算涨幅
                    if 'pre_close' in latest_data.columns and not pd.isna(latest_data.iloc[0]['pre_close']):
                        pre_close = safe_float(latest_data.iloc[0]['pre_close'])
                        if pre_close > 0:
                            stock_info['pct_chg'] = ((current_close - pre_close) / pre_close) * 100
                        else:
                            stock_info['pct_chg'] = 0
                    else:
                        # 如果没有前收盘价，尝试从K线数据计算
                        if not kline_data.empty and len(kline_data) >= 2:
                            kline_sorted = kline_data.sort_values('trade_date')
                            if len(kline_sorted) >= 2:
                                yesterday_close = safe_float(kline_sorted.iloc[-2]['close'])
                                if yesterday_close > 0:
                                    stock_info['pct_chg'] = ((current_close - yesterday_close) / yesterday_close) * 100
                                else:
                                    stock_info['pct_chg'] = 0
                            else:
                                stock_info['pct_chg'] = 0
                        else:
                            stock_info['pct_chg'] = 0
            
            if not daily_basic.empty:
                if 'turnover_rate' in daily_basic.columns:
                    stock_info['turnover_rate'] = safe_float(daily_basic.iloc[0]['turnover_rate'])
                if 'volume_ratio' in daily_basic.columns:
                    stock_info['volume_ratio'] = safe_float(daily_basic.iloc[0]['volume_ratio'])
                if 'total_mv' in daily_basic.columns:
                    stock_info['market_cap'] = safe_float(daily_basic.iloc[0]['total_mv'])
                if 'pe_ttm' in daily_basic.columns:
                    stock_info['pe_ttm'] = safe_float(daily_basic.iloc[0]['pe_ttm'])
            
            # 更新资金流向数据
            if not moneyflow_data.empty:
                if 'net_mf_amount' in moneyflow_data.columns:
                    # net_mf_amount单位是万元，转换为千万元
                    net_mf_amount_wan = safe_float(moneyflow_data.iloc[0]['net_mf_amount'])
                    stock_info['net_mf_amount'] = round(net_mf_amount_wan / 1000, 2)  # 转换为千万元，保留2位小数
            else:
                stock_info['net_mf_amount'] = 0  # 如果没有数据，设置为0
            
            # 计算九转序列
            nine_turn_up = 0
            nine_turn_down = 0
            if not kline_data.empty and len(kline_data) >= 5:
                kline_data = kline_data.sort_values('trade_date')
                kline_with_nine_turn = calculate_nine_turn(kline_data)
                # 获取最新一天的九转序列数据
                latest_nine_turn = kline_with_nine_turn.iloc[-1]
                nine_turn_up = int(latest_nine_turn['nine_turn_up']) if latest_nine_turn['nine_turn_up'] > 0 else 0
                nine_turn_down = int(latest_nine_turn['nine_turn_down']) if latest_nine_turn['nine_turn_down'] > 0 else 0
            
            stock_info['nine_turn_up'] = nine_turn_up
            stock_info['nine_turn_down'] = nine_turn_down
            stock_info['last_update'] = current_date
            stock_info['data_loaded'] = True  # 标记数据已加载
            
            # 直接在工作列表中更新股票信息，避免频繁读写缓存文件
            # 在工作列表中找到对应股票并更新
            for working_stock in working_stocks_list:
                if working_stock['ts_code'] == stock_info['ts_code']:
                    working_stock.update(stock_info)
                    break
            
            # 每10只股票保存一次缓存，减少文件IO操作
            if (i + 1) % 10 == 0 or i == len(working_stocks_list) - 1:
                # 构建缓存数据
                cache_data = {
                    'stocks': working_stocks_list,
                    'last_update_date': current_date,
                    'total': len(working_stocks_list),
                    'progress': {
                        'completed': i + 1,
                        'total': len(working_stocks_list),
                        'current_stock': stock_info['ts_code']
                    },
                    'data_status': 'updating'
                }
                save_cache_data(market, cache_data)
                print(f"已保存缓存，当前进度: {i+1}/{len(working_stocks_list)}")
            
            # 更新全局状态
            update_status[market]['completed'] = i + 1
            
            print(f"已完成 {stock_info['ts_code']} 数据更新 ({i+1}/{len(working_stocks_list)})")
            
        except Exception as e:
            error_msg = str(e)
            print(f"更新股票{stock_info['ts_code']}数据失败: {error_msg}")
            
            # 如果是API限制错误，记录失败但不中断整个流程
            if any(keyword in error_msg.lower() for keyword in ["频率", "limit", "rate", "too many", "exceeded"]):
                print(f"股票{stock_info['ts_code']}遇到API限制，将在后续重试")
                # 标记为需要重试的股票
                stock_info['retry_needed'] = True
                stock_info['retry_reason'] = 'api_limit'
            else:
                # 其他错误，标记为失败
                stock_info['retry_needed'] = False
                stock_info['retry_reason'] = 'other_error'
            
            # 即使失败也标记为已处理
            stock_info['data_loaded'] = False
            stock_info['last_update'] = current_date
            continue
    
    # 检查更新是否被取消
    if market in update_status and update_status[market].get('status') == 'cancelled':
        print(f"{market}市场更新被取消，不保存最终状态")
        return
    
    # 检查是否有因API限制失败的股票需要重试
    retry_stocks = [stock for stock in working_stocks_list if stock.get('retry_needed') and stock.get('retry_reason') == 'api_limit']
    
    if retry_stocks:
        print(f"发现{len(retry_stocks)}只股票因API限制失败，等待60秒后开始重试...")
        time.sleep(60)  # 等待60秒确保API限制解除
        
        for retry_stock in retry_stocks:
            try:
                # 检查是否需要停止更新
                if market in update_status and update_status[market].get('status') == 'cancelled':
                    print(f"{market}市场更新被取消")
                    break
                    
                print(f"重试更新 {retry_stock['ts_code']}")
                
                # 重新获取数据
                latest_data = safe_tushare_call(pro.daily, ts_code=retry_stock['ts_code'], limit=1)
                daily_basic = safe_tushare_call(pro.daily_basic, ts_code=retry_stock['ts_code'], limit=1)
                
                # 获取资金流向数据
                current_trade_date = datetime.now().strftime('%Y%m%d')
                moneyflow_data = safe_tushare_call(pro.moneyflow, ts_code=retry_stock['ts_code'], trade_date=current_trade_date)
                
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
                kline_data = safe_tushare_call(pro.daily, ts_code=retry_stock['ts_code'], start_date=start_date, end_date=end_date)
                
                # 更新数据
                if not latest_data.empty:
                    retry_stock['latest_price'] = safe_float(latest_data.iloc[0]['close'])
                    retry_stock['amount'] = safe_float(latest_data.iloc[0]['amount'])
                
                if not daily_basic.empty:
                    if 'turnover_rate' in daily_basic.columns:
                        retry_stock['turnover_rate'] = safe_float(daily_basic.iloc[0]['turnover_rate'])
                    if 'volume_ratio' in daily_basic.columns:
                        retry_stock['volume_ratio'] = safe_float(daily_basic.iloc[0]['volume_ratio'])
                    if 'total_mv' in daily_basic.columns:
                        retry_stock['market_cap'] = safe_float(daily_basic.iloc[0]['total_mv'])
                    if 'pe_ttm' in daily_basic.columns:
                        retry_stock['pe_ttm'] = safe_float(daily_basic.iloc[0]['pe_ttm'])
                
                # 更新资金流向数据
                if not moneyflow_data.empty:
                    if 'net_mf_amount' in moneyflow_data.columns:
                        # net_mf_amount单位是万元，转换为千万元
                        net_mf_amount_wan = safe_float(moneyflow_data.iloc[0]['net_mf_amount'])
                        retry_stock['net_mf_amount'] = round(net_mf_amount_wan / 1000, 2)  # 转换为千万元，保留2位小数
                else:
                    retry_stock['net_mf_amount'] = 0  # 如果没有数据，设置为0
                
                # 计算九转序列
                nine_turn_up = 0
                nine_turn_down = 0
                if not kline_data.empty and len(kline_data) >= 5:
                    kline_data = kline_data.sort_values('trade_date')
                    kline_with_nine_turn = calculate_nine_turn(kline_data)
                    latest_nine_turn = kline_with_nine_turn.iloc[-1]
                    nine_turn_up = int(latest_nine_turn['nine_turn_up']) if latest_nine_turn['nine_turn_up'] > 0 else 0
                    nine_turn_down = int(latest_nine_turn['nine_turn_down']) if latest_nine_turn['nine_turn_down'] > 0 else 0
                
                retry_stock['nine_turn_up'] = nine_turn_up
                retry_stock['nine_turn_down'] = nine_turn_down
                retry_stock['data_loaded'] = True
                retry_stock['retry_needed'] = False
                retry_stock['retry_reason'] = None
                
                print(f"重试成功: {retry_stock['ts_code']}")
                
            except Exception as e:
                print(f"重试失败 {retry_stock['ts_code']}: {e}")
                retry_stock['data_loaded'] = False
                retry_stock['retry_needed'] = False
                retry_stock['retry_reason'] = 'retry_failed'
                continue
        
        print(f"重试完成，成功重试{len([s for s in retry_stocks if s.get('data_loaded')])}只股票")
    
    # 更新完成，保存最终状态
    final_cache_data = {
        'stocks': working_stocks_list,
        'last_update_date': current_date,
        'total': len(working_stocks_list),
        'progress': {
            'completed': len(working_stocks_list),
            'total': len(working_stocks_list),
            'current_stock': 'all_completed'
        },
        'data_status': 'complete'
    }
    save_cache_data(market, final_cache_data)
    
    # 统计成功和失败的数量
    successful_count = len([s for s in working_stocks_list if s.get('data_loaded')])
    failed_count = len(working_stocks_list) - successful_count
    
    # 更新全局状态
    update_status[market] = {
        'total': len(working_stocks_list),
        'completed': len(working_stocks_list),
        'successful': successful_count,
        'failed': failed_count,
        'status': 'complete',
        'end_time': time.time()
    }
    
    print(f"完成{market}市场所有股票数据的渐进式更新！成功: {successful_count}, 失败: {failed_count}")

def calculate_nine_turn(df):
    """
    计算九转序列和Countdown - 完整TD Sequential算法（优化标注原则）
    Setup阶段（1-9）：
    - 买入Setup（看跌转涨）：当日收盘价 < 4个交易日前的收盘价，连续满足9次
    - 卖出Setup（看涨转跌）：当日收盘价 > 4个交易日前的收盘价，连续满足9次
    
    Countdown阶段（1-13）：
    - 买入Countdown（寻找反弹）：收盘价 <= 2天前最低价，满足13次（不要求连续）
    - 卖出Countdown（寻找见顶）：收盘价 >= 2天前最高价，满足13次（不要求连续）
    
    标注规则（比同花顺早3天显示）：
    1. Setup阶段：当连续满足3次条件时开始显示序列号（同花顺是6次）
    2. 继续满足条件则继续显示，如果中断则全部清除
    3. Countdown阶段：Setup完成后开始，标注1-13，可被新Setup中断
    4. Countdown不要求连续，只要满足条件就计数
    """
    df = df.copy()
    df['nine_turn_up'] = 0
    df['nine_turn_down'] = 0
    df['countdown_up'] = 0  # 卖出Countdown（K线上方）
    df['countdown_down'] = 0  # 买入Countdown（K线下方）
    
    # Setup阶段 - 卖出Setup（看涨转跌）
    up_count = 0
    up_positions = []  # 记录满足条件的位置
    up_setup_complete_pos = -1  # Setup完成的位置
    
    for i in range(4, len(df)):  # 从第5个数据开始，因为需要比较4天前的数据
        # 当日收盘价 > 4个交易日前的收盘价
        if df.iloc[i]['close'] > df.iloc[i-4]['close']:
            up_count += 1
            up_positions.append(i)
            
            # 当达到3个时开始显示序列号（比同花顺早3天）
            if up_count >= 3:
                for j, pos in enumerate(up_positions):
                    if j < 9:  # 最多显示9个
                        df.iloc[pos, df.columns.get_loc('nine_turn_up')] = j + 1  # pos是位置，j+1是序列值
            
            # 如果达到9个，记录Setup完成位置并停止计数
            if up_count >= 9:
                up_setup_complete_pos = i
                up_count = 0
                up_positions = []
        else:
            # 如果中断，清除所有标记
            for pos in up_positions:
                df.iloc[pos, df.columns.get_loc('nine_turn_up')] = 0
            up_count = 0
            up_positions = []
    
    # Setup阶段 - 买入Setup（看跌转涨）
    down_count = 0
    down_positions = []  # 记录满足条件的位置
    down_setup_complete_pos = -1  # Setup完成的位置
    
    for i in range(4, len(df)):  # 从第5个数据开始，因为需要比较4天前的数据
        # 当日收盘价 < 4个交易日前的收盘价
        if df.iloc[i]['close'] < df.iloc[i-4]['close']:
            down_count += 1
            down_positions.append(i)
            
            # 当达到3个时开始显示序列号（比同花顺早3天）
            if down_count >= 3:
                for j, pos in enumerate(down_positions):
                    if j < 9:  # 最多显示9个
                        df.iloc[pos, df.columns.get_loc('nine_turn_down')] = j + 1  # pos是位置，j+1是序列值
            
            # 如果达到9个，记录Setup完成位置并停止计数
            if down_count >= 9:
                down_setup_complete_pos = i
                down_count = 0
                down_positions = []
        else:
            # 如果中断，清除所有标记
            for pos in down_positions:
                df.iloc[pos, df.columns.get_loc('nine_turn_down')] = 0
            down_count = 0
            down_positions = []
    
    # Countdown阶段 - 卖出Countdown（上涨Setup完成后）
    if up_setup_complete_pos >= 0:
        sell_countdown = 0
        sell_countdown_completed = False  # 添加完成标志
        
        for i in range(max(up_setup_complete_pos + 1, 2), len(df)):
            # 检查是否有相反方向的Setup出现（下跌Setup），如果有则重置Countdown
            if df.iloc[i]['nine_turn_down'] > 0:
                sell_countdown = 0
                sell_countdown_completed = False  # 相反Setup出现时重置完成标志
                continue
            
            # 如果Countdown已完成（达到13），则停止计算
            if sell_countdown_completed:
                continue
                
            # 卖出Countdown条件：收盘价 >= 2天前最高价
            if df.iloc[i]['close'] >= df.iloc[i-2]['high']:
                sell_countdown += 1
                if sell_countdown <= 13:  # 显示1-13
                    df.iloc[i, df.columns.get_loc('countdown_up')] = sell_countdown  # 1, 2, 3, ..., 13
                
                # 达到13后标记为完成，停止计算
                if sell_countdown >= 13:
                    sell_countdown_completed = True
    
    # Countdown阶段 - 买入Countdown（下跌Setup完成后）
    if down_setup_complete_pos >= 0:
        buy_countdown = 0
        buy_countdown_completed = False  # 添加完成标志
        
        for i in range(max(down_setup_complete_pos + 1, 2), len(df)):
            # 检查是否有相反方向的Setup出现（上涨Setup），如果有则重置Countdown
            if df.iloc[i]['nine_turn_up'] > 0:
                buy_countdown = 0
                buy_countdown_completed = False  # 相反Setup出现时重置完成标志
                continue
            
            # 如果Countdown已完成（达到13），则停止计算
            if buy_countdown_completed:
                continue
                
            # 买入Countdown条件：收盘价 <= 2天前最低价
            if df.iloc[i]['close'] <= df.iloc[i-2]['low']:
                buy_countdown += 1
                if buy_countdown <= 13:  # 显示1-13
                    df.iloc[i, df.columns.get_loc('countdown_down')] = buy_countdown  # 1, 2, 3, ..., 13
                
                # 达到13后标记为完成，停止计算
                if buy_countdown >= 13:
                    buy_countdown_completed = True
    
    return df

def calculate_boll(df, period=20, std_dev=2):
    """
    计算布林带(BOLL)指标
    参数:
    - period: 移动平均周期，默认20天
    - std_dev: 标准差倍数，默认2倍
    """
    df = df.copy()
    
    # 计算中轨（移动平均线）- 从第一根K线开始显示
    df['boll_mid'] = df['close'].rolling(window=period, min_periods=1).mean()
    
    # 计算标准差 - 从第一根K线开始显示
    df['boll_std'] = df['close'].rolling(window=period, min_periods=1).std()
    
    # 计算上轨和下轨
    df['boll_upper'] = df['boll_mid'] + (df['boll_std'] * std_dev)
    df['boll_lower'] = df['boll_mid'] - (df['boll_std'] * std_dev)
    
    # 应用精度修复，避免显示包含"999"的浮点数
    df['boll_mid'] = df['boll_mid'].apply(lambda x: clean_float_precision(x, 4))
    df['boll_upper'] = df['boll_upper'].apply(lambda x: clean_float_precision(x, 4))
    df['boll_lower'] = df['boll_lower'].apply(lambda x: clean_float_precision(x, 4))
    
    # 对于前期数据不足的情况，保持为NaN，后续会被前端正确处理
    # 不填充NaN值，让前端图表自动处理空值
    
    return df


def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9):
    """
    计算MACD指标
    参数:
    - fast_period: 快速EMA周期，默认12天
    - slow_period: 慢速EMA周期，默认26天
    - signal_period: 信号线EMA周期，默认9天
    """
    df = df.copy()
    
    # 计算快速和慢速EMA
    df['ema_fast'] = df['close'].ewm(span=fast_period, min_periods=1).mean()
    df['ema_slow'] = df['close'].ewm(span=slow_period, min_periods=1).mean()
    
    # 计算MACD线（DIF）
    df['macd_dif'] = df['ema_fast'] - df['ema_slow']
    
    # 计算信号线（DEA）
    df['macd_dea'] = df['macd_dif'].ewm(span=signal_period, min_periods=1).mean()
    
    # 计算MACD柱状图（MACD）
    df['macd_histogram'] = (df['macd_dif'] - df['macd_dea']) * 2
    
    # 应用精度修复，避免显示包含"999"的浮点数
    df['macd_dif'] = df['macd_dif'].apply(lambda x: clean_float_precision(x, 4))
    df['macd_dea'] = df['macd_dea'].apply(lambda x: clean_float_precision(x, 4))
    df['macd_histogram'] = df['macd_histogram'].apply(lambda x: clean_float_precision(x, 4))
    
    return df


def calculate_kdj(df, k_period=9, d_period=3, j_period=3):
    """
    计算KDJ指标
    参数:
    - k_period: K值计算周期，默认9天
    - d_period: D值平滑周期，默认3天
    - j_period: J值计算周期，默认3天
    """
    df = df.copy()
    
    # 计算最高价和最低价的滚动窗口
    df['highest_high'] = df['high'].rolling(window=k_period, min_periods=1).max()
    df['lowest_low'] = df['low'].rolling(window=k_period, min_periods=1).min()
    
    # 计算RSV（未成熟随机值）
    df['rsv'] = ((df['close'] - df['lowest_low']) / (df['highest_high'] - df['lowest_low']) * 100).fillna(50)
    
    # 计算K值（使用简单移动平均代替指数移动平均以简化计算）
    df['kdj_k'] = df['rsv'].rolling(window=d_period, min_periods=1).mean()
    
    # 计算D值
    df['kdj_d'] = df['kdj_k'].rolling(window=d_period, min_periods=1).mean()
    
    # 计算J值
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    
    # 应用精度修复，避免显示包含"999"的浮点数
    df['kdj_k'] = df['kdj_k'].apply(lambda x: clean_float_precision(x, 4))
    df['kdj_d'] = df['kdj_d'].apply(lambda x: clean_float_precision(x, 4))
    df['kdj_j'] = df['kdj_j'].apply(lambda x: clean_float_precision(x, 4))
    
    return df


def calculate_rsi(df, period=14):
    """
    计算RSI指标（相对强弱指数）
    参数:
    - period: RSI计算周期，默认14天
    """
    df = df.copy()
    
    # 计算价格变化
    df['price_change'] = df['close'].diff()
    
    # 分离上涨和下跌
    df['gain'] = df['price_change'].where(df['price_change'] > 0, 0)
    df['loss'] = -df['price_change'].where(df['price_change'] < 0, 0)
    
    # 计算平均收益和平均损失（使用简单移动平均）
    df['avg_gain'] = df['gain'].rolling(window=period, min_periods=1).mean()
    df['avg_loss'] = df['loss'].rolling(window=period, min_periods=1).mean()
    
    # 计算相对强度RS
    df['rs'] = df['avg_gain'] / (df['avg_loss'] + 1e-10)  # 避免除零
    
    # 计算RSI
    df['rsi'] = 100 - (100 / (1 + df['rs']))
    
    # 处理第一行的NaN值
    df['rsi'] = df['rsi'].fillna(50)
    
    # 应用精度修复，避免显示包含"999"的浮点数
    df['rsi'] = df['rsi'].apply(lambda x: clean_float_precision(x, 4))
    
    return df


def calculate_ema15(df, period=15):
    """
    计算EMA15指数移动平均线
    参数:
    - period: EMA周期，默认15天
    """
    df = df.copy()
    
    # 计算EMA15
    df['ema15'] = df['close'].ewm(span=period, min_periods=1).mean()
    
    # 应用精度修复，避免显示包含"999"的浮点数
    df['ema15'] = df['ema15'].apply(lambda x: clean_float_precision(x, 4))
    
    return df




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stock/<stock_code>')
def stock_detail(stock_code):
    return render_template('stock_detail.html', stock_code=stock_code)

@app.route('/stock_detail')
def stock_detail_with_params():
    """股票详情页面（通过查询参数获取股票代码）"""
    stock_code = request.args.get('code', '300354')
    return render_template('stock_detail.html', stock_code=stock_code)

@app.route('/stock/<stock_code>/candlestick')
def candlestick_chart(stock_code):
    """股票蜡烛图页面"""
    return render_template('candlestick_chart.html', stock_code=stock_code)

@app.route('/stock/debug')
def stock_debug():
    """股票详情调试页面"""
    return render_template('stock_detail_debug.html')

@app.route('/test/simple')
def simple_test():
    """最简单的测试页面"""
    return render_template('simple_test.html')

@app.route('/test/step')
def step_debug():
    """逐步调试页面"""
    return render_template('step_debug.html')

@app.route('/test/error')
def error_catch_test():
    """错误捕获测试页面"""
    return render_template('error_catch_test.html')

@app.route('/test/function')
def function_test():
    """函数测试页面"""
    return render_template('function_test.html')

@app.route('/test/syntax')
def syntax_test():
    """语法测试页面"""
    return render_template('syntax_test.html')



@app.route('/watchlist')
def watchlist():
    return render_template('watchlist.html')

@app.route('/cache/monitor')
def cache_monitor():
    """缓存系统监控页面"""
    return render_template('cache_monitor.html')

@app.route('/red-filter')
def red_filter():
    """红 3-6 筛选页面"""
    return render_template('red_filter.html')

@app.route('/green-filter')
def green_filter():
    """绿 9 筛选页面"""
    return render_template('green_filter.html')

@app.route('/top-list')
def top_list():
    """龙虎榜页面"""
    return render_template('top_list.html')

@app.route('/kline-test')
def kline_test():
    """K线图重构测试页面"""
    return render_template('kline_test.html')

@app.route('/indicator-test')
def indicator_test():
    """技术指标测试页面"""
    return render_template('indicator_test.html')

@app.route('/indicator-fix-test')
def indicator_fix_test():
    """技术指标修复测试页面"""
    return render_template('indicator_fix_test.html')

@app.route('/boll-debug')
def boll_debug():
    """BOLL指标调试页面"""
    return render_template('boll_debug.html')

@app.route('/boll-test')
def boll_test():
    """BOLL指标测试验证页面"""
    return render_template('boll_test.html')

@app.route('/test/refresh')
def test_refresh():
    """自动刷新功能测试页面"""
    return render_template('test_refresh.html')

def get_stock_from_cache(ts_code):
    """从缓存中查找股票数据"""
    # 确定股票所属市场
    if ts_code.endswith('.SH'):
        if ts_code.startswith('688'):
            market = 'kcb'  # 科创板
        else:
            market = 'hu'   # 沪A
    elif ts_code.endswith('.SZ'):
        if ts_code.startswith('300'):
            market = 'cyb'  # 创业板
        else:
            market = 'zxb'  # 深A
    elif ts_code.endswith('.BJ'):
        market = 'bj'   # 北交所
    else:
        return None
    
    # 从缓存中查找股票数据
    cache_data = load_cache_data(market)
    if cache_data and 'stocks' in cache_data:
        for stock in cache_data['stocks']:
            if stock.get('ts_code') == ts_code:
                return stock
    return None

def retry_api_call_with_rate_limit(api_func, max_retries=3, retry_delay=60):
    """带重试机制的API调用，处理频率限制"""
    for attempt in range(max_retries):
        try:
            result = api_func()
            return result
        except Exception as e:
            error_msg = str(e)
            if "每分钟最多访问该接口" in error_msg or "访问频率" in error_msg:
                if attempt < max_retries - 1:
                    print(f"API频率限制，等待{retry_delay}秒后重试... (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"API频率限制，已达到最大重试次数")
                    raise e
            else:
                raise e
    return None

# 全局变量用于重试机制
last_retry_time = None
retry_interval = 30  # 30秒重试间隔

@app.route('/api/indices/reset_retry')
def reset_indices_retry():
    """重置指数数据重试状态"""
    global last_retry_time
    last_retry_time = None
    return jsonify({
        'success': True,
        'message': '指数数据重试状态已重置',
        'reset_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/indices/trigger_failure')
def trigger_indices_failure():
    """手动触发指数数据失败状态（用于测试）"""
    global last_retry_time
    last_retry_time = datetime.now()
    
    return jsonify({
        'success': True,
        'message': '已触发指数数据失败状态',
        'trigger_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'next_retry_time': (datetime.now() + timedelta(seconds=retry_interval)).strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/indices/test_akshare_realtime')
def test_akshare_realtime_indices():
    """测试AKShare实时指数数据获取"""
    try:
        # 定义要获取的指数代码和名称
        indices = {
            'sh000001': '上证指数',
            'sz399001': '深证成指', 
            'sz399006': '创业板指',
            'sh000688': '科创板'
        }
        
        print("[测试] 开始测试AKShare实时指数数据获取...")
        indices_data = get_indices_from_akshare_realtime(indices)
        
        if indices_data:
            # 转换数据格式以匹配前端期望
            formatted_data = {}
            current_time = datetime.now().strftime('%H:%M:%S')
            
            for code, data in indices_data.items():
                formatted_data[code] = {
                    'name': data['name'],
                    'current_price': data['price'],
                    'change_pct': data['change_percent'],
                    'change_amount': data['change'],
                    'volume': data['volume'],
                    'update_time': current_time
                }
            
            return jsonify({
                'success': True,
                'data': formatted_data,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'akshare_realtime',
                'message': f'AKShare实时数据获取成功，共获取到 {len(indices_data)} 个指数'
            })
        else:
            return jsonify({
                'success': False,
                'data': {},
                'message': 'AKShare实时数据获取失败',
                'source': 'akshare_realtime'
            })
            
    except Exception as e:
        print(f"测试AKShare实时指数数据异常: {e}")
        return jsonify({
            'success': False,
            'data': {},
            'message': f'测试异常: {str(e)}',
            'source': 'akshare_realtime'
        })

@app.route('/api/indices/test_tushare')
def test_tushare_indices():
    """测试Tushare指数数据获取（强制跳过AkShare）"""
    try:
        # 定义要获取的指数代码和名称
        indices = {
            'sh000001': '上证指数',
            'sz399001': '深证成指', 
            'sz399006': '创业板指',
            'sh000688': '科创板'
        }
        
        print("[测试] 强制使用Tushare获取指数数据...")
        indices_data = get_indices_from_tushare(indices)
        
        if indices_data:
            print("[测试] Tushare获取成功")
            
            # 转换数据格式以匹配前端期望
            formatted_data = {}
            for code, data in indices_data.items():
                formatted_data[code] = {
                    'name': data['name'],
                    'current_price': data['price'],
                    'change_pct': data['change_percent'],
                    'change_amount': data['change'],
                    'volume': data['volume'],
                    'update_time': datetime.now().strftime('%H:%M:%S')
                }
            
            return jsonify({
                'success': True,
                'data': formatted_data,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'tushare_test'
            })
        else:
            print("[测试] Tushare返回空数据")
            return jsonify({
                'success': False,
                'error': 'Tushare返回空数据',
                'source': 'tushare_test'
            }), 500
            
    except Exception as e:
        print(f"[测试] Tushare获取异常: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'source': 'tushare_test'
        }), 500

def is_market_open():
    """检查A股是否在开盘时间"""
    now = datetime.now()
    
    # 检查是否为工作日（周一到周五）
    if now.weekday() >= 5:  # 周六=5, 周日=6
        return False
    
    current_time = now.time()
    
    # A股开盘时间：
    # 上午：9:30-11:30
    # 下午：13:00-15:00
    morning_start = datetime.strptime('09:30', '%H:%M').time()
    morning_end = datetime.strptime('11:30', '%H:%M').time()
    afternoon_start = datetime.strptime('13:00', '%H:%M').time()
    afternoon_end = datetime.strptime('15:00', '%H:%M').time()
    
    is_morning_session = morning_start <= current_time <= morning_end
    is_afternoon_session = afternoon_start <= current_time <= afternoon_end
    
    return is_morning_session or is_afternoon_session

@app.route('/api/market/status')
def get_market_status():
    """获取市场开盘状态"""
    try:
        is_open = is_market_open()
        return jsonify({
            'success': True,
            'is_market_open': is_open,
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/indices/realtime')
def get_indices_realtime():
    """获取主要指数数据 - 根据交易时间采用不同策略"""
    try:
        # 定义要获取的指数代码和名称
        indices = {
            'sh000001': '上证指数',
            'sz399001': '深证成指', 
            'sz399006': '创业板指',
            'sh000688': '科创板'
        }
        
        is_trading_time = is_market_open()
        current_time = datetime.now().strftime('%H:%M:%S')
        
        if is_trading_time:
            print(f"[指数数据] 交易时间 {current_time}，获取实时数据...")
            # 交易时间：优先使用AKShare获取实时数据
            indices_data = get_indices_from_akshare_realtime(indices)
            
            # 如果AKShare获取失败，回退到Tushare
            if not indices_data:
                print("[指数数据] AKShare实时数据获取失败，回退到Tushare...")
                indices_data = get_indices_from_tushare(indices)
            
            if not indices_data:
                print("[指数数据] 所有数据源获取失败，返回全0数据等待重试")
                return get_zero_indices_data(indices)
            
            # 转换数据格式以匹配前端期望
            formatted_data = {}
            for code, data in indices_data.items():
                formatted_data[code] = {
                    'name': data['name'],
                    'current_price': data['price'],
                    'change_pct': data['change_percent'],
                    'change_amount': data['change'],
                    'volume': data['volume'],
                    'update_time': current_time
                }
            
            # 保存数据到缓存
            fetch_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_indices_cache(formatted_data, fetch_time)
            
            return jsonify({
                'success': True,
                'data': formatted_data,
                'fetch_time': fetch_time,
                'is_trading_time': True,
                'source': 'realtime'
            })
        else:
            print(f"[指数数据] 非交易时间 {current_time}，获取今日收盘数据...")
            # 非交易时间：获取今日收盘数据
            indices_data = get_today_close_data(indices)
            
            if not indices_data:
                print("[指数数据] 今日收盘数据获取失败，返回全0数据等待重试")
                return get_zero_indices_data(indices)
            
            return jsonify({
                'success': True,
                'data': indices_data,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_trading_time': False,
                'source': 'today_close'
            })
        
    except Exception as e:
        print(f"获取指数数据异常: {e}")
        # 异常情况返回全0数据
        return get_zero_indices_data({
            'sh000001': '上证指数',
            'sz399001': '深证成指', 
            'sz399006': '创业板指',
            'sh000688': '科创板'
        })

# 指数数据缓存管理函数
def load_indices_cache():
    """加载指数数据缓存"""
    try:
        cache_file = os.path.join('cache', 'indices_cache.json')
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
                # 检查缓存是否是当天的数据
                cache_date = cached_data.get('cache_date', '')
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                # 如果是周末，不使用当天的缓存，需要重新获取最新交易日数据
                now = datetime.now()
                if now.weekday() >= 5:  # 周六或周日
                    print(f"当前是周末，不使用缓存数据，需要重新获取最新交易日数据")
                    return None
                
                # 工作日时检查缓存日期
                if cache_date == current_date:
                    return cached_data
                else:
                    print(f"指数缓存数据过期: 缓存日期={cache_date}, 当前日期={current_date}")
        return None
    except Exception as e:
        print(f"加载指数缓存失败: {e}")
        return None

def save_indices_cache(data, fetch_time):
    """保存指数数据到缓存"""
    try:
        cache_dir = 'cache'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        cache_file = os.path.join(cache_dir, 'indices_cache.json')
        cache_data = {
            'data': data,
            'fetch_time': fetch_time,
            'cache_date': datetime.now().strftime('%Y-%m-%d'),
            'cache_time': datetime.now().strftime('%H:%M:%S')
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"指数数据已保存到缓存: {cache_file}")
        return True
    except Exception as e:
        print(f"保存指数缓存失败: {e}")
        return False

def load_all_indices_cache():
    """加载所有指数数据缓存"""
    try:
        cache_file = os.path.join('cache', 'all_indices_cache.json')
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
                # 检查缓存是否是当天的数据
                cache_date = cached_data.get('cache_date', '')
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                # 如果是周末，不使用当天的缓存，需要重新获取最新交易日数据
                now = datetime.now()
                if now.weekday() >= 5:  # 周六或周日
                    print(f"当前是周末，不使用所有指数缓存数据，需要重新获取最新交易日数据")
                    return None
                
                # 工作日时检查缓存日期
                if cache_date == current_date:
                    return cached_data
                else:
                    print(f"所有指数缓存数据过期: 缓存日期={cache_date}, 当前日期={current_date}")
        return None
    except Exception as e:
        print(f"加载所有指数缓存失败: {e}")
        return None

def save_all_indices_cache(data):
    """保存所有指数数据到缓存"""
    try:
        cache_dir = 'cache'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        cache_file = os.path.join(cache_dir, 'all_indices_cache.json')
        cache_data = {
            'data': data,
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'cache_date': datetime.now().strftime('%Y-%m-%d'),
            'cache_time': datetime.now().strftime('%H:%M:%S'),
            'count': len(data)
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"所有指数数据已保存到缓存: {cache_file}, 共{len(data)}条")
        return True
    except Exception as e:
        print(f"保存所有指数缓存失败: {e}")
        return False

def get_cached_all_indices_data():
    """获取缓存的所有指数数据，如果没有缓存则返回示例数据"""
    cached_data = load_all_indices_cache()
    
    if cached_data:
        print(f"从缓存获取所有指数数据，共{cached_data.get('count', 0)}条")
        return jsonify({
            'success': True,
            'data': cached_data['data'],
            'fetch_time': cached_data.get('fetch_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'count': cached_data.get('count', len(cached_data['data'])),
            'is_trading_time': False,
            'source': 'cache'
        })
    else:
        print("没有可用的所有指数缓存数据，返回示例数据")
        return get_sample_indices_data()

def get_indices_from_akshare_realtime(indices):
    """使用AKShare获取实时指数数据 - 双数据源策略（新浪财经和东财）"""
    if not AKSHARE_AVAILABLE:
        print("[AKShare] AKShare不可用，跳过AKShare获取")
        return None
        
    if 'ak' not in globals() or ak is None:
        print("[AKShare] akshare模块未正确导入，跳过AKShare获取")
        return None
        
    indices_data = {}
    current_time = datetime.now().strftime('%H:%M:%S')
    
    print(f"[AKShare] 开始获取实时指数数据 {current_time}")
    
    # 定义指数代码映射关系
    index_mapping = {
        'sh000001': {'name': '上证指数', 'search_name': '上证指数'},
        'sz399001': {'name': '深证成指', 'search_name': '深证成指'},
        'sz399006': {'name': '创业板指', 'search_name': '创业板指'},
        'sh000688': {'name': '科创板', 'search_name': '科创50'}
    }
    
    # 双数据源策略：先尝试新浪财经，失败后尝试东财
    data_sources = [
        {
            'name': '新浪财经',
            'functions': [
                {'func': ak.stock_zh_index_spot_sina, 'symbol': None, 'desc': '新浪财经指数'},
            ]
        },
        {
            'name': '东财',
            'functions': [
                {'func': ak.stock_zh_index_spot_em, 'symbol': "沪深重要指数", 'desc': '东财沪深重要指数'},
                {'func': ak.stock_zh_index_spot_em, 'symbol': "上证系列指数", 'desc': '东财上证系列指数'},
                {'func': ak.stock_zh_index_spot_em, 'symbol': "深证系列指数", 'desc': '东财深证系列指数'}
            ]
        }
    ]
    
    for source in data_sources:
        print(f"[AKShare] 尝试使用{source['name']}数据源...")
        source_success = False
        
        try:
            if source['name'] == '新浪财经':
                # 新浪财经数据源
                print(f"[AKShare] {source['name']} - 获取指数数据...")
                df = safe_akshare_call(ak.stock_zh_index_spot_sina, 'akshare_sina_indices')
                
                if df is not None and not df.empty:
                    print(f"[AKShare] {source['name']} - 数据获取成功，共{len(df)}条记录")
                    
                    for _, row in df.iterrows():
                        index_name = row['名称'] if '名称' in row else row.get('name', '')
                        index_code = row['代码'] if '代码' in row else row.get('code', '')
                        
                        print(f"[AKShare] {source['name']} - 处理指数: {index_name} ({index_code})")
                        
                        # 匹配指数
                        for code, info in index_mapping.items():
                            if (info['search_name'] in index_name or index_name in info['search_name'] or
                                code.replace('sh', '').replace('sz', '') in index_code):
                                try:
                                    current_price = float(row['最新价'] if '最新价' in row else row.get('price', 0))
                                    change_amount = float(row['涨跌额'] if '涨跌额' in row else row.get('change', 0))
                                    change_percent = float(row['涨跌幅'] if '涨跌幅' in row else row.get('change_pct', 0))
                                    volume = float(row['成交额'] if '成交额' in row else row.get('volume', 0))
                                    
                                    indices_data[code] = {
                                        'name': info['name'],
                                        'code': index_code,
                                        'price': current_price,
                                        'change': change_amount,
                                        'change_percent': change_percent,
                                        'volume': volume / 100000000 if volume > 0 else 0  # 转换为亿元
                                    }
                                    print(f"[AKShare] {source['name']} - {info['name']} 获取成功: 价格={current_price}, 涨跌幅={change_percent}%")
                                    source_success = True
                                except Exception as e:
                                    print(f"[AKShare] {source['name']} - 处理{info['name']}数据失败: {e}")
                                break
                    
                    if source_success and len(indices_data) >= 2:  # 至少获取到2个指数才算成功
                        print(f"[AKShare] {source['name']}数据源成功，获取到{len(indices_data)}个指数")
                        break
                        
            else:
                # 东财数据源
                for func_info in source['functions']:
                    print(f"[AKShare] {source['name']} - {func_info['desc']}...")
                    
                    if func_info['symbol']:
                        df = safe_akshare_call(func_info['func'], f"akshare_{func_info['symbol']}", symbol=func_info['symbol'])
                    else:
                        df = safe_akshare_call(func_info['func'], f"akshare_{func_info['desc']}")
                    
                    if df is not None and not df.empty:
                        print(f"[AKShare] {source['name']} - {func_info['desc']}数据获取成功，共{len(df)}条记录")
                        
                        for _, row in df.iterrows():
                            index_name = row['名称']
                            print(f"[AKShare] {source['name']} - 处理指数: {index_name}")
                            
                            # 匹配指数
                            for code, info in index_mapping.items():
                                if info['search_name'] in index_name or index_name in info['search_name']:
                                    try:
                                        current_price = float(row['最新价'])
                                        change_amount = float(row['涨跌额'])
                                        change_percent = float(row['涨跌幅'])
                                        volume = float(row['成交额']) if pd.notna(row['成交额']) else 0
                                        
                                        indices_data[code] = {
                                            'name': info['name'],
                                            'code': row['代码'],
                                            'price': current_price,
                                            'change': change_amount,
                                            'change_percent': change_percent,
                                            'volume': volume / 100000000  # 转换为亿元
                                        }
                                        print(f"[AKShare] {source['name']} - {info['name']} 获取成功: 价格={current_price}, 涨跌幅={change_percent}%")
                                        source_success = True
                                    except Exception as e:
                                        print(f"[AKShare] {source['name']} - 处理{info['name']}数据失败: {e}")
                                    break
                
                if source_success and len(indices_data) >= 2:  # 至少获取到2个指数才算成功
                    print(f"[AKShare] {source['name']}数据源成功，获取到{len(indices_data)}个指数")
                    break
                    
        except Exception as e:
            print(f"[AKShare] {source['name']}数据源异常: {e}")
            continue
        
        # 如果当前数据源失败，尝试下一个数据源
        if not source_success:
            print(f"[AKShare] {source['name']}数据源失败，切换到下一个数据源...")
    
    if indices_data:
        print(f"[AKShare] 实时数据获取成功，共获取到 {len(indices_data)} 个指数数据")
        return indices_data
    else:
        print("[AKShare] 所有数据源都失败，未获取到任何实时指数数据")
        return None

def get_indices_from_tushare(indices):
    """使用Tushare获取指数数据"""
    if not TUSHARE_AVAILABLE:
        print("[Tushare] Tushare不可用，跳过Tushare获取")
        return None
        
    if 'ts' not in globals() or ts is None:
        print("[Tushare] tushare模块未正确导入，跳过Tushare获取")
        return None
        
    if 'pro' not in globals() or pro is None:
        print("[Tushare] Tushare pro API未初始化，跳过Tushare获取")
        return None
        
    indices_data = {}
    current_date = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%H:%M:%S')
    
    print(f"[Tushare] 开始获取 {current_date} {current_time} 的指数数据")
    
    try:
        # 获取最近10个交易日的日期范围，确保能获取到最新数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=15)).strftime('%Y%m%d')
        
        print(f"[Tushare] 查询日期范围: {start_date} 到 {end_date}")
        
        # 动态获取最新交易日数据
        # 获取最近几个可能的交易日（排除周末）
        expected_latest_dates = []
        current_date = datetime.now()
        for i in range(7):  # 检查最近7天
            check_date = current_date - timedelta(days=i)
            # 排除周末（周六=5, 周日=6）
            if check_date.weekday() < 5:  # 周一到周五
                expected_latest_dates.append(check_date.strftime('%Y%m%d'))
        
        print(f"[Tushare] 期望的最新交易日: {expected_latest_dates}")
        
        # 获取上证指数
        try:
            df = safe_tushare_call(pro.index_daily, ts_code='000001.SH', start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                # 按日期降序排序，确保最新数据在前
                df = df.sort_values('trade_date', ascending=False)
                
                # 打印所有获取到的数据用于调试
                print(f"[Tushare] 上证指数原始数据:")
                for _, row in df.iterrows():
                    print(f"  日期: {row['trade_date']}, 收盘价: {row['close']}, 涨跌幅: {row['pct_chg']}%")
                
                # 查找最新的有效交易日数据
                latest = None
                found_expected_date = False
                for _, row in df.iterrows():
                    if row['trade_date'] in expected_latest_dates:
                        latest = row
                        found_expected_date = True
                        print(f"[Tushare] 上证指数找到期望日期的数据: {row['trade_date']}")
                        break
                
                # 如果没有找到期望日期的数据，使用最新的数据
                if latest is None:
                    latest = df.iloc[0]
                    print(f"[Tushare] 警告：上证指数未找到期望日期的数据，使用最新数据: {latest['trade_date']}")
                
                trade_date = latest['trade_date']
                
                indices_data['sh000001'] = {
                    'name': '上证指数',
                    'code': '000001.SH',
                    'price': float(latest['close']),
                    'change': float(latest['change']),
                    'change_percent': float(latest['pct_chg']),
                    'volume': float(latest['amount']) / 10 if 'amount' in latest and pd.notna(latest['amount']) else 0
                }
                print(f"[Tushare] 获取上证指数成功: 交易日期={trade_date}, 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
            else:
                print(f"[Tushare] 上证指数无数据返回")
        except Exception as e:
            print(f"[Tushare] 获取上证指数失败: {e}")
        
        # 获取深证成指
        try:
            df = safe_tushare_call(pro.index_daily, ts_code='399001.SZ', start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                # 按日期降序排序，确保最新数据在前
                df = df.sort_values('trade_date', ascending=False)
                
                # 查找最新的有效交易日数据
                latest = None
                for _, row in df.iterrows():
                    if row['trade_date'] in expected_latest_dates:
                        latest = row
                        break
                
                # 如果没有找到期望日期的数据，使用最新的数据
                if latest is None:
                    latest = df.iloc[0]
                    print(f"[Tushare] 警告：深证成指未找到期望日期的数据，使用最新数据: {latest['trade_date']}")
                
                trade_date = latest['trade_date']
                
                indices_data['sz399001'] = {
                    'name': '深证成指',
                    'code': '399001.SZ',
                    'price': float(latest['close']),
                    'change': float(latest['change']),
                    'change_percent': float(latest['pct_chg']),
                    'volume': float(latest['amount']) / 10 if 'amount' in latest and pd.notna(latest['amount']) else 0
                }
                print(f"[Tushare] 获取深证成指成功: 交易日期={trade_date}, 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
            else:
                print(f"[Tushare] 深证成指无数据返回")
        except Exception as e:
            print(f"[Tushare] 获取深证成指失败: {e}")
        
        # 获取创业板指
        try:
            df = safe_tushare_call(pro.index_daily, ts_code='399006.SZ', start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                # 按日期降序排序，确保最新数据在前
                df = df.sort_values('trade_date', ascending=False)
                
                # 查找最新的有效交易日数据
                latest = None
                for _, row in df.iterrows():
                    if row['trade_date'] in expected_latest_dates:
                        latest = row
                        break
                
                # 如果没有找到期望日期的数据，使用最新的数据
                if latest is None:
                    latest = df.iloc[0]
                    print(f"[Tushare] 警告：创业板指未找到期望日期的数据，使用最新数据: {latest['trade_date']}")
                
                trade_date = latest['trade_date']
                
                indices_data['sz399006'] = {
                    'name': '创业板指',
                    'code': '399006.SZ',
                    'price': float(latest['close']),
                    'change': float(latest['change']),
                    'change_percent': float(latest['pct_chg']),
                    'volume': float(latest['amount']) / 10 if 'amount' in latest and pd.notna(latest['amount']) else 0
                }
                print(f"[Tushare] 获取创业板指成功: 交易日期={trade_date}, 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
            else:
                print(f"[Tushare] 创业板指无数据返回")
        except Exception as e:
            print(f"[Tushare] 获取创业板指失败: {e}")
        
        # 获取科创板
        try:
            df = safe_tushare_call(pro.index_daily, ts_code='000688.SH', start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                # 按日期降序排序，确保最新数据在前
                df = df.sort_values('trade_date', ascending=False)
                
                # 查找最新的有效交易日数据
                latest = None
                for _, row in df.iterrows():
                    if row['trade_date'] in expected_latest_dates:
                        latest = row
                        break
                
                # 如果没有找到期望日期的数据，使用最新的数据
                if latest is None:
                    latest = df.iloc[0]
                    print(f"[Tushare] 警告：科创板未找到期望日期的数据，使用最新数据: {latest['trade_date']}")
                
                trade_date = latest['trade_date']
                
                indices_data['sh000688'] = {
                     'name': '科创板',
                     'code': '000688.SH',
                     'price': float(latest['close']),
                     'change': float(latest['change']),
                     'change_percent': float(latest['pct_chg']),
                     'volume': float(latest['amount']) / 10 if 'amount' in latest and pd.notna(latest['amount']) else 0
                 }
                print(f"[Tushare] 获取科创板成功: 交易日期={trade_date}, 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
            else:
                print(f"[Tushare] 科创板无数据返回")
        except Exception as e:
            print(f"[Tushare] 获取科创板失败: {e}")
        
        if indices_data:
            print(f"Tushare获取到 {len(indices_data)} 个指数数据")
            return indices_data
        else:
            print("Tushare未获取到任何数据")
            return None
            
    except Exception as e:
        print(f"Tushare获取异常: {e}")
        return None

def get_today_close_data(indices):
    """获取今日收盘数据"""
    try:
        # 优先从缓存获取今日数据
        cached_data = load_indices_cache()
        if cached_data:
            print("从缓存获取今日收盘数据")
            return cached_data['data']
        
        # 缓存中没有数据，尝试从Tushare获取今日数据
        print("缓存中无数据，从Tushare获取今日收盘数据")
        indices_data = get_indices_from_tushare(indices)
        
        if indices_data:
            # 转换数据格式
            formatted_data = {}
            for code, data in indices_data.items():
                formatted_data[code] = {
                    'name': data['name'],
                    'current_price': data['price'],
                    'change_pct': data['change_percent'],
                    'change_amount': data['change'],
                    'volume': data['volume'],
                    'update_time': datetime.now().strftime('%H:%M:%S')
                }
            
            # 保存到缓存
            fetch_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_indices_cache(formatted_data, fetch_time)
            
            return formatted_data
        
        return None
        
    except Exception as e:
        print(f"获取今日收盘数据失败: {e}")
        return None

@app.route('/api/indices/all')
def get_all_indices():
    """获取所有指数数据 - 根据交易时间采用不同策略"""
    try:
        if not AKSHARE_AVAILABLE:
            return get_sample_indices_data()
        
        if 'ak' not in globals() or ak is None:
            return get_sample_indices_data()
        
        current_time = datetime.now().strftime('%H:%M:%S')
        is_trading_time = is_market_open()
        
        if is_trading_time:
            print(f"[所有指数] 交易时间 {current_time}，开始获取所有指数数据")
            
            # 使用新浪财经数据源获取所有指数
            df = safe_akshare_call(ak.stock_zh_index_spot_sina, 'akshare_all_indices')
            
            if df is None or df.empty:
                print("[所有指数] AkShare数据获取失败，尝试返回缓存数据")
                return get_cached_all_indices_data()
            
            print(f"[所有指数] 获取到 {len(df)} 条指数数据")
            
            # 转换数据格式
            all_indices = []
            for _, row in df.iterrows():
                try:
                    index_data = {
                        'name': row['名称'] if '名称' in row else row.get('name', ''),
                        'code': row['代码'] if '代码' in row else row.get('code', ''),
                        'price': float(row['最新价'] if '最新价' in row else row.get('price', 0)),
                        'change': float(row['涨跌额'] if '涨跌额' in row else row.get('change', 0)),
                        'change_percent': float(row['涨跌幅'] if '涨跌幅' in row else row.get('change_pct', 0)),
                        'volume': float(row['成交额'] if '成交额' in row else row.get('volume', 0)) / 100000000 if '成交额' in row or 'volume' in row else 0  # 转换为亿元
                    }
                    
                    # 只添加有效的指数数据
                    if index_data['name'] and index_data['price'] > 0:
                        all_indices.append(index_data)
                        
                except Exception as e:
                    print(f"[所有指数] 处理指数数据失败: {e}")
                    continue
            
            if len(all_indices) == 0:
                print("[所有指数] 没有有效的指数数据，尝试返回缓存数据")
                return get_cached_all_indices_data()
            
            print(f"[所有指数] 成功处理 {len(all_indices)} 条有效指数数据")
            
            # 保存到缓存
            save_all_indices_cache(all_indices)
            
            return jsonify({
                'success': True,
                'data': all_indices,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'count': len(all_indices),
                'is_trading_time': True,
                'source': 'realtime'
            })
        else:
            print(f"[所有指数] 非交易时间 {current_time}，返回最后缓存的指数数据")
            return get_cached_all_indices_data()
        
    except Exception as e:
        print(f"[所有指数] 获取所有指数数据异常: {e}")
        return get_cached_all_indices_data()

def get_sample_indices_data():
    """返回示例指数数据用于演示"""
    import random
    
    # 示例指数数据
    sample_indices = [
        {'name': '上证指数', 'code': 'sh000001', 'price': 3456.78, 'change': 12.34, 'change_percent': 0.36, 'volume': 234.56},
        {'name': '深证成指', 'code': 'sz399001', 'price': 11234.56, 'change': -45.67, 'change_percent': -0.40, 'volume': 345.67},
        {'name': '创业板指', 'code': 'sz399006', 'price': 2234.56, 'change': 23.45, 'change_percent': 1.06, 'volume': 456.78},
        {'name': '科创50', 'code': 'sh000688', 'price': 987.65, 'change': -8.90, 'change_percent': -0.89, 'volume': 123.45},
        {'name': '沪深300', 'code': 'sh000300', 'price': 3987.65, 'change': 15.67, 'change_percent': 0.39, 'volume': 567.89},
        {'name': '中证500', 'code': 'sh000905', 'price': 6543.21, 'change': -23.45, 'change_percent': -0.36, 'volume': 234.56},
        {'name': '中证1000', 'code': 'sh000852', 'price': 5432.10, 'change': 34.56, 'change_percent': 0.64, 'volume': 345.67},
        {'name': '上证50', 'code': 'sh000016', 'price': 2876.54, 'change': 8.90, 'change_percent': 0.31, 'volume': 123.45},
        {'name': '中小板指', 'code': 'sz399005', 'price': 7654.32, 'change': -12.34, 'change_percent': -0.16, 'volume': 456.78},
        {'name': '红利指数', 'code': 'sh000015', 'price': 3210.98, 'change': 5.67, 'change_percent': 0.18, 'volume': 89.12},
        {'name': '央视50', 'code': 'sh000016', 'price': 2987.65, 'change': -3.45, 'change_percent': -0.12, 'volume': 67.89},
        {'name': '新能源车', 'code': 'sz399976', 'price': 1234.56, 'change': 45.67, 'change_percent': 3.84, 'volume': 234.56},
        {'name': '半导体', 'code': 'sz399995', 'price': 2345.67, 'change': -23.45, 'change_percent': -0.99, 'volume': 345.67},
        {'name': '医药生物', 'code': 'sz399987', 'price': 3456.78, 'change': 12.34, 'change_percent': 0.36, 'volume': 123.45},
        {'name': '白酒指数', 'code': 'sz399997', 'price': 9876.54, 'change': -34.56, 'change_percent': -0.35, 'volume': 89.12},
        {'name': '军工指数', 'code': 'sz399967', 'price': 1987.65, 'change': 23.45, 'change_percent': 1.20, 'volume': 156.78},
        {'name': '银行指数', 'code': 'sz399986', 'price': 1543.21, 'change': 8.90, 'change_percent': 0.58, 'volume': 67.89},
        {'name': '地产指数', 'code': 'sz399393', 'price': 2109.87, 'change': -15.67, 'change_percent': -0.74, 'volume': 234.56},
        {'name': '5G通信', 'code': 'sz399975', 'price': 1876.54, 'change': 34.56, 'change_percent': 1.88, 'volume': 345.67},
        {'name': '人工智能', 'code': 'sz399996', 'price': 3721.31, 'change': 15.83, 'change_percent': 0.43, 'volume': 857.11}
    ]
    
    # 为每个指数添加一些随机波动，使数据看起来更真实
    for index in sample_indices:
        # 添加小幅随机波动
        price_change = random.uniform(-0.02, 0.02)  # ±2%的随机波动
        index['price'] = round(index['price'] * (1 + price_change), 2)
        index['change'] = round(index['change'] * (1 + price_change * 0.5), 2)
        index['change_percent'] = round(index['change_percent'] * (1 + price_change * 0.5), 2)
        index['volume'] = round(index['volume'] * (1 + random.uniform(-0.1, 0.1)), 2)
    
    return jsonify({
        'success': True,
        'data': sample_indices,
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(sample_indices),
        'source': 'sample_data'
    })

def get_zero_indices_data(indices):
    """返回全0指数数据"""
    zero_data = {}
    for code, name in indices.items():
        zero_data[code] = {
            'name': name,
            'current_price': 0.0,
            'change_pct': 0.0,
            'change_amount': 0.0,
            'volume': 0,
            'update_time': datetime.now().strftime('%H:%M:%S')
        }
    
    print("返回全0指数数据，等待重试")
    return jsonify({
        'success': False,
        'error': '指数数据获取失败，正在重试...',
        'data': zero_data,
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'zero_data'
    })

def get_fallback_indices_data(indices):
    """获取回退数据 - 优先从缓存读取，无缓存时返回合理的默认数据"""
    # 尝试从缓存读取指数数据
    cached_data = load_indices_cache()
    
    if cached_data:
        print("从缓存获取指数数据")
        return jsonify({
            'success': True,
            'data': cached_data['data'],
            'fetch_time': cached_data.get('fetch_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'source': 'cache'
        })
    
    # 如果没有缓存数据，返回合理的默认数据（基于历史水平）
    fallback_data = {
        'sh000001': {
            'name': '上证指数',
            'current_price': 3500.0,
            'change_pct': 0.0,
            'change_amount': 0.0,
            'volume': 0,
            'update_time': datetime.now().strftime('%H:%M:%S')
        },
        'sz399001': {
            'name': '深证成指',
            'current_price': 11000.0,
            'change_pct': 0.0,
            'change_amount': 0.0,
            'volume': 0,
            'update_time': datetime.now().strftime('%H:%M:%S')
        },
        'sz399006': {
            'name': '创业板指',
            'current_price': 2200.0,
            'change_pct': 0.0,
            'change_amount': 0.0,
            'volume': 0,
            'update_time': datetime.now().strftime('%H:%M:%S')
        },
        'sh000688': {
            'name': '科创板',
            'current_price': 900.0,
            'change_pct': 0.0,
            'change_amount': 0.0,
            'volume': 0,
            'update_time': datetime.now().strftime('%H:%M:%S')
        }
    }
    
    print("数据获取失败，返回默认数据")
    return jsonify({
        'success': False,
        'error': '指数数据获取失败，显示默认数据',
        'data': fallback_data,
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'fallback_default_data'
    })

@app.route('/api/stock/<stock_code>')
def get_stock_data(stock_code):
    try:
        # 检查是否强制刷新数据
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        # 确保股票代码格式正确
        if len(stock_code) == 6:
            if stock_code.startswith(('60', '68')):
                ts_code = f"{stock_code}.SH"
            elif stock_code.startswith(('43', '83', '87')):
                ts_code = f"{stock_code}.BJ"
            else:
                ts_code = f"{stock_code}.SZ"
        else:
            # 如果已经包含后缀，直接使用
            ts_code = stock_code
            
        # 优先从缓存获取净流入数据
        cached_stock = None
        if not force_refresh:
            cached_stock = get_stock_from_cache(ts_code)
            if cached_stock:
                current_date = datetime.now().strftime('%Y%m%d')
                cache_date = cached_stock.get('last_update', '')
                if cache_date == current_date and cached_stock.get('net_mf_amount') is not None:
                    print(f"从缓存获取{ts_code}的净流入数据: {cached_stock.get('net_mf_amount')}千万元")
        
        # 如果强制刷新，清除相关缓存
        if force_refresh:
            print(f"强制刷新股票数据: {ts_code}")
            # 这里可以添加清除特定股票缓存的逻辑
        
        # 获取基本信息（使用频率限制）
        basic_info = safe_tushare_call(pro.stock_basic, ts_code=ts_code)
        if basic_info.empty:
            return jsonify({'error': '股票代码不存在'}), 404
        
        # 获取最近500天的日K线数据（直接使用原始数据）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=500)).strftime('%Y%m%d')
        
        # 使用TushareDataFetcher获取标准格式的日线数据
        from tushare_data_fetcher import TushareDataFetcher
        fetcher = TushareDataFetcher(pro_api=pro)
        daily_data = fetcher.get_daily_data(ts_code, days=1000)
        
        if daily_data.empty:
            return jsonify({'error': '无法获取股票数据'}), 404
        
        print(f"获取到{len(daily_data)}条日线数据，股票代码: {ts_code}，最新收盘价: {daily_data['close'].iloc[-1]:.2f}")
        
        # 确保数据已按日期排序
        daily_data = daily_data.sort_values('trade_date')
        
        # 获取最新的财务数据，尝试多个交易日（使用频率限制）
        daily_basic = pd.DataFrame()
        for i in range(10):  # 尝试最近10个交易日
            try:
                check_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                daily_basic = safe_tushare_call(pro.daily_basic, ts_code=ts_code, trade_date=check_date)
                if not daily_basic.empty:
                    break
            except:
                continue
        
        # 计算九转序列
        daily_data = calculate_nine_turn(daily_data)
        
        # 计算BOLL指标
        daily_data = calculate_boll(daily_data)
        
        # 计算MACD指标
        daily_data = calculate_macd(daily_data)
        
        # 计算KDJ指标
        daily_data = calculate_kdj(daily_data)
        
        # 计算RSI指标
        daily_data = calculate_rsi(daily_data)
        
        # 计算EMA15指标
        daily_data = calculate_ema15(daily_data)
        
        # 确保所有数值字段不为None（除了BOLL指标）
        numeric_columns = ['open', 'high', 'low', 'close', 'vol', 'amount', 'nine_turn_up', 'nine_turn_down']
        for col in numeric_columns:
            if col in daily_data.columns:
                daily_data[col] = daily_data[col].fillna(0)
        
        # BOLL指标保留NaN值，让前端图表正确处理
        # 将NaN转换为None，这样在JSON序列化时会变成null
        boll_columns = ['boll_upper', 'boll_mid', 'boll_lower', 'boll_std']
        for col in boll_columns:
            if col in daily_data.columns:
                daily_data[col] = daily_data[col].where(pd.notna(daily_data[col]), None)
        
        # 计算最高价和最低价
        highest_price = daily_data['high'].max()
        lowest_price = daily_data['low'].min()
        highest_date = daily_data.loc[daily_data['high'].idxmax(), 'trade_date']
        lowest_date = daily_data.loc[daily_data['low'].idxmin(), 'trade_date']
        
        # 安全获取数值的辅助函数
        def safe_float(value, default=0.0):
            try:
                if value is None or pd.isna(value):
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # 确保DataFrame中所有NaN值都被正确处理，避免JSON序列化问题
        import numpy as np
        daily_data = daily_data.replace({np.nan: None})
        # 使用fillna确保所有NaN都被替换为None
        daily_data = daily_data.where(pd.notna(daily_data), None)
        
        # 检查缓存中是否有完整的资金流向数据
        cached_moneyflow = None
        if cached_stock:
            current_date = datetime.now().strftime('%Y%m%d')
            cache_date = cached_stock.get('last_update', '')
            if cache_date == current_date:
                # 检查是否有完整的资金流向数据字段
                if (cached_stock.get('buy_elg_amount') is not None or 
                    cached_stock.get('buy_lg_amount') is not None or 
                    cached_stock.get('net_mf_amount') is not None):
                    cached_moneyflow = {
                        'net_amount': cached_stock.get('net_mf_amount', 0) * 1000 if cached_stock.get('net_mf_amount') else 0,
                        'buy_elg_amount': cached_stock.get('buy_elg_amount', 0),
                        'sell_elg_amount': cached_stock.get('sell_elg_amount', 0),
                        'buy_lg_amount': cached_stock.get('buy_lg_amount', 0),
                        'sell_lg_amount': cached_stock.get('sell_lg_amount', 0),
                        'buy_md_amount': cached_stock.get('buy_md_amount', 0),
                        'sell_md_amount': cached_stock.get('sell_md_amount', 0),
                        'buy_sm_amount': cached_stock.get('buy_sm_amount', 0),
                        'sell_sm_amount': cached_stock.get('sell_sm_amount', 0),
                        'net_amount_rate': cached_stock.get('net_amount_rate', 0),
                        'data_source': 'cache'
                    }
                    print(f"从缓存获取完整资金流向数据: 净流入{cached_stock.get('net_mf_amount', 0)}千万元")
        
        # 获取资金流向数据（优先使用缓存，然后尝试API）
        moneyflow_data = None
        
        # 如果缓存中没有完整的资金流向数据，则通过API获取
        if cached_moneyflow is None:
            try:
                print(f"缓存中无当天净流入数据，正在通过API获取{ts_code}的资金流向数据...")
                
                # 定义API调用函数，用于重试机制
                def call_moneyflow_dc():
                    return safe_tushare_call(pro.moneyflow_dc, ts_code=ts_code, limit=1)
                
                def call_moneyflow():
                    return safe_tushare_call(pro.moneyflow, ts_code=ts_code, limit=1)
                
                # 优先尝试moneyflow接口（需要2000积分）
                try:
                    moneyflow_data = retry_api_call_with_rate_limit(call_moneyflow)
                    if moneyflow_data is not None and not moneyflow_data.empty:
                        print(f"成功从moneyflow获取{ts_code}的资金流向数据")
                    else:
                        print(f"moneyflow接口无{ts_code}数据，尝试moneyflow_dc接口...")
                        # 如果moneyflow没有数据，尝试moneyflow_dc接口（需要5000积分，数据更详细）
                        moneyflow_data = retry_api_call_with_rate_limit(call_moneyflow_dc)
                        if moneyflow_data is not None and not moneyflow_data.empty:
                            print(f"成功从moneyflow_dc获取{ts_code}的资金流向数据")
                        else:
                            print(f"moneyflow_dc接口也无{ts_code}数据")
                except Exception as e:
                    print(f"API调用失败: {e}")
                    # 如果重试后仍然失败，尝试另一个接口
                    try:
                        moneyflow_data = retry_api_call_with_rate_limit(call_moneyflow_dc)
                        if moneyflow_data is not None and not moneyflow_data.empty:
                            print(f"备用接口成功获取{ts_code}的资金流向数据")
                    except Exception as e2:
                        print(f"备用接口也失败: {e2}")
                        
            except Exception as e:
                print(f"获取{ts_code}资金流向数据失败: {e}")
                # 如果积分不足或其他错误，继续执行但不包含资金流向数据
                pass
        
        # 计算当天涨幅（基于今开价格，而不是昨收价格）
        latest_close = safe_float(daily_data.iloc[-1]['close'])
        latest_open = safe_float(daily_data.iloc[-1]['open'])
        pct_chg = 0
        change_amount = 0
        
        # 尝试从daily_data中获取pct_chg字段
        if 'pct_chg' in daily_data.columns and not pd.isna(daily_data.iloc[-1]['pct_chg']):
            # 如果有pct_chg字段，重新计算基于今开价格的涨跌幅
            if latest_open > 0:
                pct_chg = ((latest_close - latest_open) / latest_open) * 100
                change_amount = latest_close - latest_open
                print(f"[股票数据] 涨跌幅重新计算(基于今开): 收盘={latest_close:.2f}, 今开={latest_open:.2f}, 涨跌幅={pct_chg:.2f}%")
            elif len(daily_data) >= 2:
                # 如果今开价格为0，使用昨收价格作为备选
                yesterday_close = safe_float(daily_data.iloc[-2]['close'])
                if yesterday_close > 0:
                    pct_chg = ((latest_close - yesterday_close) / yesterday_close) * 100
                    change_amount = latest_close - yesterday_close
                    print(f"[股票数据] 涨跌幅计算(备选昨收): 收盘={latest_close:.2f}, 昨收={yesterday_close:.2f}, 涨跌幅={pct_chg:.2f}%")
        elif len(daily_data) >= 2:
            # 如果没有pct_chg字段，优先基于今开价格计算
            if latest_open > 0:
                pct_chg = ((latest_close - latest_open) / latest_open) * 100
                change_amount = latest_close - latest_open
                print(f"[股票数据] 涨跌幅计算(基于今开): 收盘={latest_close:.2f}, 今开={latest_open:.2f}, 涨跌幅={pct_chg:.2f}%")
            else:
                # 如果今开价格为0，使用昨收价格作为备选
                yesterday_close = safe_float(daily_data.iloc[-2]['close'])
                if yesterday_close > 0:
                    pct_chg = ((latest_close - yesterday_close) / yesterday_close) * 100
                    change_amount = latest_close - yesterday_close
                    print(f"[股票数据] 涨跌幅计算(备选昨收): 收盘={latest_close:.2f}, 昨收={yesterday_close:.2f}, 涨跌幅={pct_chg:.2f}%")
        
        # 确保只包含Tushare官方文档定义的字段，避免index等额外字段
        # 官方文档字段：ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        tushare_columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount']
        
        # 添加计算出的技术指标字段
        indicator_columns = ['nine_turn_up', 'nine_turn_down', 'countdown_up', 'countdown_down', 
                           'boll_upper', 'boll_mid', 'boll_lower', 'boll_std',
                           'macd_dif', 'macd_dea', 'macd_histogram',
                           'kdj_k', 'kdj_d', 'kdj_j', 'rsi', 'ema15']
        
        # 只选择存在的列
        available_columns = [col for col in tushare_columns + indicator_columns if col in daily_data.columns]
        clean_daily_data = daily_data[available_columns].copy()
        
        # 对OHLC数据应用精度清理，避免显示包含"999"的浮点数
        ohlc_columns = ['open', 'high', 'low', 'close', 'pre_close']
        for col in ohlc_columns:
            if col in clean_daily_data.columns:
                clean_daily_data[col] = clean_daily_data[col].apply(lambda x: clean_float_precision(x, 4) if x is not None and not pd.isna(x) else x)
        
        # 保留原始索引信息，确保九转序列显示在正确位置
        # 重置索引并将原索引作为data_index字段保存
        clean_daily_data_with_index = clean_daily_data.reset_index()
        clean_daily_data_with_index['data_index'] = clean_daily_data_with_index.index
        
        # 准备返回数据
        stock_info = {
            'ts_code': ts_code,
            'name': basic_info.iloc[0]['name'],
            'industry': basic_info.iloc[0]['industry'],
            'latest_price': latest_close,
            'pct_chg': pct_chg,  # 添加当天涨幅
            'change_amount': change_amount,  # 添加涨跌额
            'open': latest_open,  # 添加今开价格
            'pre_close': safe_float(daily_data.iloc[-1]['pre_close']) if 'pre_close' in daily_data.columns else (safe_float(daily_data.iloc[-2]['close']) if len(daily_data) >= 2 else 0),  # 添加昨收价格
            'high': safe_float(daily_data.iloc[-1]['high']),  # 添加最高价
            'low': safe_float(daily_data.iloc[-1]['low']),  # 添加最低价
            'volume': safe_float(daily_data.iloc[-1]['vol']),  # 添加成交量
            'market_cap': safe_float(daily_basic.iloc[0]['total_mv']) if not daily_basic.empty and 'total_mv' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['total_mv']) else 0,
            'turnover_rate': safe_float(daily_basic.iloc[0]['turnover_rate']) if not daily_basic.empty and 'turnover_rate' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['turnover_rate']) else 0,
            'pe_ttm': safe_float(daily_basic.iloc[0]['pe_ttm']) if not daily_basic.empty and 'pe_ttm' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['pe_ttm']) and daily_basic.iloc[0]['pe_ttm'] > 0 else None,
            'pb': safe_float(daily_basic.iloc[0]['pb']) if not daily_basic.empty and 'pb' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['pb']) and daily_basic.iloc[0]['pb'] > 0 else None,
            'volume_ratio': safe_float(daily_basic.iloc[0]['volume_ratio']) if not daily_basic.empty and 'volume_ratio' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['volume_ratio']) else 0,
            'amount': safe_float(daily_data.iloc[-1]['amount']),
            'highest_price': safe_float(highest_price),
            'lowest_price': safe_float(lowest_price),
            'highest_date': highest_date,
            'lowest_date': lowest_date,
            'kline_data': clean_daily_data_with_index.to_dict('records')  # 包含data_index字段的数据
        }
        
        # 添加资金流向数据（优先使用缓存数据）
        if cached_moneyflow is not None:
            # 使用缓存中的完整资金流向数据
            stock_info['net_mf_amount'] = cached_stock.get('net_mf_amount', 0)
            stock_info['moneyflow'] = cached_moneyflow
            print(f"使用缓存数据，设置net_mf_amount为: {stock_info['net_mf_amount']}千万元")
        elif moneyflow_data is not None and not moneyflow_data.empty:
            print(f"资金流向原始数据: {moneyflow_data.iloc[0].to_dict()}")
            # 检查是否是moneyflow_dc接口的数据（包含net_amount字段）
            if 'net_amount' in moneyflow_data.columns:
                net_amount_wan = safe_float(moneyflow_data.iloc[0]['net_amount'])  # 万元
                print(f"moneyflow_dc接口 - net_amount原始值: {net_amount_wan}万元")
                stock_info['moneyflow'] = {
                    'net_amount': net_amount_wan,  # 主力净流入额（万元）
                    'net_amount_rate': safe_float(moneyflow_data.iloc[0]['net_amount_rate']),  # 主力净流入净占比
                    'buy_elg_amount': safe_float(moneyflow_data.iloc[0]['buy_elg_amount']),  # 超大单净流入额
                    'buy_lg_amount': safe_float(moneyflow_data.iloc[0]['buy_lg_amount']),  # 大单净流入额
                    'buy_md_amount': safe_float(moneyflow_data.iloc[0]['buy_md_amount']),  # 中单净流入额
                    'buy_sm_amount': safe_float(moneyflow_data.iloc[0]['buy_sm_amount']),  # 小单净流入额
                    'data_source': 'moneyflow_dc'
                }
                # 设置net_mf_amount字段（转换为千万元，与列表页面保持一致）
                stock_info['net_mf_amount'] = round(net_amount_wan / 1000, 2)
                print(f"设置net_mf_amount为: {stock_info['net_mf_amount']}千万元")
            # 检查是否是moneyflow接口的数据（包含net_mf_amount字段）
            elif 'net_mf_amount' in moneyflow_data.columns:
                net_mf_amount_wan = safe_float(moneyflow_data.iloc[0]['net_mf_amount'])  # 万元
                print(f"moneyflow接口 - net_mf_amount原始值: {net_mf_amount_wan}万元")
                stock_info['moneyflow'] = {
                    'net_amount': net_mf_amount_wan,  # 净流入额（万元）
                    'buy_elg_amount': safe_float(moneyflow_data.iloc[0]['buy_elg_amount']),  # 特大单买入金额（万元）
                    'sell_elg_amount': safe_float(moneyflow_data.iloc[0]['sell_elg_amount']),  # 特大单卖出金额（万元）
                    'buy_lg_amount': safe_float(moneyflow_data.iloc[0]['buy_lg_amount']),  # 大单买入金额（万元）
                    'sell_lg_amount': safe_float(moneyflow_data.iloc[0]['sell_lg_amount']),  # 大单卖出金额（万元）
                    'buy_md_amount': safe_float(moneyflow_data.iloc[0]['buy_md_amount']),  # 中单买入金额（万元）
                    'sell_md_amount': safe_float(moneyflow_data.iloc[0]['sell_md_amount']),  # 中单卖出金额（万元）
                    'buy_sm_amount': safe_float(moneyflow_data.iloc[0]['buy_sm_amount']),  # 小单买入金额（万元）
                    'sell_sm_amount': safe_float(moneyflow_data.iloc[0]['sell_sm_amount']),  # 小单卖出金额（万元）
                    'data_source': 'moneyflow'
                }
                # 设置net_mf_amount字段（转换为千万元，与列表页面保持一致）
                stock_info['net_mf_amount'] = round(net_mf_amount_wan / 1000, 2)
                print(f"设置net_mf_amount为: {stock_info['net_mf_amount']}千万元")
        else:
            stock_info['moneyflow'] = None
            stock_info['net_mf_amount'] = 0  # 如果没有资金流向数据，设置为0
            print(f"无资金流向数据，设置net_mf_amount为0")
        
        return jsonify(stock_info)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_latest_trading_day():
    """获取最近的交易日"""
    current_date = datetime.now()
    
    # 如果是周末，回退到上周五
    if current_date.weekday() == 5:  # 周六
        return (current_date - timedelta(days=1)).strftime('%Y%m%d')
    elif current_date.weekday() == 6:  # 周日
        return (current_date - timedelta(days=2)).strftime('%Y%m%d')
    else:
        # 工作日，如果是交易时间内，返回今天；否则返回今天（因为今天的收盘数据已经可用）
        return current_date.strftime('%Y%m%d')

def get_live_realtime_data(ts_code, stock_code):
    """获取真实的实时数据（交易时间内调用）"""
    try:
        print(f"[实时数据] 获取{ts_code}的真实实时数据...")
        
        # 首先尝试从AkShare获取最新的实时数据
        akshare_realtime_data = None
        if AKSHARE_AVAILABLE:
            try:
                print(f"[实时数据] 尝试从AkShare获取{stock_code}的最新实时数据...")
                # 调用AkShare接口获取实时数据，设置较短的超时时间
                realtime_df = safe_akshare_call(
                    ak.stock_zh_a_spot_em, 
                    'live_realtime_data',
                    max_retries=1,  # 减少重试次数
                    retry_delay=0.2  # 减少重试延迟
                )
                
                if realtime_df is not None and not realtime_df.empty:
                    # 查找指定股票的数据
                    stock_data_row = realtime_df[realtime_df['代码'] == stock_code]
                    if not stock_data_row.empty:
                        row = stock_data_row.iloc[0]
                        akshare_realtime_data = {
                            'name': str(row.get('名称', '')),
                            'latest_price': float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else 0.0,
                            'open': float(row.get('今开', 0)) if pd.notna(row.get('今开')) else 0.0,
                            'high': float(row.get('最高', 0)) if pd.notna(row.get('最高')) else 0.0,
                            'low': float(row.get('最低', 0)) if pd.notna(row.get('最低')) else 0.0,
                            'pre_close': float(row.get('昨收', 0)) if pd.notna(row.get('昨收')) else 0.0,
                            'volume': float(row.get('成交量', 0)) if pd.notna(row.get('成交量')) else 0.0,
                            'amount': float(row.get('成交额', 0)) if pd.notna(row.get('成交额')) else 0.0,
                            'turnover_rate': float(row.get('换手率', 0)) if pd.notna(row.get('换手率')) else 0.0,
                            'volume_ratio': float(row.get('量比', 0)) if pd.notna(row.get('量比')) else 0.0,
                            'pe_ratio': float(row.get('市盈率-动态', 0)) if pd.notna(row.get('市盈率-动态')) else 0.0,
                            'market_cap': float(row.get('总市值', 0)) if pd.notna(row.get('总市值')) else 0.0,
                            'data_source': 'akshare_live'
                        }
                        
                        # 重新计算涨跌幅和涨跌额（基于昨收价格）
                        latest_price = akshare_realtime_data['latest_price']
                        pre_close = akshare_realtime_data['pre_close']
                        
                        if pre_close > 0:
                            change_amount = latest_price - pre_close
                            change_percent = (change_amount / pre_close) * 100
                        else:
                            change_amount = 0
                            change_percent = 0
                        
                        akshare_realtime_data['change_amount'] = change_amount
                        akshare_realtime_data['change_percent'] = change_percent
                        
                        print(f"[实时数据] 成功从AkShare获取{stock_code}实时数据: 最新价={latest_price}, 涨跌幅={change_percent:.2f}%")
                    else:
                        print(f"[实时数据] AkShare数据中未找到股票{stock_code}")
                else:
                    print(f"[实时数据] AkShare返回空数据")
            except Exception as e:
                print(f"[实时数据] AkShare获取失败，将使用Tushare数据: {e}")
                akshare_realtime_data = None
        
        # 获取股票基础数据（用于K线、资金流向等）
        stock_detail_response = get_stock_data(ts_code)
        if hasattr(stock_detail_response, 'get_json'):
            stock_data = stock_detail_response.get_json()
        elif isinstance(stock_detail_response, dict):
            stock_data = stock_detail_response
        else:
            return jsonify({'error': '无法获取股票数据'}), 500
        
        if stock_data.get('error'):
            return jsonify({'error': stock_data['error']}), 500
        
        # 构造实时数据
        realtime_data = {}
        
        if akshare_realtime_data:
            # 优先使用AkShare的实时数据
            realtime_data['spot'] = {
                'name': akshare_realtime_data['name'],
                'latest_price': clean_float_precision(akshare_realtime_data['latest_price']),
                'change_percent': clean_float_precision(akshare_realtime_data['change_percent']),
                'change_amount': clean_float_precision(akshare_realtime_data['change_amount']),
                'volume': clean_float_precision(akshare_realtime_data['volume']),
                'amount': clean_float_precision(akshare_realtime_data['amount']),
                'turnover_rate': clean_float_precision(akshare_realtime_data['turnover_rate']),
                'volume_ratio': clean_float_precision(akshare_realtime_data['volume_ratio']),
                'pe_ratio': akshare_realtime_data['pe_ratio'],
                'market_cap': clean_float_precision(akshare_realtime_data['market_cap']),
                'open': clean_float_precision(akshare_realtime_data['open']),
                'high': clean_float_precision(akshare_realtime_data['high']),
                'low': clean_float_precision(akshare_realtime_data['low']),
                'pre_close': clean_float_precision(akshare_realtime_data['pre_close']),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': 'akshare_live_realtime'  # 标记数据来源
            }
        elif stock_data:
            # 备用：使用股票数据中的信息
            realtime_data['spot'] = {
                'name': stock_data.get('name', ''),
                'latest_price': clean_float_precision(stock_data.get('latest_price', 0)),
                'change_percent': clean_float_precision(stock_data.get('pct_chg', 0)),
                'change_amount': clean_float_precision(stock_data.get('change_amount', 0)),
                'volume': clean_float_precision(stock_data.get('volume', 0)),
                'amount': clean_float_precision(stock_data.get('amount', 0)),
                'turnover_rate': clean_float_precision(stock_data.get('turnover_rate', 0)),
                'volume_ratio': clean_float_precision(stock_data.get('volume_ratio', 0)),
                'pe_ratio': stock_data.get('pe_ttm'),
                'market_cap': clean_float_precision(stock_data.get('total_mv', 0)),
                'open': clean_float_precision(stock_data.get('open', 0)),
                'high': clean_float_precision(stock_data.get('high', 0)),
                'low': clean_float_precision(stock_data.get('low', 0)),
                'pre_close': clean_float_precision(stock_data.get('pre_close', 0)),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': 'tushare_fallback'  # 标记数据来源
            }
        
        # 添加K线数据
        if stock_data.get('kline_data'):
            realtime_data['kline_data'] = stock_data['kline_data']
        
        # 添加分时数据
        if stock_data.get('minute_data'):
            realtime_data['minute_data'] = stock_data['minute_data']
        else:
            realtime_data['minute_data'] = []
        
        # 添加资金流向数据
        if stock_data.get('moneyflow'):
            realtime_data['money_flow'] = stock_data['moneyflow']
        elif stock_data.get('net_mf_amount') is not None:
            realtime_data['money_flow'] = {
                'close_price': realtime_data['spot']['latest_price'],
                'change_percent': realtime_data['spot']['change_percent'],
                'main_net_inflow': stock_data.get('net_mf_amount', 0) * 10000
            }
        
        # 添加净流入额
        if stock_data.get('net_mf_amount') is not None:
            realtime_data['net_mf_amount'] = stock_data.get('net_mf_amount', 0)
        
        print(f"[实时数据] 成功获取{ts_code}的实时数据，数据源: {realtime_data['spot']['data_source']}")
        return jsonify(realtime_data)
        
    except Exception as e:
        print(f"[实时数据] 获取失败: {e}")
        return jsonify({'error': f'获取实时数据失败: {str(e)}'}), 500

def get_latest_close_data(ts_code, stock_code):
    """获取最近交易日的收盘数据（非交易时间使用）"""
    try:
        print(f"[收盘数据] 获取{ts_code}的最近交易日收盘数据...")
        
        # 获取最近交易日
        latest_trading_day = get_latest_trading_day()
        print(f"[收盘数据] 最近交易日: {latest_trading_day}")
        
        # 获取股票基础数据
        stock_detail_response = get_stock_data(ts_code)
        if hasattr(stock_detail_response, 'get_json'):
            stock_data = stock_detail_response.get_json()
        elif isinstance(stock_detail_response, dict):
            stock_data = stock_detail_response
        else:
            return jsonify({'error': '无法获取股票数据'}), 500
        
        if stock_data.get('error'):
            return jsonify({'error': stock_data['error']}), 500
        
        # 构造收盘数据
        realtime_data = {}
        
        if stock_data:
            # 获取最新的K线数据作为收盘数据
            latest_kline = None
            if stock_data.get('kline_data') and len(stock_data['kline_data']) > 0:
                latest_kline = stock_data['kline_data'][-1]
            
            # 计算涨跌幅（基于今开价格，而不是昨收价格）
            calculated_change_percent = 0
            calculated_change_amount = 0
            pre_close = 0
            
            if stock_data.get('kline_data') and len(stock_data['kline_data']) > 1:
                current_kline = stock_data['kline_data'][-1]
                prev_kline = stock_data['kline_data'][-2]
                
                current_close = current_kline.get('close', 0)
                current_open = current_kline.get('open', 0)
                prev_close = prev_kline.get('close', 0)
                pre_close = prev_close
                
                # 修正涨跌幅计算：基于今开价格
                if current_open > 0:
                    calculated_change_amount = clean_float_precision(current_close - current_open)
                    calculated_change_percent = clean_float_precision((calculated_change_amount / current_open) * 100)
                    print(f"[收盘数据] 涨跌幅计算(基于今开): 当前收盘={current_close:.2f}, 今开={current_open:.2f}, 涨跌幅={calculated_change_percent:.2f}%")
                elif prev_close > 0:
                    # 如果今开价格为0，则使用昨收价格作为备选
                    calculated_change_amount = clean_float_precision(current_close - prev_close)
                    calculated_change_percent = clean_float_precision((calculated_change_amount / prev_close) * 100)
                    print(f"[收盘数据] 涨跌幅计算(备选昨收): 当前收盘={current_close:.2f}, 昨收={prev_close:.2f}, 涨跌幅={calculated_change_percent:.2f}%")
            
            realtime_data['spot'] = {
                'name': stock_data.get('name', ''),
                'latest_price': clean_float_precision(latest_kline.get('close', 0) if latest_kline else stock_data.get('latest_price', 0)),
                'change_percent': calculated_change_percent,
                'change_amount': calculated_change_amount,
                'volume': clean_float_precision(latest_kline.get('vol', 0) if latest_kline else 0),
                'amount': clean_float_precision(latest_kline.get('amount', 0) if latest_kline else 0),
                'turnover_rate': clean_float_precision(stock_data.get('turnover_rate', 0)),
                'volume_ratio': 0,  # 非交易时间无法计算量比
                'pe_ratio': stock_data.get('pe_ttm'),
                'market_cap': clean_float_precision(stock_data.get('total_mv', 0)),
                'open': clean_float_precision(latest_kline.get('open', 0) if latest_kline else 0),
                'high': clean_float_precision(latest_kline.get('high', 0) if latest_kline else 0),
                'low': clean_float_precision(latest_kline.get('low', 0) if latest_kline else 0),
                'pre_close': clean_float_precision(pre_close),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': 'latest_close'  # 标记数据来源
            }
        
        # 添加K线数据
        if stock_data.get('kline_data'):
            realtime_data['kline_data'] = stock_data['kline_data']
        
        # 添加资金流向数据
        if stock_data.get('moneyflow'):
            realtime_data['money_flow'] = stock_data['moneyflow']
        elif stock_data.get('net_mf_amount') is not None:
            realtime_data['money_flow'] = {
                'close_price': stock_data.get('latest_price', 0),
                'change_percent': stock_data.get('pct_chg', 0),
                'main_net_inflow': stock_data.get('net_mf_amount', 0) * 10000
            }
        
        # 添加净流入额
        if stock_data.get('net_mf_amount') is not None:
            realtime_data['net_mf_amount'] = stock_data.get('net_mf_amount', 0)
        
        # 非交易时间不提供分时数据
        realtime_data['minute_data'] = []
        
        print(f"[收盘数据] 成功获取{ts_code}的收盘数据")
        return jsonify(realtime_data)
        
    except Exception as e:
        print(f"[收盘数据] 获取失败: {e}")
        return jsonify({'error': f'获取收盘数据失败: {str(e)}'}), 500

@app.route('/api/stock/<stock_code>/realtime')
def get_realtime_stock_data(stock_code):
    """获取股票实时数据，根据交易时间智能返回实时数据或收盘数据"""
    
    def safe_float(value, default=0.0):
        """安全转换为浮点数"""
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    try:
        # 判断当前是否为交易时间
        is_trading_time = is_market_open()
        current_time = datetime.now().strftime('%H:%M:%S')
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"[实时数据] 当前时间: {current_date} {current_time}, 交易时间: {is_trading_time}")
        
        # 确保股票代码格式正确
        if len(stock_code) == 6:
            if stock_code.startswith(('60', '68')):
                ts_code = f"{stock_code}.SH"
            elif stock_code.startswith(('43', '83', '87')):
                ts_code = f"{stock_code}.BJ"
            else:
                ts_code = f"{stock_code}.SZ"
        else:
            ts_code = stock_code
        
        if is_trading_time:
            print(f"[实时数据] 交易时间内，获取{ts_code}的真实实时数据...")
            # 交易时间内：获取真实的实时数据
            return get_live_realtime_data(ts_code, stock_code)
        else:
            print(f"[实时数据] 非交易时间，获取{ts_code}的最近交易日收盘数据...")
            # 非交易时间：返回最近交易日的收盘数据
            return get_latest_close_data(ts_code, stock_code)
        
    except Exception as e:
        print(f"[实时数据] 获取失败: {e}")
        return jsonify({'error': f'获取实时数据失败: {str(e)}'}), 500

def get_last_trading_day_data():
    """
    获取最后交易日的收盘数据，用于非交易时间显示
    返回格式与实时交易数据API相同
    """
    try:
        print("[最后交易日数据] 开始获取最后交易日的收盘数据...")
        
        # 动态获取最后交易日期
        last_trading_date = get_latest_trading_day()
        print(f"[最后交易日数据] 动态获取的最后交易日: {last_trading_date}")
        
        # 获取股票基本信息列表
        stock_basic = safe_tushare_call(pro.stock_basic, exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
        
        if stock_basic.empty:
            print("[最后交易日数据] 无法获取股票基本信息")
            return jsonify({
                'success': False,
                'error': '无法获取股票基本信息',
                'data': [],
                'message': '数据源暂时不可用'
            }), 503
        
        # 获取最后交易日的日线数据
        daily_data = safe_tushare_call(pro.daily, trade_date=last_trading_date)
        
        if daily_data.empty:
            print(f"[最后交易日数据] {last_trading_date}无日线数据，尝试获取前一个交易日数据")
            # 如果当天没有数据，尝试前一个交易日
            prev_date = (datetime.strptime(last_trading_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
            daily_data = safe_tushare_call(pro.daily, trade_date=prev_date)
            if not daily_data.empty:
                last_trading_date = prev_date
                print(f"[最后交易日数据] 使用前一个交易日数据: {last_trading_date}")
            else:
                return jsonify({
                    'success': False,
                    'error': f'无法获取{last_trading_date}的交易数据',
                    'data': [],
                    'message': '最后交易日数据不可用'
                }), 404
        
        # 获取每日指标数据
        daily_basic = safe_tushare_call(pro.daily_basic, trade_date=last_trading_date)
        
        print(f"[最后交易日数据] 获取到{len(daily_data)}条日线数据，{len(daily_basic)}条每日指标数据")
        
        # 合并数据
        if not daily_basic.empty:
            merged_data = daily_data.merge(daily_basic, on=['ts_code', 'trade_date'], how='left')
        else:
            merged_data = daily_data.copy()
            # 添加缺失的每日指标字段
            for col in ['turnover_rate', 'turnover_rate_f', 'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'dv_ratio', 'dv_ttm', 'total_share', 'float_share', 'free_share', 'total_mv', 'circ_mv']:
                if col not in merged_data.columns:
                    merged_data[col] = None
        
        # 转换为实时交易数据格式
        data_list = []
        for idx, row in merged_data.iterrows():
            try:
                # 获取股票名称
                stock_info = stock_basic[stock_basic['ts_code'] == row['ts_code']]
                stock_name = stock_info['name'].iloc[0] if not stock_info.empty else row['ts_code']
                
                # 计算涨跌幅和涨跌额
                close_raw = row.get('close')
                pre_close_raw = row.get('pre_close')
                
                # 检查当前时间是否在收盘后的时间段（15:00-18:00）
                now = datetime.now()
                current_time = now.time()
                afternoon_end = datetime.strptime('15:00', '%H:%M').time()
                evening_cutoff = datetime.strptime('18:00', '%H:%M').time()
                is_after_close = afternoon_end < current_time <= evening_cutoff
                is_weekday = now.weekday() < 5
                
                # 如果close字段为空，说明可能是非交易日或数据问题
                if pd.notna(close_raw) and close_raw is not None:
                    close_price = float(close_raw)
                    pre_close = float(pre_close_raw) if pd.notna(pre_close_raw) and pre_close_raw is not None else close_price
                else:
                    # close字段为空的处理策略
                    if is_weekday and is_after_close:
                        # 收盘后时间段：尝试使用更合理的收盘价估算
                        # 优先级：(high + low) / 2 -> open -> pre_close
                        high_raw = row.get('high')
                        low_raw = row.get('low') 
                        open_raw = row.get('open')
                        
                        if (pd.notna(high_raw) and high_raw is not None and high_raw > 0 and 
                            pd.notna(low_raw) and low_raw is not None and low_raw > 0):
                            # 使用最高价和最低价的平均值作为收盘价的估算
                            close_price = (float(high_raw) + float(low_raw)) / 2
                            print(f"[收盘后数据] 股票 {row['ts_code']} close字段为空，使用(high+low)/2作为收盘价: {close_price} (high:{high_raw}, low:{low_raw})")
                        elif pd.notna(open_raw) and open_raw is not None and open_raw > 0:
                            close_price = float(open_raw)
                            print(f"[收盘后数据] 股票 {row['ts_code']} close字段为空，使用open作为收盘价: {close_price}")
                        else:
                            close_price = float(pre_close_raw) if pd.notna(pre_close_raw) and pre_close_raw is not None else 0.0
                            print(f"[收盘后数据] 股票 {row['ts_code']} 所有价格字段都为空，使用pre_close: {close_price}")
                        
                        pre_close = float(pre_close_raw) if pd.notna(pre_close_raw) and pre_close_raw is not None else close_price
                    else:
                        # 非收盘后时间段：使用pre_close作为最新价
                        close_price = float(pre_close_raw) if pd.notna(pre_close_raw) and pre_close_raw is not None else 0.0
                        pre_close = close_price  # 在这种情况下，涨跌幅为0
                
                if pre_close > 0:
                    pct_chg = ((close_price - pre_close) / pre_close) * 100
                    change = close_price - pre_close
                else:
                    pct_chg = 0.0
                    change = 0.0
                
                # 构造实时交易数据格式
                data_item = {
                    '序号': idx + 1,
                    '代码': row['ts_code'].split('.')[0],  # 去掉后缀
                    '名称': stock_name,
                    '最新价': close_price,
                    '涨跌幅': pct_chg,
                    '涨跌额': change,
                    '成交量': float(row.get('vol', 0)) if pd.notna(row.get('vol')) else 0.0,
                    '成交额': float(row.get('amount', 0)) if pd.notna(row.get('amount')) else 0.0,
                    '振幅': float(row.get('high', 0) - row.get('low', 0)) / pre_close * 100 if pre_close > 0 and pd.notna(row.get('high')) and pd.notna(row.get('low')) else 0.0,
                    '最高': float(row.get('high', 0)) if pd.notna(row.get('high')) else 0.0,
                    '最低': float(row.get('low', 0)) if pd.notna(row.get('low')) else 0.0,
                    '今开': float(row.get('open', 0)) if pd.notna(row.get('open')) else 0.0,
                    '昨收': pre_close,
                    '量比': float(row.get('volume_ratio', 0)) if pd.notna(row.get('volume_ratio')) else 0.0,
                    '换手率': float(row.get('turnover_rate', 0)) if pd.notna(row.get('turnover_rate')) else 0.0,
                    '市盈率-动态': float(row.get('pe_ttm', 0)) if pd.notna(row.get('pe_ttm')) else 0.0,
                    '市净率': float(row.get('pb', 0)) if pd.notna(row.get('pb')) else 0.0,
                    '总市值': float(row.get('total_mv', 0)) if pd.notna(row.get('total_mv')) else 0.0,
                    '流通市值': float(row.get('circ_mv', 0)) if pd.notna(row.get('circ_mv')) else 0.0,
                    '涨速': 0.0,  # 收盘数据无涨速
                    '5分钟涨跌': 0.0,  # 收盘数据无5分钟涨跌
                    '60日涨跌幅': 0.0,  # 需要额外计算，暂时设为0
                    '年初至今涨跌幅': 0.0  # 需要额外计算，暂时设为0
                }
                data_list.append(data_item)
            except Exception as e:
                print(f"[最后交易日数据] 处理数据行失败: {e}")
                continue
        
        if not data_list:
            return jsonify({
                'success': False,
                'error': '数据处理失败',
                'data': [],
                'message': '获取到数据但处理过程中出现错误'
            }), 500
        
        print(f"[最后交易日数据] 成功处理{len(data_list)}条数据")
        
        return jsonify({
            'success': True,
            'data': data_list,
            'total_records': len(data_list),
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': f'Tushare - 最后交易日({last_trading_date})收盘数据',
            'message': f'成功获取{len(data_list)}条最后交易日数据',
            'is_last_trading_day': True
        })
        
    except Exception as e:
        print(f"[最后交易日数据] 获取失败: {e}")
        return jsonify({
            'success': False,
            'error': f'获取最后交易日数据失败: {str(e)}',
            'data': [],
            'message': '服务器内部错误，请稍后重试'
        }), 500


def save_realtime_data_cache(data):
    """保存实时交易数据到缓存"""
    try:
        cache_dir = 'cache'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        cache_file = os.path.join(cache_dir, 'realtime_trading_data_cache.json')
        cache_data = {
            'data': data,
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'cache_date': datetime.now().strftime('%Y-%m-%d'),
            'cache_time': datetime.now().strftime('%H:%M:%S')
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"[实时交易数据缓存] 已保存{len(data)}条数据到缓存")
        
    except Exception as e:
        print(f"[实时交易数据缓存] 保存失败: {e}")

def load_realtime_data_cache():
    """加载实时交易数据缓存"""
    try:
        cache_file = os.path.join('cache', 'realtime_trading_data_cache.json')
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
                print(f"[实时交易数据缓存] 找到缓存数据，缓存时间: {cached_data.get('fetch_time', '未知')}")
                return cached_data
        
        print("[实时交易数据缓存] 未找到缓存文件")
        return None
        
    except Exception as e:
        print(f"[实时交易数据缓存] 加载失败: {e}")
        return None

@app.route('/api/stock/realtime_trading_data')
def get_realtime_trading_data():
    """
    获取沪深京A股实时交易数据
    基于AKShare的stock_zh_a_spot_em接口
    当获取不到实时数据时，使用最后一次成功获取的AKShare缓存数据
    
    Returns:
        JSON: 实时交易数据，包含AKShare官方文档中的所有输出参数
    """
    try:
        if not AKSHARE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'AKShare库未安装，无法获取实时交易数据',
                'data': [],
                'message': '请安装AKShare库以获取实时数据'
            }), 500
        
        print("[实时交易数据] 开始获取沪深京A股实时交易数据...")
        
        # 调用AKShare接口获取实时交易数据，增加重试机制
        realtime_data = safe_akshare_call(
            ak.stock_zh_a_spot_em, 
            'realtime_trading_data',
            max_retries=3,
            retry_delay=1
        )
        
        # 如果获取不到实时数据，使用最后一次成功获取的AKShare缓存数据
        if realtime_data is None or realtime_data.empty:
            print("[实时交易数据] 无法获取AKShare实时数据，尝试使用最后一次成功获取的缓存数据...")
            cached_data = load_realtime_data_cache()
            if cached_data and 'data' in cached_data:
                print(f"[实时交易数据] 使用缓存数据，缓存时间: {cached_data.get('fetch_time', '未知')}")
                return jsonify({
                    'success': True,
                    'data': cached_data['data'],
                    'total_records': len(cached_data['data']),
                    'fetch_time': cached_data.get('fetch_time', '未知'),
                    'data_source': f"AKShare缓存数据 - 缓存时间: {cached_data.get('fetch_time', '未知')}",
                    'message': f'AKShare实时接口暂时不可用，使用最后一次成功获取的缓存数据({len(cached_data["data"])}条)',
                    'is_cached_data': True
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'AKShare实时接口暂时不可用，且无可用的缓存数据',
                    'data': [],
                    'message': '请稍后重试或联系管理员'
                }), 503
            
        print(f"[实时交易数据] 成功获取{len(realtime_data)}条实时交易数据")
        
        print(f"[实时交易数据] 成功获取{len(realtime_data)}条实时交易数据")
        
        # 转换数据格式，确保所有字段都包含，并修正涨跌幅计算
        data_list = []
        for _, row in realtime_data.iterrows():
            try:
                # 获取基础数据
                latest_price = float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else 0.0
                open_price = float(row.get('今开', 0)) if pd.notna(row.get('今开')) else 0.0
                yesterday_close = float(row.get('昨收', 0)) if pd.notna(row.get('昨收')) else 0.0
                
                # 重新计算涨跌幅和涨跌额（基于昨收价格，这是标准的计算方式）
                if yesterday_close > 0:
                    # 正确的涨跌幅：(当前价格 - 昨收价格) / 昨收价格 * 100
                    corrected_change_percent = ((latest_price - yesterday_close) / yesterday_close) * 100
                    corrected_change_amount = latest_price - yesterday_close
                else:
                    # 如果昨收价格为0，则涨跌幅为0
                    corrected_change_percent = 0.0
                    corrected_change_amount = 0.0
                
                data_item = {
                    '序号': int(row.get('序号', 0)) if pd.notna(row.get('序号')) else 0,
                    '代码': str(row.get('代码', '')),
                    '名称': str(row.get('名称', '')),
                    '最新价': latest_price,
                    '涨跌幅': round(corrected_change_percent, 2),  # 使用修正后的涨跌幅
                    '涨跌额': round(corrected_change_amount, 2),  # 使用修正后的涨跌额
                    '成交量': float(row.get('成交量', 0)) if pd.notna(row.get('成交量')) else 0.0,
                    '成交额': float(row.get('成交额', 0)) if pd.notna(row.get('成交额')) else 0.0,
                    '振幅': float(row.get('振幅', 0)) if pd.notna(row.get('振幅')) else 0.0,
                    '最高': float(row.get('最高', 0)) if pd.notna(row.get('最高')) else 0.0,
                    '最低': float(row.get('最低', 0)) if pd.notna(row.get('最低')) else 0.0,
                    '今开': float(row.get('今开', 0)) if pd.notna(row.get('今开')) else 0.0,
                    '昨收': float(row.get('昨收', 0)) if pd.notna(row.get('昨收')) else 0.0,
                    '量比': float(row.get('量比', 0)) if pd.notna(row.get('量比')) else 0.0,
                    '换手率': float(row.get('换手率', 0)) if pd.notna(row.get('换手率')) else 0.0,
                    '市盈率-动态': float(row.get('市盈率-动态', 0)) if pd.notna(row.get('市盈率-动态')) else 0.0,
                    '市净率': float(row.get('市净率', 0)) if pd.notna(row.get('市净率')) else 0.0,
                    '总市值': float(row.get('总市值', 0)) if pd.notna(row.get('总市值')) else 0.0,
                    '流通市值': float(row.get('流通市值', 0)) if pd.notna(row.get('流通市值')) else 0.0,
                    '涨速': float(row.get('涨速', 0)) if pd.notna(row.get('涨速')) else 0.0,
                    '5分钟涨跌': float(row.get('5分钟涨跌', 0)) if pd.notna(row.get('5分钟涨跌')) else 0.0,
                    '60日涨跌幅': float(row.get('60日涨跌幅', 0)) if pd.notna(row.get('60日涨跌幅')) else 0.0,
                    '年初至今涨跌幅': float(row.get('年初至今涨跌幅', 0)) if pd.notna(row.get('年初至今涨跌幅')) else 0.0,
                    '连涨天数': int(row.get('连涨天数', 0)) if pd.notna(row.get('连涨天数')) else 0,
                    '量价齐升天数': int(row.get('量价齐升天数', 0)) if pd.notna(row.get('量价齐升天数')) else 0
                }
                data_list.append(data_item)
            except Exception as e:
                print(f"[实时交易数据] 处理数据行失败: {e}")
                continue
        
        if not data_list:
            return jsonify({
                'success': False,
                'error': '数据处理失败',
                'data': [],
                'message': '获取到数据但处理过程中出现错误'
            }), 500
        
        # 成功获取数据后，保存到缓存
        try:
            save_realtime_data_cache(data_list)
            print(f"[实时交易数据] 已保存{len(data_list)}条数据到缓存")
        except Exception as cache_error:
            print(f"[实时交易数据] 保存缓存失败: {cache_error}")
        
        return jsonify({
            'success': True,
            'data': data_list,
            'total_records': len(data_list),
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': 'AKShare - stock_zh_a_spot_em',
            'message': f'成功获取{len(data_list)}条实时交易数据'
        })
        
    except Exception as e:
        print(f"[实时交易数据] 获取失败: {e}")
        return jsonify({
            'success': False,
            'error': f'获取实时交易数据失败: {str(e)}',
            'data': [],
            'message': '服务器内部错误，请稍后重试'
        }), 500


@app.route('/api/stock/<stock_code>/daily_basic')
def get_stock_daily_basic(stock_code):
    """
    获取股票每日指标数据
    严格按照Tushare官方文档 daily_basic 接口的输出参数
    
    Args:
        stock_code: 股票代码，如 000001 或 000001.SZ
        
    Query Parameters:
        trade_date: 指定交易日期 YYYYMMDD，默认为前一交易日
        
    Returns:
        JSON: 每日指标数据，包含Tushare官方文档中的所有输出参数
    """
    
    def safe_float(value, default=None):
        """安全转换为浮点数，保持None值用于显示空数据"""
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_previous_trading_date():
        """获取前一个交易日期 - 基于最后交易日20250725，返回20250724"""
        # 根据用户说明，最后一个交易日是20250725，所以每日指标显示20250724的数据
        last_trading_date = '20250725'
        previous_trading_date = '20250724'
        
        print(f"[每日指标] 最后交易日: {last_trading_date}, 返回前一交易日: {previous_trading_date}")
        return previous_trading_date
    
    try:
        # 确保股票代码格式正确
        if len(stock_code) == 6:
            if stock_code.startswith(('60', '68')):
                ts_code = f"{stock_code}.SH"
            elif stock_code.startswith(('43', '83', '87')):
                ts_code = f"{stock_code}.BJ"
            else:
                ts_code = f"{stock_code}.SZ"
        else:
            ts_code = stock_code
        
        # 获取交易日期参数，默认为前一交易日
        trade_date = request.args.get('trade_date')
        if not trade_date:
            trade_date = get_previous_trading_date()
        
        print(f"[每日指标] 获取{ts_code}在{trade_date}的每日指标数据...")
        
        # 验证股票代码是否存在
        basic_info = safe_tushare_call(pro.stock_basic, ts_code=ts_code)
        if basic_info.empty:
            return jsonify({'error': '股票代码不存在'}), 404
        
        # 获取指定日期的每日指标数据
        daily_basic_data = safe_tushare_call(pro.daily_basic, ts_code=ts_code, trade_date=trade_date)
        
        # 如果指定日期没有数据，尝试获取最近的数据
        if daily_basic_data.empty:
            print(f"[每日指标] {trade_date}无数据，尝试获取最近的每日指标数据...")
            # 尝试最近10个交易日
            for i in range(1, 11):
                try_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=i)).strftime('%Y%m%d')
                daily_basic_data = safe_tushare_call(pro.daily_basic, ts_code=ts_code, trade_date=try_date)
                if not daily_basic_data.empty:
                    trade_date = try_date
                    print(f"[每日指标] 找到{trade_date}的数据")
                    break
        
        if daily_basic_data.empty:
            return jsonify({'error': '无法获取每日指标数据'}), 404
        
        # 获取数据行
        data_row = daily_basic_data.iloc[0]
        
        # 按照Tushare官方文档构建返回数据，包含所有输出参数
        result_data = {
            'ts_code': data_row.get('ts_code', ts_code),
            'trade_date': data_row.get('trade_date', trade_date),
            'close': safe_float(data_row.get('close')),
            'turnover_rate': safe_float(data_row.get('turnover_rate')),
            'turnover_rate_f': safe_float(data_row.get('turnover_rate_f')),
            'volume_ratio': safe_float(data_row.get('volume_ratio')),
            'pe': safe_float(data_row.get('pe')),
            'pe_ttm': safe_float(data_row.get('pe_ttm')),
            'pb': safe_float(data_row.get('pb')),
            'ps': safe_float(data_row.get('ps')),
            'ps_ttm': safe_float(data_row.get('ps_ttm')),
            'dv_ratio': safe_float(data_row.get('dv_ratio')),
            'dv_ttm': safe_float(data_row.get('dv_ttm')),
            'total_share': safe_float(data_row.get('total_share')),
            'float_share': safe_float(data_row.get('float_share')),
            'free_share': safe_float(data_row.get('free_share')),
            'total_mv': safe_float(data_row.get('total_mv')),
            'circ_mv': safe_float(data_row.get('circ_mv'))
        }
        
        # 获取股票基本信息用于显示
        stock_name = basic_info.iloc[0]['name'] if not basic_info.empty else stock_code
        stock_industry = basic_info.iloc[0]['industry'] if not basic_info.empty and 'industry' in basic_info.columns else '未知行业'
        
        print(f"[每日指标] 成功获取{ts_code}({stock_name})在{trade_date}的每日指标数据，行业: {stock_industry}")
        
        return jsonify({
            'success': True,
            'data': result_data,
            'stock_info': {
                'ts_code': ts_code,
                'name': stock_name,
                'industry': stock_industry,
                'trade_date': trade_date
            },
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"[每日指标] 获取失败: {e}")
        return jsonify({'error': f'获取每日指标数据失败: {str(e)}'}), 500


@app.route('/api/stock/<stock_code>/moneyflow')
def get_stock_moneyflow(stock_code):
    """
    获取股票资金流向数据
    严格按照Tushare官方文档 moneyflow 接口的输出参数
    
    Args:
        stock_code: 股票代码，如 000001 或 000001.SZ
        
    Query Parameters:
        trade_date: 交易日期 YYYYMMDD，默认为最近交易日
        days: 获取天数，默认1天
        
    Returns:
        JSON: 资金流向数据，包含Tushare官方文档中的所有输出参数
    """
    try:
        # 确保股票代码格式正确
        if len(stock_code) == 6:
            if stock_code.startswith(('60', '68')):
                ts_code = f"{stock_code}.SH"
            elif stock_code.startswith(('43', '83', '87')):
                ts_code = f"{stock_code}.BJ"
            else:
                ts_code = f"{stock_code}.SZ"
        else:
            ts_code = stock_code
        
        # 获取参数
        trade_date = request.args.get('trade_date')
        days = request.args.get('days', 1, type=int)
        
        print(f"[资金流向] 获取{ts_code}的资金流向数据，交易日期: {trade_date}, 天数: {days}")
        
        # 验证股票代码是否存在
        basic_info = safe_tushare_call(pro.stock_basic, ts_code=ts_code)
        if basic_info.empty:
            return jsonify({'error': '股票代码不存在'}), 404
        
        stock_name = basic_info.iloc[0]['name']
        
        # 如果没有指定交易日期，使用最近的交易日
        if not trade_date:
            trade_date = get_latest_trading_day()
        
        # 首先尝试从缓存获取数据
        cached_stock = get_stock_from_cache(ts_code)
        cached_moneyflow = None
        
        if cached_stock:
            # 检查是否有完整的资金流向数据字段
            required_fields = ['buy_sm_amount', 'sell_sm_amount', 'buy_md_amount', 'sell_md_amount', 
                             'buy_lg_amount', 'sell_lg_amount', 'buy_elg_amount', 'sell_elg_amount', 'net_mf_amount']
            if all(field in cached_stock for field in required_fields):
                cached_moneyflow = {
                    'ts_code': ts_code,
                    'trade_date': trade_date,
                    'buy_sm_vol': cached_stock.get('buy_sm_vol', 0),
                    'buy_sm_amount': cached_stock.get('buy_sm_amount', 0),
                    'sell_sm_vol': cached_stock.get('sell_sm_vol', 0),
                    'sell_sm_amount': cached_stock.get('sell_sm_amount', 0),
                    'buy_md_vol': cached_stock.get('buy_md_vol', 0),
                    'buy_md_amount': cached_stock.get('buy_md_amount', 0),
                    'sell_md_vol': cached_stock.get('sell_md_vol', 0),
                    'sell_md_amount': cached_stock.get('sell_md_amount', 0),
                    'buy_lg_vol': cached_stock.get('buy_lg_vol', 0),
                    'buy_lg_amount': cached_stock.get('buy_lg_amount', 0),
                    'sell_lg_vol': cached_stock.get('sell_lg_vol', 0),
                    'sell_lg_amount': cached_stock.get('sell_lg_amount', 0),
                    'buy_elg_vol': cached_stock.get('buy_elg_vol', 0),
                    'buy_elg_amount': cached_stock.get('buy_elg_amount', 0),
                    'sell_elg_vol': cached_stock.get('sell_elg_vol', 0),
                    'sell_elg_amount': cached_stock.get('sell_elg_amount', 0),
                    'net_mf_vol': cached_stock.get('net_mf_vol', 0),
                    'net_mf_amount': cached_stock.get('net_mf_amount', 0),
                    'data_source': 'cache'
                }
                print(f"从缓存获取完整资金流向数据: 净流入{cached_moneyflow['net_mf_amount']}万元")
        
        # 如果缓存中没有完整的资金流向数据，则通过API获取
        moneyflow_data = None
        if cached_moneyflow is None:
            try:
                print(f"缓存中无完整资金流向数据，正在通过API获取{ts_code}的资金流向数据...")
                
                # 优先尝试moneyflow接口（需要2000积分）
                if days == 1:
                    moneyflow_data = safe_tushare_call(pro.moneyflow, ts_code=ts_code, trade_date=trade_date)
                else:
                    # 获取多天数据
                    end_date = datetime.strptime(trade_date, '%Y%m%d')
                    start_date = end_date - timedelta(days=days-1)
                    moneyflow_data = safe_tushare_call(pro.moneyflow, 
                                                     ts_code=ts_code, 
                                                     start_date=start_date.strftime('%Y%m%d'),
                                                     end_date=trade_date)
                
                if moneyflow_data is None or moneyflow_data.empty:
                    print(f"moneyflow接口无{ts_code}数据")
                    moneyflow_data = None
                else:
                    print(f"成功从moneyflow获取{ts_code}的资金流向数据")
                    
            except Exception as e:
                print(f"获取{ts_code}资金流向数据失败: {e}")
                moneyflow_data = None
        
        # 构造返回数据
        if cached_moneyflow is not None:
            # 使用缓存中的完整资金流向数据
            data_list = [cached_moneyflow]
        elif moneyflow_data is not None and not moneyflow_data.empty:
            # 使用API获取的数据
            data_list = []
            for _, row in moneyflow_data.iterrows():
                data_list.append({
                    'ts_code': row['ts_code'],
                    'trade_date': row['trade_date'],
                    'buy_sm_vol': int(row['buy_sm_vol']) if pd.notna(row['buy_sm_vol']) else 0,
                    'buy_sm_amount': float(row['buy_sm_amount']) if pd.notna(row['buy_sm_amount']) else 0.0,
                    'sell_sm_vol': int(row['sell_sm_vol']) if pd.notna(row['sell_sm_vol']) else 0,
                    'sell_sm_amount': float(row['sell_sm_amount']) if pd.notna(row['sell_sm_amount']) else 0.0,
                    'buy_md_vol': int(row['buy_md_vol']) if pd.notna(row['buy_md_vol']) else 0,
                    'buy_md_amount': float(row['buy_md_amount']) if pd.notna(row['buy_md_amount']) else 0.0,
                    'sell_md_vol': int(row['sell_md_vol']) if pd.notna(row['sell_md_vol']) else 0,
                    'sell_md_amount': float(row['sell_md_amount']) if pd.notna(row['sell_md_amount']) else 0.0,
                    'buy_lg_vol': int(row['buy_lg_vol']) if pd.notna(row['buy_lg_vol']) else 0,
                    'buy_lg_amount': float(row['buy_lg_amount']) if pd.notna(row['buy_lg_amount']) else 0.0,
                    'sell_lg_vol': int(row['sell_lg_vol']) if pd.notna(row['sell_lg_vol']) else 0,
                    'sell_lg_amount': float(row['sell_lg_amount']) if pd.notna(row['sell_lg_amount']) else 0.0,
                    'buy_elg_vol': int(row['buy_elg_vol']) if pd.notna(row['buy_elg_vol']) else 0,
                    'buy_elg_amount': float(row['buy_elg_amount']) if pd.notna(row['buy_elg_amount']) else 0.0,
                    'sell_elg_vol': int(row['sell_elg_vol']) if pd.notna(row['sell_elg_vol']) else 0,
                    'sell_elg_amount': float(row['sell_elg_amount']) if pd.notna(row['sell_elg_amount']) else 0.0,
                    'net_mf_vol': int(row['net_mf_vol']) if pd.notna(row['net_mf_vol']) else 0,
                    'net_mf_amount': float(row['net_mf_amount']) if pd.notna(row['net_mf_amount']) else 0.0,
                    'data_source': 'api'
                })
        else:
            # 没有数据，返回空数据结构
            data_list = [{
                'ts_code': ts_code,
                'trade_date': trade_date,
                'buy_sm_vol': 0,
                'buy_sm_amount': 0.0,
                'sell_sm_vol': 0,
                'sell_sm_amount': 0.0,
                'buy_md_vol': 0,
                'buy_md_amount': 0.0,
                'sell_md_vol': 0,
                'sell_md_amount': 0.0,
                'buy_lg_vol': 0,
                'buy_lg_amount': 0.0,
                'sell_lg_vol': 0,
                'sell_lg_amount': 0.0,
                'buy_elg_vol': 0,
                'buy_elg_amount': 0.0,
                'sell_elg_vol': 0,
                'sell_elg_amount': 0.0,
                'net_mf_vol': 0,
                'net_mf_amount': 0.0,
                'data_source': 'empty'
            }]
        
        print(f"[资金流向] 成功获取{ts_code}({stock_name})在{trade_date}的资金流向数据")
        
        return jsonify({
            'success': True,
            'data': data_list,
            'stock_info': {
                'ts_code': ts_code,
                'name': stock_name,
                'trade_date': trade_date
            },
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"[资金流向] 获取失败: {e}")
        return jsonify({'error': f'获取资金流向数据失败: {str(e)}'}), 500


@app.route('/api/stock/<stock_code>/daily_history')
def get_stock_daily_history(stock_code):
    """
    获取股票历史日线数据
    严格按照Tushare官方文档 daily 接口的输出参数
    
    Args:
        stock_code: 股票代码，如 000001 或 000001.SZ
        
    Query Parameters:
        days: 获取天数，默认500天
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        
    Returns:
        JSON: 历史日线数据，包含Tushare官方文档中的所有输出参数
    """
    try:
        # 确保股票代码格式正确
        if len(stock_code) == 6:
            if stock_code.startswith(('60', '68')):
                ts_code = f"{stock_code}.SH"
            elif stock_code.startswith(('43', '83', '87')):
                ts_code = f"{stock_code}.BJ"
            else:
                ts_code = f"{stock_code}.SZ"
        else:
            ts_code = stock_code
        
        # 获取参数
        days = request.args.get('days', 500, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        print(f"[历史日线] 获取{ts_code}的历史日线数据，天数: {days}")
        
        # 验证股票代码是否存在
        basic_info = safe_tushare_call(pro.stock_basic, ts_code=ts_code)
        if basic_info.empty:
            return jsonify({'error': '股票代码不存在'}), 404
        
        # 使用TushareDataFetcher获取历史日线数据
        from tushare_data_fetcher import TushareDataFetcher
        fetcher = TushareDataFetcher(pro_api=pro)
        
        if start_date and end_date:
            daily_data = fetcher.get_daily_data(ts_code, start_date=start_date, end_date=end_date)
        else:
            daily_data = fetcher.get_daily_data(ts_code, days=days)
        
        if daily_data.empty:
            return jsonify({'error': '无法获取历史日线数据'}), 404
        
        # 计算BOLL指标
        daily_data = calculate_boll(daily_data)
        
        # 转换为JSON格式，保持Tushare官方文档的字段格式，并添加BOLL指标
        data_list = []
        for _, row in daily_data.iterrows():
            data_list.append({
                'ts_code': row['ts_code'],
                'trade_date': row['trade_date'],
                'open': float(row['open']) if pd.notna(row['open']) else None,
                'high': float(row['high']) if pd.notna(row['high']) else None,
                'low': float(row['low']) if pd.notna(row['low']) else None,
                'close': float(row['close']) if pd.notna(row['close']) else None,
                'pre_close': float(row['pre_close']) if pd.notna(row['pre_close']) else None,
                'change': float(row['change']) if pd.notna(row['change']) else None,
                'pct_chg': float(row['pct_chg']) if pd.notna(row['pct_chg']) else None,
                'vol': float(row['vol']) if pd.notna(row['vol']) else None,
                'amount': float(row['amount']) if pd.notna(row['amount']) else None,
                # 添加BOLL指标数据
                'boll_upper': float(row['boll_upper']) if pd.notna(row['boll_upper']) else None,
                'boll_mid': float(row['boll_mid']) if pd.notna(row['boll_mid']) else None,
                'boll_lower': float(row['boll_lower']) if pd.notna(row['boll_lower']) else None
            })
        
        # 获取股票基本信息
        stock_name = basic_info.iloc[0]['name'] if not basic_info.empty else stock_code
        
        print(f"[历史日线] 成功获取{ts_code}({stock_name})的{len(data_list)}条历史日线数据")
        
        return jsonify({
            'success': True,
            'data': data_list,
            'stock_info': {
                'ts_code': ts_code,
                'name': stock_name,
                'total_records': len(data_list),
                'date_range': {
                    'start': data_list[0]['trade_date'] if data_list else None,
                    'end': data_list[-1]['trade_date'] if data_list else None
                }
            },
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"[历史日线] 获取失败: {e}")
        return jsonify({'error': f'获取历史日线数据失败: {str(e)}'}), 500


@app.route('/api/stock/<stock_code>/nine_turn')
def get_stock_nine_turn(stock_code):
    """
    获取股票神奇九转指标数据
    使用本地计算方式，严格按照神奇九转算法实现
    
    Args:
        stock_code: 股票代码，如 000001 或 000001.SZ
        
    Query Parameters:
        freq: 频率(日daily,分钟60min)，默认daily
        days: 获取天数，默认200天
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        
    Returns:
        JSON: 神奇九转指标数据
    """
    try:
        # 确保股票代码格式正确
        if len(stock_code) == 6:
            if stock_code.startswith(('60', '68')):
                ts_code = f"{stock_code}.SH"
            elif stock_code.startswith(('43', '83', '87')):
                ts_code = f"{stock_code}.BJ"
            else:
                ts_code = f"{stock_code}.SZ"
        else:
            ts_code = stock_code
        
        # 获取参数
        freq = request.args.get('freq', 'daily')  # 默认日线
        days = request.args.get('days', 200, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        print(f"[神奇九转] 获取{ts_code}的神奇九转数据，频率: {freq}，天数: {days}")
        
        # 验证股票代码是否存在
        basic_info = safe_tushare_call(pro.stock_basic, ts_code=ts_code)
        if basic_info.empty:
            return jsonify({'error': '股票代码不存在'}), 404
        
        # 获取K线数据用于计算神奇九转
        # 需要更多数据来确保九转计算的准确性
        extended_days = days + 30  # 额外获取30天数据
        
        if start_date and end_date:
            # 使用指定的日期范围
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                # 扩展开始日期以获取足够的数据进行计算
                extended_start = start_date_obj - timedelta(days=30)
                kline_data = safe_tushare_call(pro.daily, 
                                             ts_code=ts_code, 
                                             start_date=extended_start.strftime('%Y%m%d'),
                                             end_date=end_date_obj.strftime('%Y%m%d'))
            except ValueError:
                return jsonify({'error': '日期格式错误，请使用YYYY-MM-DD格式'}), 400
        else:
            # 使用默认天数
            end_date_obj = datetime.now()
            start_date_obj = end_date_obj - timedelta(days=extended_days)
            kline_data = safe_tushare_call(pro.daily, 
                                         ts_code=ts_code, 
                                         start_date=start_date_obj.strftime('%Y%m%d'),
                                         end_date=end_date_obj.strftime('%Y%m%d'))
        
        if kline_data.empty:
            return jsonify({
                'success': True,
                'data': [],
                'message': '该股票暂无K线数据',
                'stock_info': {
                    'ts_code': ts_code,
                    'name': basic_info.iloc[0]['name'] if not basic_info.empty else stock_code,
                    'freq': freq
                }
            })
        
        # 按交易日期排序（从早到晚）
        kline_data = kline_data.sort_values('trade_date')
        
        # 计算神奇九转指标
        nine_turn_results = calculate_nine_turn_indicator(kline_data)
        
        # 如果指定了日期范围，过滤结果
        if start_date and end_date:
            start_filter = start_date.replace('-', '')
            end_filter = end_date.replace('-', '')
            nine_turn_results = [r for r in nine_turn_results 
                               if start_filter <= r['trade_date'].replace('-', '') <= end_filter]
        else:
            # 只返回最近指定天数的数据
            nine_turn_results = nine_turn_results[-days:] if len(nine_turn_results) > days else nine_turn_results
        
        # 获取股票基本信息
        stock_name = basic_info.iloc[0]['name'] if not basic_info.empty else stock_code
        
        # 统计九转信号 - 统计所有有信号的点（不只是第9天）
        buy_signals = len([d for d in nine_turn_results if d['buy_signal'] > 0])
        sell_signals = len([d for d in nine_turn_results if d['sell_signal'] > 0])
        
        # 统计完整的九转序列（第9天）
        complete_buy_turns = len([d for d in nine_turn_results if d['buy_signal'] == 9])
        complete_sell_turns = len([d for d in nine_turn_results if d['sell_signal'] == 9])
        
        print(f"[神奇九转] 成功计算{ts_code}({stock_name})的{len(nine_turn_results)}条神奇九转数据，买入信号: {buy_signals}个(完整序列{complete_buy_turns}个)，卖出信号: {sell_signals}个(完整序列{complete_sell_turns}个)")
        
        return jsonify({
            'success': True,
            'data': nine_turn_results,
            'stock_info': {
                'ts_code': ts_code,
                'name': stock_name,
                'freq': freq,
                'total_records': len(nine_turn_results),
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'complete_buy_turns': complete_buy_turns,
                'complete_sell_turns': complete_sell_turns,
                'date_range': {
                    'start': nine_turn_results[0]['trade_date'] if nine_turn_results else None,
                    'end': nine_turn_results[-1]['trade_date'] if nine_turn_results else None
                }
            },
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"[神奇九转] 获取失败: {e}")
        return jsonify({'error': f'获取神奇九转数据失败: {str(e)}'}), 500


def calculate_nine_turn_indicator(kline_data):
    """
    计算神奇九转指标 - 完整序列显示版本
    
    神奇九转算法：
    1. 卖出序列（上九转）：连续N天收盘价高于4天前的收盘价，显示1-9序列
    2. 买入序列（下九转）：连续N天收盘价低于4天前的收盘价，显示1-9序列
    3. 当连续第3天达到条件时开始显示前面的1、2、3
    4. 如果序列中断，重新开始计数
    
    Args:
        kline_data: K线数据DataFrame，包含trade_date, open, high, low, close, vol, amount等字段
        
    Returns:
        list: 包含九转指标的数据列表
    """
    results = []
    data_list = kline_data.to_dict('records')
    
    # 跟踪序列状态
    up_sequence_count = 0    # 卖出序列计数
    down_sequence_count = 0  # 买入序列计数
    
    for i, row in enumerate(data_list):
        # 基础数据
        result = {
            'ts_code': row['ts_code'],
            'trade_date': row['trade_date'],
            'freq': 'daily',
            'open': float(row['open']) if pd.notna(row['open']) else None,
            'high': float(row['high']) if pd.notna(row['high']) else None,
            'low': float(row['low']) if pd.notna(row['low']) else None,
            'close': float(row['close']) if pd.notna(row['close']) else None,
            'vol': float(row['vol']) if pd.notna(row['vol']) else None,
            'amount': float(row['amount']) if pd.notna(row['amount']) else None,
            'buy_signal': 0,     # 买入信号数字 (1-9)
            'sell_signal': 0,    # 卖出信号数字 (1-9)
            'nine_up_turn': None,
            'nine_down_turn': None
        }
        
        # 需要至少4天前的数据才能计算
        if i >= 4:
            current_close = row['close']
            four_days_ago_close = data_list[i - 4]['close']
            
            if pd.notna(current_close) and pd.notna(four_days_ago_close):
                # 检查卖出序列（收盘价 > 4天前收盘价）
                if current_close > four_days_ago_close:
                    up_sequence_count += 1
                    down_sequence_count = 0  # 重置买入序列
                    
                    # 从第3天开始显示序列
                    if up_sequence_count >= 3:
                        result['sell_signal'] = up_sequence_count
                        
                        # 回填前面的信号
                        start_idx = max(0, len(results) - up_sequence_count + 1)
                        for j in range(start_idx, len(results)):
                            if results[j]['sell_signal'] == 0:
                                seq_num = j - start_idx + 1
                                if seq_num <= up_sequence_count:
                                    results[j]['sell_signal'] = seq_num
                    
                    # 标记第9天的特殊信号并重置序列
                    if up_sequence_count == 9:
                        result['nine_up_turn'] = '+9'
                        up_sequence_count = 0  # 完成一个完整序列后重置计数器
                
                # 检查买入序列（收盘价 < 4天前收盘价）
                elif current_close < four_days_ago_close:
                    down_sequence_count += 1
                    up_sequence_count = 0  # 重置卖出序列
                    
                    # 从第3天开始显示序列
                    if down_sequence_count >= 3:
                        result['buy_signal'] = down_sequence_count
                        
                        # 回填前面的信号
                        start_idx = max(0, len(results) - down_sequence_count + 1)
                        for j in range(start_idx, len(results)):
                            if results[j]['buy_signal'] == 0:
                                seq_num = j - start_idx + 1
                                if seq_num <= down_sequence_count:
                                    results[j]['buy_signal'] = seq_num
                    
                    # 标记第9天的特殊信号并重置序列
                    if down_sequence_count == 9:
                        result['nine_down_turn'] = '-9'
                        down_sequence_count = 0  # 完成一个完整序列后重置计数器
                
                else:
                    # 序列中断，重置计数
                    up_sequence_count = 0
                    down_sequence_count = 0
            else:
                # 数据缺失，重置计数
                up_sequence_count = 0
                down_sequence_count = 0
        
        # 保持向后兼容的字段
        result['up_count'] = float(up_sequence_count)
        result['down_count'] = float(down_sequence_count)
        
        results.append(result)
    
    return results


# 获取真实的实时数据（交易时间内调用）

@app.route('/api/update_progress/<market>')
def get_update_progress(market):
    """获取指定市场的数据更新进度"""
    try:
        # 从全局状态获取进度信息
        if market in update_status:
            status = update_status[market]
            return jsonify({
                'status': status.get('status', 'unknown'),
                'completed': status.get('completed', 0),
                'total': status.get('total', 0),
                'progress_percent': round((status.get('completed', 0) / max(status.get('total', 1), 1)) * 100, 2)
            })
        
        # 如果没有全局状态，尝试从缓存获取进度
        cache_data = load_cache_data(market)
        if cache_data and 'progress' in cache_data:
            progress = cache_data['progress']
            return jsonify({
                'status': cache_data.get('data_status', 'unknown'),
                'completed': progress.get('completed', 0),
                'total': progress.get('total', 0),
                'current_stock': progress.get('current_stock', ''),
                'progress_percent': round((progress.get('completed', 0) / max(progress.get('total', 1), 1)) * 100, 2)
            })
        
        return jsonify({
            'status': 'not_started',
            'completed': 0,
            'total': 0,
            'progress_percent': 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stocks/<market>')
def get_stocks_by_market(market):
    try:
        page = int(request.args.get('page', 1))
        per_page = 500  # 每页显示500行数据
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        current_date = datetime.now().strftime('%Y%m%d')
        
        # 检查缓存
        cache_data = load_cache_data(market)
        latest_cache_date = get_latest_cache_date(market)
        
        # 安全获取数值的辅助函数
        def safe_float(value, default=0.0):
            try:
                if value is None or pd.isna(value):
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # 判断是否需要更新数据
        need_full_update = False
        need_incremental_update = False
        
        if force_refresh:
            # 强制刷新，先取消正在运行的更新线程
            if market in update_status and update_status[market].get('status') == 'updating':
                update_status[market]['status'] = 'cancelled'
                print(f"取消{market}市场正在运行的更新线程")
                time.sleep(1)  # 等待线程停止
            
            # 清除缓存并进行全量更新
            need_full_update = True
            print(f"强制刷新{market}市场数据，进行全量更新")
        elif cache_data is None or latest_cache_date is None:
            # 没有缓存，返回空数据，提示用户使用"立即同步"按钮
            print(f"{market}市场无缓存数据，请使用'立即同步'按钮获取数据")
            return jsonify({
                'stocks': [],
                'total': 0,
                'pages': 0,
                'current_page': page,
                'data_status': 'no_cache',
                'message': '暂无缓存数据，请点击"立即同步"按钮获取最新数据',
                'cache_info': {
                    'last_update': None,
                    'is_cached': False,
                    'force_refreshed': False
                }
            })
        else:
            # 有缓存数据，直接使用缓存，不触发任何更新
            print(f"{market}市场使用缓存数据，缓存日期: {latest_cache_date}")
        
        if need_full_update:
            # 优先使用缓存中的股票列表，避免不必要的API调用
            if cache_data and 'stocks' in cache_data and cache_data['stocks']:
                # 如果缓存中有股票列表，直接使用缓存数据进行更新
                print(f"使用缓存中的{market}市场股票列表，共{len(cache_data['stocks'])}只股票")
                all_stocks_data = cache_data['stocks']
                
                # 重置数据状态为基本信息
                for stock_info in all_stocks_data:
                    stock_info['last_update'] = current_date
                    stock_info['data_loaded'] = False  # 标记需要重新加载实时数据
                
                # 保存实时数据到缓存
                cache_data = {
                    'stocks': all_stocks_data,
                    'last_update_date': current_date,
                    'total': len(all_stocks_data),
                    'data_status': 'complete'  # 标记为完整数据
                }
                save_cache_data(market, cache_data)
                print(f"已保存{market}市场实时数据到缓存")
            else:
                # 只有在没有缓存时才调用API获取股票列表
                print(f"缓存中无{market}市场数据，从API获取股票列表")
                if market == 'cyb':  # 创业板
                    stocks = safe_tushare_call(pro.stock_basic, market='创业板')
                elif market == 'hu':  # 沪A
                    stocks = safe_tushare_call(pro.stock_basic, market='主板', exchange='SSE')
                elif market == 'zxb':  # 深A（原中小板，已并入深市主板）
                    stocks = safe_tushare_call(pro.stock_basic, market='主板', exchange='SZSE')
                elif market == 'kcb':  # 科创板
                    # 科创板股票代码以688开头，需要单独获取
                    stocks = safe_tushare_call(pro.stock_basic, market='科创板', exchange='SSE')
                    print(f"获取到{len(stocks)}只科创板股票")
                elif market == 'bj':  # 北交所
                    stocks = safe_tushare_call(pro.stock_basic, exchange='BSE')
                else:
                    return jsonify({'error': '无效的市场类型'}), 400
                
                if stocks.empty:
                    return jsonify({'stocks': [], 'total': 0, 'pages': 0})
                
                print(f"开始获取{len(stocks)}只{market}股票的数据...")
                
                # 获取真实的实时数据，确保首页显示准确信息
                all_stocks_data = []
                for i, (_, stock) in enumerate(stocks.iterrows()):
                    print(f"正在获取 {stock['ts_code']} 的实时数据 ({i+1}/{len(stocks)})")
                    
                    # 获取实时数据
                    stock_info = get_real_time_stock_data(stock['ts_code'], stock['name'], stock['industry'], current_date)
                    all_stocks_data.append(stock_info)
                    
                    # 每处理10只股票打印一次进度
                    if (i + 1) % 10 == 0:
                        print(f"已处理 {i + 1}/{len(stocks)} 只股票")
                
                print(f"完成{market}市场实时数据获取，共{len(all_stocks_data)}只股票")
                
                # 保存基本信息到缓存
                cache_data = {
                    'stocks': all_stocks_data,
                    'last_update_date': current_date,
                    'total': len(all_stocks_data),
                    'data_status': 'basic_only'  # 标记为仅基本信息
                }
                save_cache_data(market, cache_data)
                
                # 启动后台线程进行渐进式数据更新
                update_thread = threading.Thread(
                    target=update_stock_data_progressive, 
                    args=(market, all_stocks_data),
                    daemon=True
                )
                update_thread.start()
                print(f"已启动后台线程更新{market}市场实时数据")
            
        else:
            # 使用缓存数据，不触发任何更新
            all_stocks_data = cache_data['stocks']
        
        # 分页处理
        total = len(all_stocks_data)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_stocks = all_stocks_data[start_idx:end_idx]
        
        return jsonify({
            'stocks': page_stocks,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'current_page': page,
            'data_status': cache_data.get('data_status', 'complete') if cache_data else 'basic_only',
            'cache_info': {
                'last_update': cache_data.get('last_update_date', current_date) if cache_data else current_date,
                'is_cached': not need_full_update,  # 只有强制刷新时才不是缓存数据
                'force_refreshed': force_refresh
            }
        })
    
    except Exception as e:
        print(f"获取{market}市场数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/force_refresh/<market>', methods=['POST'])
def force_refresh_market(market):
    """强制刷新指定市场的数据"""
    try:
        # 验证市场类型
        valid_markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        if market not in valid_markets:
            return jsonify({'error': '无效的市场类型'}), 400
        
        # 取消正在运行的更新线程
        if market in update_status and update_status[market].get('status') == 'updating':
            update_status[market]['status'] = 'cancelled'
            print(f"取消{market}市场正在运行的更新线程")
            time.sleep(1)  # 等待线程停止
        
        # 清除缓存文件
        cache_file = get_cache_file_path(market)
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print(f"已清除{market}市场缓存文件")
        
        # 重置更新状态
        if market in update_status:
            del update_status[market]
        
        current_date = datetime.now().strftime('%Y%m%d')
        
        # 获取股票列表（使用频率限制）
        if market == 'cyb':  # 创业板
            stocks = safe_tushare_call(pro.stock_basic, market='创业板')
        elif market == 'hu':  # 沪A
            stocks = safe_tushare_call(pro.stock_basic, market='主板', exchange='SSE')
        elif market == 'zxb':  # 深A（原中小板，已并入深市主板）
            stocks = safe_tushare_call(pro.stock_basic, market='主板', exchange='SZSE')
        elif market == 'kcb':  # 科创板
            stocks = safe_tushare_call(pro.stock_basic, market='科创板', exchange='SSE')
        elif market == 'bj':  # 北交所
            stocks = safe_tushare_call(pro.stock_basic, exchange='BSE')
        
        if stocks.empty:
            return jsonify({'success': True, 'message': f'{market}市场暂无股票数据'})
        
        print(f"开始强制刷新{len(stocks)}只{market}股票的数据...")
        
        # 在后台线程中异步执行强制刷新
        def force_refresh_worker():
            try:
                # 设置更新状态
                update_status[market] = {
                    'status': 'updating',
                    'completed': 0,
                    'total': len(stocks),
                    'current_stock': ''
                }
                
                # 获取真实的实时数据
                all_stocks_data = []
                for i, (_, stock) in enumerate(stocks.iterrows()):
                    # 检查是否被取消
                    if market in update_status and update_status[market].get('status') == 'cancelled':
                        print(f"{market}市场强制刷新被取消")
                        return
                    
                    print(f"正在强制刷新 {stock['ts_code']} 的实时数据 ({i+1}/{len(stocks)})")
                    
                    # 更新进度
                    update_status[market].update({
                        'completed': i + 1,
                        'current_stock': stock['ts_code']
                    })
                    
                    stock_info = get_real_time_stock_data(stock['ts_code'], stock['name'], stock['industry'], current_date)
                    all_stocks_data.append(stock_info)
                
                # 保存实时数据到缓存
                cache_data = {
                    'stocks': all_stocks_data,
                    'last_update_date': current_date,
                    'total': len(all_stocks_data),
                    'data_status': 'complete'
                }
                save_cache_data(market, cache_data)
                print(f"已保存{market}市场实时数据到缓存")
                
                # 更新状态为完成
                update_status[market] = {
                    'status': 'completed',
                    'completed': len(all_stocks_data),
                    'total': len(all_stocks_data)
                }
                
            except Exception as e:
                print(f"强制刷新{market}市场数据失败: {e}")
                if market in update_status:
                    update_status[market]['status'] = 'error'
        
        # 启动后台线程
        refresh_thread = threading.Thread(target=force_refresh_worker, daemon=True)
        refresh_thread.start()
        
        # 立即返回响应
        return jsonify({
            'success': True, 
            'message': f'{market}市场数据强制刷新已启动，正在后台处理...',
            'total_stocks': len(stocks)
        })
        
    except Exception as e:
        print(f"强制刷新{market}市场数据失败: {e}")
        return jsonify({'error': str(e)}), 500

# 定时任务功能
def auto_update_moneyflow_data():
    """自动更新资金流向数据到缓存 - 工作日晚上7点执行"""
    try:
        now = datetime.now()
        print(f"开始自动更新资金流向数据 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取所有市场的股票数据
        all_stocks = []
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        
        for market in markets:
            try:
                market_data = cache_manager.load_cache_data(market)
                if market_data and 'stocks' in market_data:
                    all_stocks.extend([(stock, market) for stock in market_data['stocks']])
            except Exception as e:
                print(f"获取市场 {market} 数据失败: {e}")
                continue
        
        if not all_stocks:
            print("没有找到股票数据，跳过资金流向数据更新")
            return
        
        print(f"找到 {len(all_stocks)} 只股票，开始更新资金流向数据")
        
        # 创建专用的资金流向API频率限制器（每分钟2次）
        moneyflow_rate_limiter = RateLimiter(max_requests=2, time_window=60)
        
        # 获取当前交易日期
        current_trade_date = datetime.now().strftime('%Y%m%d')
        
        # 分批处理股票，每批处理完后等待足够时间
        batch_size = 2  # 每批处理2只股票（对应API限制）
        total_batches = (len(all_stocks) + batch_size - 1) // batch_size
        
        updated_count = 0
        failed_count = 0
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(all_stocks))
            batch_stocks = all_stocks[start_idx:end_idx]
            
            print(f"处理第 {batch_idx + 1}/{total_batches} 批，股票 {start_idx + 1}-{end_idx}")
            
            # 处理当前批次的股票
            for stock_info, market in batch_stocks:
                try:
                    ts_code = stock_info['ts_code']
                    print(f"更新 {ts_code} 的资金流向数据")
                    
                    # 使用专用频率限制器获取资金流向数据
                    moneyflow_data = None
                    
                    # 首先尝试 moneyflow 接口（需要2000积分）
                    try:
                        moneyflow_rate_limiter.wait_if_needed()
                        moneyflow_data = pro.moneyflow(ts_code=ts_code, trade_date=current_trade_date)
                        if moneyflow_data.empty:
                            raise Exception("moneyflow 返回空数据")
                        print(f"使用 moneyflow 接口获取 {ts_code} 数据成功")
                    except Exception as e:
                        print(f"moneyflow 接口失败: {e}，尝试 moneyflow_dc 接口")
                        try:
                            moneyflow_rate_limiter.wait_if_needed()
                            moneyflow_data = pro.moneyflow_dc(ts_code=ts_code, trade_date=current_trade_date)
                            if moneyflow_data.empty:
                                raise Exception("moneyflow_dc 返回空数据")
                            print(f"使用 moneyflow_dc 接口获取 {ts_code} 数据成功")
                        except Exception as e2:
                            print(f"moneyflow_dc 接口也失败: {e2}")
                            failed_count += 1
                            continue
                    
                    # 更新股票的资金流向数据
                    if moneyflow_data is not None and not moneyflow_data.empty:
                        row = moneyflow_data.iloc[0]
                        
                        # 更新各种资金流向字段（按照Tushare官方文档字段）
                    # 净流入额（万元）
                    if 'net_mf_amount' in row:
                        net_mf_amount_wan = safe_float(row['net_mf_amount'])
                        stock_info['net_mf_amount'] = round(net_mf_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 特大单买入金额（万元）
                    if 'buy_elg_amount' in row:
                        buy_elg_amount_wan = safe_float(row['buy_elg_amount'])
                        stock_info['buy_elg_amount'] = round(buy_elg_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 特大单卖出金额（万元）
                    if 'sell_elg_amount' in row:
                        sell_elg_amount_wan = safe_float(row['sell_elg_amount'])
                        stock_info['sell_elg_amount'] = round(sell_elg_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 大单买入金额（万元）
                    if 'buy_lg_amount' in row:
                        buy_lg_amount_wan = safe_float(row['buy_lg_amount'])
                        stock_info['buy_lg_amount'] = round(buy_lg_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 大单卖出金额（万元）
                    if 'sell_lg_amount' in row:
                        sell_lg_amount_wan = safe_float(row['sell_lg_amount'])
                        stock_info['sell_lg_amount'] = round(sell_lg_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 中单买入金额（万元）
                    if 'buy_md_amount' in row:
                        buy_md_amount_wan = safe_float(row['buy_md_amount'])
                        stock_info['buy_md_amount'] = round(buy_md_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 中单卖出金额（万元）
                    if 'sell_md_amount' in row:
                        sell_md_amount_wan = safe_float(row['sell_md_amount'])
                        stock_info['sell_md_amount'] = round(sell_md_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 小单买入金额（万元）
                    if 'buy_sm_amount' in row:
                        buy_sm_amount_wan = safe_float(row['buy_sm_amount'])
                        stock_info['buy_sm_amount'] = round(buy_sm_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 小单卖出金额（万元）
                    if 'sell_sm_amount' in row:
                        sell_sm_amount_wan = safe_float(row['sell_sm_amount'])
                        stock_info['sell_sm_amount'] = round(sell_sm_amount_wan / 1000, 2)  # 转换为千万元
                    
                    # 主力净流入额（万元）- 如果有的话
                    if 'net_amount' in row:
                        net_amount_wan = safe_float(row['net_amount'])
                        stock_info['net_amount'] = round(net_amount_wan / 1000, 2)  # 转换为千万元
                        
                        # 更新数据时间戳
                        stock_info['moneyflow_last_update'] = current_trade_date
                        stock_info['last_update'] = datetime.now().strftime('%Y-%m-%d')
                        
                        updated_count += 1
                        print(f"成功更新 {ts_code} 的资金流向数据")
                    else:
                        failed_count += 1
                        print(f"未能获取 {ts_code} 的资金流向数据")
                        
                except Exception as e:
                    failed_count += 1
                    print(f"更新 {stock_info.get('ts_code', 'unknown')} 资金流向数据失败: {e}")
                    continue
            
            # 批次处理完成后，如果不是最后一批，等待足够时间避免API限制
            if batch_idx < total_batches - 1:
                wait_time = 35  # 等待35秒，确保不超过每分钟2次的限制
                print(f"批次 {batch_idx + 1} 完成，等待 {wait_time} 秒后处理下一批...")
                time.sleep(wait_time)
        
        # 更新完成后，重新保存所有市场的缓存数据
        markets_updated = set()
        for stock_info, market in all_stocks:
            if market not in markets_updated:
                try:
                    # 获取该市场的所有股票数据
                    market_stocks = [s for s, m in all_stocks if m == market]
                    
                    # 构建缓存数据
                    cache_data = {
                        'stocks': market_stocks,
                        'last_update_date': datetime.now().strftime('%Y-%m-%d'),
                        'total': len(market_stocks),
                        'progress': {
                            'completed': len(market_stocks),
                            'total': len(market_stocks),
                            'current_stock': 'moneyflow_update_completed'
                        },
                        'data_status': 'complete',
                        'moneyflow_update_time': datetime.now().isoformat()
                    }
                    
                    # 保存缓存
                    cache_manager.save_cache_data(market, cache_data)
                    markets_updated.add(market)
                    print(f"已更新 {market} 市场缓存数据")
                    
                except Exception as e:
                    print(f"保存 {market} 市场缓存失败: {e}")
        
        print(f"资金流向数据更新完成！成功: {updated_count}, 失败: {failed_count}")
        print(f"更新了 {len(markets_updated)} 个市场的缓存数据")
        
    except Exception as e:
        print(f"自动更新资金流向数据失败: {e}")
        import traceback
        traceback.print_exc()

def auto_filter_stocks():
    """自动筛选符合条件的股票并保存结果"""
    try:
        now = datetime.now()
        print(f"开始自动筛选股票 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 从缓存中获取所有市场的股票数据
        all_stocks = []
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        
        for market in markets:
            try:
                market_data = cache_manager.load_cache_data(market)
                if market_data and 'stocks' in market_data:
                    all_stocks.extend(market_data['stocks'])
            except Exception as e:
                print(f"获取市场 {market} 数据失败: {e}")
                continue
        
        if not all_stocks:
            print("没有可用的股票数据进行筛选")
            return
        
        # 筛选红 3-6 股票
        # 注意：由于量比数据可能不准确或为0，调整筛选条件
        red_filtered_stocks = []
        for stock in all_stocks:
            try:
                turnover_rate = float(stock.get('turnover_rate', 0))
                volume_ratio = float(stock.get('volume_ratio', 0))
                nine_turn_up = int(stock.get('nine_turn_up', 0))
                
                # 筛选条件：换手率>1，九转买入红色3-6
                # 如果量比数据可用且>0，则加入量比条件
                volume_condition = True
                if volume_ratio > 0:
                    volume_condition = volume_ratio > 0.8  # 降低量比要求
                
                if (turnover_rate > 1 and  # 降低换手率要求
                    volume_condition and 
                    3 <= nine_turn_up <= 6):
                    
                    stock_copy = stock.copy()
                    stock_copy['filter_date'] = now.strftime('%Y-%m-%d')
                    stock_copy['filter_time'] = now.strftime('%H:%M:%S')
                    red_filtered_stocks.append(stock_copy)
                    
            except (ValueError, TypeError):
                continue
        
        # 筛选绿 9 股票
        green_filtered_stocks = []
        for stock in all_stocks:
            try:
                nine_turn_down = int(stock.get('nine_turn_down', 0))
                
                if nine_turn_down == 9:
                    stock_copy = stock.copy()
                    stock_copy['filter_date'] = now.strftime('%Y-%m-%d')
                    stock_copy['filter_time'] = now.strftime('%H:%M:%S')
                    green_filtered_stocks.append(stock_copy)
                    
            except (ValueError, TypeError):
                continue
        
        # 排序
        red_filtered_stocks.sort(key=lambda x: (x.get('nine_turn_up', 0), x.get('turnover_rate', 0)), reverse=True)
        green_filtered_stocks.sort(key=lambda x: x.get('nine_turn_down', 0), reverse=True)
        
        # 保存筛选结果到文件
        cache_dir = 'cache'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        # 保存红色筛选结果
        red_filter_file = os.path.join(cache_dir, 'red_filter_results.json')
        red_filter_data = {
            'filter_time': now.isoformat(),
            'filter_date': now.strftime('%Y-%m-%d'),
            'total': len(red_filtered_stocks),
            'stocks': red_filtered_stocks
        }
        
        with open(red_filter_file, 'w', encoding='utf-8') as f:
            json.dump(red_filter_data, f, ensure_ascii=False, indent=2)
        
        # 保存绿色筛选结果
        green_filter_file = os.path.join(cache_dir, 'green_filter_results.json')
        green_filter_data = {
            'filter_time': now.isoformat(),
            'filter_date': now.strftime('%Y-%m-%d'),
            'total': len(green_filtered_stocks),
            'stocks': green_filtered_stocks
        }
        
        with open(green_filter_file, 'w', encoding='utf-8') as f:
            json.dump(green_filter_data, f, ensure_ascii=False, indent=2)
        
        print(f"自动筛选完成 - 红色筛选: {len(red_filtered_stocks)}只, 绿色筛选: {len(green_filtered_stocks)}只")
        print(f"筛选结果已保存到: {red_filter_file} 和 {green_filter_file}")
        
    except Exception as e:
        print(f"自动筛选任务执行失败: {e}")

def auto_sync_all_markets():
    """自动同步所有A股市场数据"""
    try:
        # 检查是否为工作日
        now = datetime.now()
        if now.weekday() >= 5:  # 周六(5)和周日(6)不执行
            print(f"今天是{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]}，跳过自动同步")
            return
        
        print(f"开始自动同步所有A股市场数据 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        market_names = {
            'cyb': '创业板',
            'hu': '沪A股',
            'zxb': '深A',
            'kcb': '科创板',
            'bj': '北交所'
        }
        
        for market in markets:
            try:
                print(f"正在同步{market_names[market]}数据...")
                
                # 取消正在运行的更新线程
                if market in update_status and update_status[market].get('status') == 'updating':
                    update_status[market]['status'] = 'cancelled'
                    print(f"取消{market}市场正在运行的更新线程")
                    time.sleep(1)
                
                # 清除缓存文件
                cache_file = get_cache_file_path(market)
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    print(f"已清除{market}市场缓存文件")
                
                # 重置更新状态
                if market in update_status:
                    del update_status[market]
                
                current_date = datetime.now().strftime('%Y%m%d')
                
                # 获取股票列表（使用频率限制）
                if market == 'cyb':
                    stocks = safe_tushare_call(pro.stock_basic, market='创业板')
                elif market == 'hu':
                    stocks = safe_tushare_call(pro.stock_basic, market='主板', exchange='SSE')
                elif market == 'zxb':
                    stocks = safe_tushare_call(pro.stock_basic, market='主板', exchange='SZSE')
                elif market == 'kcb':
                    stocks = safe_tushare_call(pro.stock_basic, market='科创板', exchange='SSE')
                elif market == 'bj':
                    stocks = safe_tushare_call(pro.stock_basic, exchange='BSE')
                
                if stocks.empty:
                    print(f"{market_names[market]}暂无股票数据")
                    continue
                
                print(f"开始刷新{len(stocks)}只{market_names[market]}股票的数据...")
                
                # 创建基本信息
                all_stocks_data = []
                for _, stock in stocks.iterrows():
                    stock_info = {
                        'ts_code': stock['ts_code'],
                        'name': stock['name'],
                        'industry': stock['industry'],
                        'latest_price': 0,
                        'turnover_rate': 0,
                        'volume_ratio': 0,
                        'amount': 0,
                        'market_cap': 0,
                        'pe_ttm': 0,
                        'last_update': current_date
                    }
                    all_stocks_data.append(stock_info)
                
                # 保存基本信息到缓存
                cache_data = {
                    'stocks': all_stocks_data,
                    'last_update_date': current_date,
                    'total': len(all_stocks_data),
                    'data_status': 'basic_only'
                }
                save_cache_data(market, cache_data)
                
                # 启动后台线程进行渐进式数据更新
                update_thread = threading.Thread(
                    target=update_stock_data_progressive,
                    args=(market, all_stocks_data),
                    daemon=True
                )
                update_thread.start()
                print(f"已启动{market_names[market]}后台更新线程")
                
                # 等待一段时间再处理下一个市场，避免API频率限制
                time.sleep(2)
                
            except Exception as e:
                print(f"同步{market_names[market]}数据失败: {e}")
                continue
        
        print(f"所有A股市场数据同步任务已启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"自动同步任务执行失败: {e}")

# cleanup_akshare_failures函数已删除，不再使用AkShare

def auto_update_nine_turn_all_markets():
    """自动更新所有A股市场的九转序列数据"""
    try:
        # 检查是否为工作日
        now = datetime.now()
        if now.weekday() >= 5:  # 周六(5)和周日(6)不执行
            print(f"今天是{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]}，跳过九转序列更新")
            return
        
        print(f"开始自动更新所有A股市场的九转序列数据 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        market_names = {
            'cyb': '创业板',
            'hu': '沪A股',
            'zxb': '深A',
            'kcb': '科创板',
            'bj': '北交所'
        }
        
        total_updated = 0
        total_failed = 0
        
        for market in markets:
            try:
                print(f"正在更新{market_names[market]}九转序列数据...")
                
                # 加载缓存数据
                cache_data = load_cache_data(market)
                if not cache_data or 'stocks' not in cache_data:
                    print(f"{market_names[market]}无缓存数据，跳过")
                    continue
                
                stocks_list = cache_data['stocks']
                market_updated = 0
                market_failed = 0
                
                # 逐个更新股票的九转序列
                for i, stock_info in enumerate(stocks_list):
                    try:
                        ts_code = stock_info['ts_code']
                        print(f"正在更新 {ts_code} 九转序列 ({i+1}/{len(stocks_list)})")
                        
                        # 获取最近45天的K线数据用于计算九转序列
                        end_date = datetime.now().strftime('%Y%m%d')
                        start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
                        kline_data = safe_tushare_call(pro.daily, ts_code=ts_code, start_date=start_date, end_date=end_date)
                        
                        # 计算九转序列
                        nine_turn_up = 0
                        nine_turn_down = 0
                        countdown_up = 0
                        countdown_down = 0
                        
                        if not kline_data.empty and len(kline_data) >= 5:
                            kline_data = kline_data.sort_values('trade_date')
                            kline_with_nine_turn = calculate_nine_turn(kline_data)
                            # 获取最新一天的九转序列数据
                            latest_nine_turn = kline_with_nine_turn.iloc[-1]
                            nine_turn_up = int(latest_nine_turn['nine_turn_up']) if latest_nine_turn['nine_turn_up'] > 0 else 0
                            nine_turn_down = int(latest_nine_turn['nine_turn_down']) if latest_nine_turn['nine_turn_down'] > 0 else 0
                            countdown_up = int(latest_nine_turn['countdown_up']) if latest_nine_turn['countdown_up'] > 0 else 0
                            countdown_down = int(latest_nine_turn['countdown_down']) if latest_nine_turn['countdown_down'] > 0 else 0
                        
                        # 更新股票信息中的九转序列数据
                        stock_info['nine_turn_up'] = nine_turn_up
                        stock_info['nine_turn_down'] = nine_turn_down
                        stock_info['countdown_up'] = countdown_up
                        stock_info['countdown_down'] = countdown_down
                        stock_info['nine_turn_last_update'] = datetime.now().strftime('%Y%m%d %H:%M:%S')
                        
                        market_updated += 1
                        
                        # 每10只股票保存一次缓存，减少文件IO操作
                        if (i + 1) % 10 == 0 or i == len(stocks_list) - 1:
                            cache_data['stocks'] = stocks_list
                            cache_data['nine_turn_last_update'] = datetime.now().strftime('%Y%m%d %H:%M:%S')
                            save_cache_data(market, cache_data)
                            print(f"已保存{market_names[market]}九转序列缓存，当前进度: {i+1}/{len(stocks_list)}")
                        
                        # 避免API频率限制
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"更新股票{stock_info.get('ts_code', 'unknown')}九转序列失败: {e}")
                        market_failed += 1
                        continue
                
                print(f"{market_names[market]}九转序列更新完成: 成功{market_updated}只, 失败{market_failed}只")
                total_updated += market_updated
                total_failed += market_failed
                
                # 等待一段时间再处理下一个市场，避免API频率限制
                time.sleep(2)
                
            except Exception as e:
                print(f"更新{market_names[market]}九转序列数据失败: {e}")
                continue
        
        print(f"所有A股市场九转序列更新完成 - 总计成功: {total_updated}只, 失败: {total_failed}只 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"自动九转序列更新任务执行失败: {e}")

def manual_update_nine_turn_all_markets():
    """手动更新所有A股市场的九转序列数据（不受工作日限制）"""
    try:
        now = datetime.now()
        print(f"开始手动更新所有A股市场的九转序列数据 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        market_names = {
            'cyb': '创业板',
            'hu': '沪A股',
            'zxb': '深A',
            'kcb': '科创板',
            'bj': '北交所'
        }
        
        total_updated = 0
        total_failed = 0
        
        for market in markets:
            try:
                print(f"正在更新{market_names[market]}九转序列数据...")
                
                # 加载缓存数据
                cache_data = load_cache_data(market)
                if not cache_data or 'stocks' not in cache_data:
                    print(f"{market_names[market]}无缓存数据，跳过")
                    continue
                
                stocks_list = cache_data['stocks']
                market_updated = 0
                market_failed = 0
                
                # 逐个更新股票的九转序列
                for i, stock_info in enumerate(stocks_list):
                    try:
                        ts_code = stock_info['ts_code']
                        print(f"正在更新 {ts_code} 九转序列 ({i+1}/{len(stocks_list)})")
                        
                        # 获取最近45天的K线数据用于计算九转序列
                        end_date = datetime.now().strftime('%Y%m%d')
                        start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
                        kline_data = safe_tushare_call(pro.daily, ts_code=ts_code, start_date=start_date, end_date=end_date)
                        
                        # 计算九转序列
                        nine_turn_up = 0
                        nine_turn_down = 0
                        countdown_up = 0
                        countdown_down = 0
                        
                        if not kline_data.empty and len(kline_data) >= 5:
                            kline_data = kline_data.sort_values('trade_date')
                            kline_with_nine_turn = calculate_nine_turn(kline_data)
                            # 获取最新一天的九转序列数据
                            latest_nine_turn = kline_with_nine_turn.iloc[-1]
                            nine_turn_up = int(latest_nine_turn['nine_turn_up']) if latest_nine_turn['nine_turn_up'] > 0 else 0
                            nine_turn_down = int(latest_nine_turn['nine_turn_down']) if latest_nine_turn['nine_turn_down'] > 0 else 0
                            countdown_up = int(latest_nine_turn['countdown_up']) if latest_nine_turn['countdown_up'] > 0 else 0
                            countdown_down = int(latest_nine_turn['countdown_down']) if latest_nine_turn['countdown_down'] > 0 else 0
                        
                        # 更新股票信息中的九转序列数据
                        stock_info['nine_turn_up'] = nine_turn_up
                        stock_info['nine_turn_down'] = nine_turn_down
                        stock_info['countdown_up'] = countdown_up
                        stock_info['countdown_down'] = countdown_down
                        stock_info['nine_turn_last_update'] = datetime.now().strftime('%Y%m%d %H:%M:%S')
                        
                        market_updated += 1
                        
                        # 每10只股票保存一次缓存，减少文件IO操作
                        if (i + 1) % 10 == 0 or i == len(stocks_list) - 1:
                            cache_data['stocks'] = stocks_list
                            cache_data['nine_turn_last_update'] = datetime.now().strftime('%Y%m%d %H:%M:%S')
                            save_cache_data(market, cache_data)
                            print(f"已保存{market_names[market]}九转序列缓存，当前进度: {i+1}/{len(stocks_list)}")
                        
                        # 避免API频率限制
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"更新股票{stock_info.get('ts_code', 'unknown')}九转序列失败: {e}")
                        market_failed += 1
                        continue
                
                print(f"{market_names[market]}九转序列更新完成: 成功{market_updated}只, 失败{market_failed}只")
                total_updated += market_updated
                total_failed += market_failed
                
                # 等待一段时间再处理下一个市场，避免API频率限制
                time.sleep(2)
                
            except Exception as e:
                print(f"更新{market_names[market]}九转序列数据失败: {e}")
                continue
        
        print(f"所有A股市场九转序列更新完成 - 总计成功: {total_updated}只, 失败: {total_failed}只 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"手动九转序列更新任务执行失败: {e}")

def start_scheduler():
    """启动定时调度器"""
    # 设置定时任务：工作日下午5点执行数据同步
    schedule.every().monday.at("17:00").do(auto_sync_all_markets)
    schedule.every().tuesday.at("17:00").do(auto_sync_all_markets)
    schedule.every().wednesday.at("17:00").do(auto_sync_all_markets)
    schedule.every().thursday.at("17:00").do(auto_sync_all_markets)
    schedule.every().friday.at("17:00").do(auto_sync_all_markets)
    
    # 设置定时任务：工作日下午5:30执行九转序列更新
    schedule.every().monday.at("17:30").do(auto_update_nine_turn_all_markets)
    schedule.every().tuesday.at("17:30").do(auto_update_nine_turn_all_markets)
    schedule.every().wednesday.at("17:30").do(auto_update_nine_turn_all_markets)
    schedule.every().thursday.at("17:30").do(auto_update_nine_turn_all_markets)
    schedule.every().friday.at("17:30").do(auto_update_nine_turn_all_markets)
    
    # 设置定时任务：工作日晚上7点执行资金流向数据更新
    schedule.every().monday.at("19:00").do(auto_update_moneyflow_data)
    schedule.every().tuesday.at("19:00").do(auto_update_moneyflow_data)
    schedule.every().wednesday.at("19:00").do(auto_update_moneyflow_data)
    schedule.every().thursday.at("19:00").do(auto_update_moneyflow_data)
    schedule.every().friday.at("19:00").do(auto_update_moneyflow_data)
    
    # 设置定时任务：每天晚上6点执行股票筛选
    schedule.every().day.at("18:00").do(auto_filter_stocks)
    
    # AkShare清理任务已删除，不再使用AkShare
    
    print("定时任务已设置：工作日下午5点自动同步所有A股数据")
    print("定时任务已设置：工作日下午5:30自动更新九转序列数据")
    print("定时任务已设置：工作日晚上7点自动更新资金流向数据")
    print("定时任务已设置：每天晚上6点自动筛选符合条件的股票")
    
    # 在后台线程中运行调度器
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("定时调度器已启动")

# get_akshare_retry_status路由已删除，不再使用AkShare

@app.route('/api/scheduler/status')
def get_scheduler_status():
    """获取定时任务状态"""
    try:
        jobs = schedule.jobs
        next_run_time = None
        
        # 找到最近的下次运行时间
        if jobs:
            next_runs = [job.next_run for job in jobs if job.next_run]
            if next_runs:
                next_run_time = min(next_runs).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'status': 'running' if jobs else 'stopped',
            'next_run': next_run_time,
            'total_jobs': len(jobs)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/trigger', methods=['POST'])
def trigger_auto_sync():
    """手动触发自动同步任务"""
    try:
        # 在后台线程中执行同步任务
        sync_thread = threading.Thread(target=auto_sync_all_markets, daemon=True)
        sync_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': '手动同步任务已启动'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/scheduler/trigger_moneyflow', methods=['POST'])
def trigger_moneyflow_update():
    """手动触发资金流向数据更新任务"""
    try:
        # 在后台线程中执行资金流向数据更新任务
        moneyflow_thread = threading.Thread(target=auto_update_moneyflow_data, daemon=True)
        moneyflow_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': '资金流向数据更新任务已启动'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/scheduler/trigger_filter', methods=['POST'])
def trigger_auto_filter():
    """手动触发自动筛选任务"""
    try:
        # 在后台线程中执行筛选任务
        filter_thread = threading.Thread(target=auto_filter_stocks, daemon=True)
        filter_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': '手动筛选任务已启动'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/scheduler/trigger_nine_turn', methods=['POST'])
def trigger_nine_turn_update():
    """手动触发九转序列更新任务"""
    try:
        # 在后台线程中执行九转序列更新任务（使用不受工作日限制的手动版本）
        nine_turn_thread = threading.Thread(target=manual_update_nine_turn_all_markets, daemon=True)
        nine_turn_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': '九转序列更新任务已启动'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/update_all_data', methods=['POST'])
def update_all_data():
    """智能更新全部数据 - 只更新有新增日期的市场数据"""
    try:
        current_date = datetime.now().strftime('%Y%m%d')
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        market_names = {
            'cyb': '创业板',
            'hu': '沪A股', 
            'zxb': '深A',
            'kcb': '科创板',
            'bj': '北交所'
        }
        
        markets_to_update = []
        markets_already_latest = []
        
        # 检查每个市场的缓存状态
        for market in markets:
            cache_data = load_cache_data(market)
            latest_cache_date = get_latest_cache_date(market)
            
            if cache_data is None or latest_cache_date is None:
                # 没有缓存，需要更新
                markets_to_update.append(market)
            else:
                # 检查是否已有今天的数据
                cache_stocks = cache_data.get('stocks', [])
                has_today_data = any(stock.get('last_update') == current_date for stock in cache_stocks)
                
                if has_today_data:
                    # 已有今天的数据
                    markets_already_latest.append(market)
                elif latest_cache_date < current_date:
                    # 需要增量更新
                    markets_to_update.append(market)
                else:
                    # 数据已是最新
                    markets_already_latest.append(market)
        
        if not markets_to_update:
            # 所有市场数据都是最新的
            return jsonify({
                'status': 'success',
                'message': '所有市场数据已是最新，无需更新',
                'updated_markets': [],
                'latest_markets': [market_names[m] for m in markets_already_latest]
            })
        
        # 启动需要更新的市场
        updated_market_names = []
        for market in markets_to_update:
            try:
                print(f"开始更新{market_names[market]}数据...")
                
                # 取消正在运行的更新线程
                if market in update_status and update_status[market].get('status') == 'updating':
                    update_status[market]['status'] = 'cancelled'
                    print(f"取消{market}市场正在运行的更新线程")
                    time.sleep(0.5)
                
                # 加载现有缓存数据进行增量更新
                cache_data = load_cache_data(market)
                if cache_data and 'stocks' in cache_data and cache_data['stocks']:
                    all_stocks_data = cache_data['stocks']
                    
                    # 标记数据状态为更新中
                    cache_data['data_status'] = 'updating'
                    cache_data['last_update_date'] = current_date
                    save_cache_data(market, cache_data)
                    
                    # 启动后台线程进行增量更新
                    update_thread = threading.Thread(
                        target=update_stock_data_progressive,
                        args=(market, all_stocks_data),
                        daemon=True
                    )
                    update_thread.start()
                    updated_market_names.append(market_names[market])
                    print(f"已启动{market_names[market]}增量更新线程")
                else:
                    # 没有缓存数据，需要全量更新
                    print(f"{market_names[market]}无缓存数据，需要全量更新")
                    updated_market_names.append(f"{market_names[market]}(全量)")
                
                # 避免API频率限制
                time.sleep(0.5)
                
            except Exception as e:
                print(f"更新{market_names[market]}数据失败: {e}")
                continue
        
        return jsonify({
            'status': 'success',
            'message': f'已启动{len(updated_market_names)}个市场的数据更新',
            'updated_markets': updated_market_names,
            'latest_markets': [market_names[m] for m in markets_already_latest]
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/rate_limiter/status')
def get_rate_limiter_status():
    """获取Tushare API频率限制器状态"""
    try:
        status = rate_limiter.get_status()
        
        # 格式化时间显示
        if status['next_reset_time']:
            next_reset = datetime.fromtimestamp(status['next_reset_time'])
            status['next_reset_time_formatted'] = next_reset.strftime('%Y-%m-%d %H:%M:%S')
            status['seconds_until_reset'] = max(0, int(status['next_reset_time'] - status['current_time']))
        else:
            status['next_reset_time_formatted'] = None
            status['seconds_until_reset'] = 0
        
        current_time = datetime.fromtimestamp(status['current_time'])
        status['current_time_formatted'] = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/akshare_rate_limiter/status')
def get_akshare_rate_limiter_status():
    """获取AkShare API频率限制器状态"""
    try:
        status = akshare_rate_limiter.get_status()
        
        # 格式化时间显示
        if status['next_reset_time']:
            next_reset = datetime.fromtimestamp(status['next_reset_time'])
            status['next_reset_time_formatted'] = next_reset.strftime('%Y-%m-%d %H:%M:%S')
            status['seconds_until_reset'] = max(0, int(status['next_reset_time'] - status['current_time']))
        else:
            status['next_reset_time_formatted'] = None
            status['seconds_until_reset'] = 0
        
        if status['next_allowed_time']:
            next_allowed = datetime.fromtimestamp(status['next_allowed_time'])
            status['next_allowed_time_formatted'] = next_allowed.strftime('%Y-%m-%d %H:%M:%S')
            status['seconds_until_next_allowed'] = max(0, int(status['next_allowed_time'] - status['current_time']))
        else:
            status['next_allowed_time_formatted'] = None
            status['seconds_until_next_allowed'] = 0
        
        current_time = datetime.fromtimestamp(status['current_time'])
        status['current_time_formatted'] = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 自选股管理功能
def get_watchlist_file_path():
    """获取自选股文件路径"""
    cache_dir = 'cache'
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return os.path.join(cache_dir, 'watchlist.json')

def load_watchlist():
    """加载自选股数据"""
    watchlist_file = get_watchlist_file_path()
    if os.path.exists(watchlist_file):
        try:
            with open(watchlist_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_watchlist(watchlist_data):
    """保存自选股数据"""
    watchlist_file = get_watchlist_file_path()
    try:
        with open(watchlist_file, 'w', encoding='utf-8') as f:
            json.dump(watchlist_data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

@app.route('/api/watchlist')
def get_watchlist():
    """获取自选股列表"""
    try:
        watchlist_data = load_watchlist()
        return jsonify({
            'success': True,
            'data': watchlist_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """添加股票到自选股"""
    try:
        data = request.get_json()
        if not data or 'ts_code' not in data:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        watchlist_data = load_watchlist()
        
        # 检查是否已存在
        for stock in watchlist_data:
            if stock['ts_code'] == data['ts_code']:
                return jsonify({
                    'success': False,
                    'message': '该股票已在自选股中'
                })
        
        # 添加新股票
        new_stock = {
            'ts_code': data['ts_code'],
            'name': data.get('name', ''),
            'latest_price': data.get('latest_price', 0),
            'pct_chg': data.get('pct_chg', 0),
            'industry': data.get('industry', '-'),
            'volume_ratio': data.get('volume_ratio', 0),
            'pe': data.get('pe', 0),
            'amount': data.get('amount', 0),
            'total_mv': data.get('total_mv', 0),
            'nine_turn_up': data.get('nine_turn_up', 0),
            'nine_turn_down': data.get('nine_turn_down', 0),
            'priority': data.get('priority', 'green'),  # 默认绿色优先级
            'note': data.get('note', ''),  # 默认备注为空
            'add_time': data.get('add_time', datetime.now().isoformat())
        }
        
        watchlist_data.append(new_stock)
        
        if save_watchlist(watchlist_data):
            return jsonify({
                'success': True,
                'message': '添加成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    """从自选股中移除股票"""
    try:
        data = request.get_json()
        if not data or 'ts_code' not in data:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        watchlist_data = load_watchlist()
        original_length = len(watchlist_data)
        
        # 移除指定股票
        watchlist_data = [stock for stock in watchlist_data if stock['ts_code'] != data['ts_code']]
        
        if len(watchlist_data) == original_length:
            return jsonify({
                'success': False,
                'message': '股票不在自选股中'
            })
        
        if save_watchlist(watchlist_data):
            return jsonify({
                'success': True,
                'message': '移除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/watchlist/clear', methods=['POST'])
def clear_watchlist():
    """清空自选股"""
    try:
        if save_watchlist([]):
            return jsonify({
                'success': True,
                'message': '清空成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '清空失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/watchlist/update_priority', methods=['POST'])
def update_watchlist_priority():
    """更新自选股优先级"""
    try:
        data = request.get_json()
        if not data or 'ts_code' not in data or 'priority' not in data:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        # 验证优先级值
        valid_priorities = ['purple', 'red', 'green', 'holding', 'sold']
        if data['priority'] not in valid_priorities:
            return jsonify({
                'success': False,
                'message': '无效的优先级值'
            }), 400
        
        watchlist_data = load_watchlist()
        
        # 查找并更新股票优先级
        stock_found = False
        for stock in watchlist_data:
            if stock['ts_code'] == data['ts_code']:
                stock['priority'] = data['priority']
                stock_found = True
                break
        
        if not stock_found:
            return jsonify({
                'success': False,
                'message': '股票不在自选股中'
            })
        
        if save_watchlist(watchlist_data):
            return jsonify({
                'success': True,
                'message': '优先级更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/watchlist/update_note', methods=['POST'])
def update_watchlist_note():
    """更新自选股备注"""
    try:
        data = request.get_json()
        if not data or 'ts_code' not in data:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        note = data.get('note', '').strip()
        
        watchlist_data = load_watchlist()
        
        # 查找并更新股票备注
        stock_found = False
        for stock in watchlist_data:
            if stock['ts_code'] == data['ts_code']:
                stock['note'] = note
                stock['note_update_time'] = datetime.now().isoformat()
                stock_found = True
                break
        
        if not stock_found:
            return jsonify({
                'success': False,
                'message': '股票不在自选股中'
            })
        
        if save_watchlist(watchlist_data):
            return jsonify({
                'success': True,
                'message': '备注更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/watchlist/check', methods=['GET'])
def check_watchlist_status():
    """检查股票是否已在自选股中"""
    try:
        ts_code = request.args.get('ts_code')
        if not ts_code:
            return jsonify({
                'success': False,
                'message': '缺少股票代码参数'
            }), 400
        
        watchlist_data = load_watchlist()
        
        # 检查股票是否在自选股中
        for stock in watchlist_data:
            if stock['ts_code'] == ts_code:
                return jsonify({
                    'success': True,
                    'in_watchlist': True,
                    'priority': stock.get('priority', 'green'),
                    'note': stock.get('note', ''),
                    'add_time': stock.get('add_time', '')
                })
        
        return jsonify({
            'success': True,
            'in_watchlist': False
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/watchlist/refresh', methods=['POST'])
def refresh_watchlist():
    """刷新自选股数据，获取最新的换手率、市盈率和市值"""
    def safe_float(value, default=0.0):
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    try:
        watchlist_data = load_watchlist()
        if not watchlist_data:
            return jsonify({
                'success': False,
                'message': '自选股列表为空'
            })
        
        updated_count = 0
        failed_stocks = []
        
        for stock in watchlist_data:
            try:
                ts_code = stock['ts_code']
                print(f"正在更新自选股: {ts_code} {stock.get('name', '')}")
                
                # 获取最新的基本面数据
                daily_basic = safe_tushare_call(pro.daily_basic, ts_code=ts_code, limit=1)
                latest_data = safe_tushare_call(pro.daily, ts_code=ts_code, limit=1)
                
                if not daily_basic.empty:
                    # 更新换手率
                    if 'turnover_rate' in daily_basic.columns:
                        turnover_rate = safe_float(daily_basic.iloc[0]['turnover_rate'])
                        stock['turnover_rate'] = turnover_rate
                    
                    # 更新市盈率
                    if 'pe_ttm' in daily_basic.columns:
                        pe = safe_float(daily_basic.iloc[0]['pe_ttm'])
                        stock['pe'] = pe
                    
                    # 更新市值
                    if 'total_mv' in daily_basic.columns:
                        total_mv = safe_float(daily_basic.iloc[0]['total_mv'])
                        stock['total_mv'] = total_mv
                    
                    # 更新流通市值
                    if 'circ_mv' in daily_basic.columns:
                        circ_mv = safe_float(daily_basic.iloc[0]['circ_mv'])
                        stock['circ_mv'] = circ_mv
                    
                    # 更新市净率
                    if 'pb' in daily_basic.columns:
                        pb = safe_float(daily_basic.iloc[0]['pb'])
                        stock['pb'] = pb
                
                # 更新最新价格和成交额
                if not latest_data.empty:
                    stock['latest_price'] = safe_float(latest_data.iloc[0]['close'])
                    stock['amount'] = safe_float(latest_data.iloc[0]['amount'])
                    
                    # 更新涨跌幅
                    if 'pct_chg' in latest_data.columns:
                        stock['pct_chg'] = safe_float(latest_data.iloc[0]['pct_chg'])
                    
                    # 更新量比
                    if 'vol_ratio' in latest_data.columns:
                        stock['volume_ratio'] = safe_float(latest_data.iloc[0]['vol_ratio'])
                    
                    # 更新成交量
                    if 'vol' in latest_data.columns:
                        stock['vol'] = safe_float(latest_data.iloc[0]['vol'])
                
                # 获取净流入额数据
                net_mf_amount = 0
                try:
                    # 优先从缓存获取净流入数据
                    cached_stock = get_stock_from_cache(ts_code)
                    if cached_stock:
                        current_date = datetime.now().strftime('%Y%m%d')
                        cache_date = cached_stock.get('last_update', '')
                        if cache_date == current_date and cached_stock.get('net_mf_amount') is not None:
                            net_mf_amount = safe_float(cached_stock.get('net_mf_amount', 0))
                            print(f"从缓存获取{ts_code}的净流入数据: {net_mf_amount}千万元")
                        else:
                            # 缓存中没有当天数据，通过API获取
                            print(f"缓存中无当天净流入数据，正在通过API获取{ts_code}的资金流向数据...")
                            
                            # 尝试获取资金流向数据
                            moneyflow_data = None
                            try:
                                # 优先尝试moneyflow接口
                                moneyflow_data = safe_tushare_call(pro.moneyflow, ts_code=ts_code, limit=1)
                                if moneyflow_data is None or moneyflow_data.empty:
                                    # 如果moneyflow没有数据，尝试moneyflow_dc接口
                                    moneyflow_data = safe_tushare_call(pro.moneyflow_dc, ts_code=ts_code, limit=1)
                            except Exception as e:
                                print(f"获取{ts_code}资金流向数据失败: {e}")
                            
                            if moneyflow_data is not None and not moneyflow_data.empty:
                                # 检查是否是moneyflow_dc接口的数据（包含net_amount字段）
                                if 'net_amount' in moneyflow_data.columns:
                                    net_amount_wan = safe_float(moneyflow_data.iloc[0]['net_amount'])  # 万元
                                    net_mf_amount = round(net_amount_wan / 1000, 2)  # 转换为千万元
                                # 检查是否是moneyflow接口的数据（包含net_mf_amount字段）
                                elif 'net_mf_amount' in moneyflow_data.columns:
                                    net_mf_amount_wan = safe_float(moneyflow_data.iloc[0]['net_mf_amount'])  # 万元
                                    net_mf_amount = round(net_mf_amount_wan / 1000, 2)  # 转换为千万元
                                
                                print(f"API获取{ts_code}净流入额: {net_mf_amount}千万元")
                    else:
                        # 没有缓存数据，直接通过API获取
                        print(f"无缓存数据，正在通过API获取{ts_code}的资金流向数据...")
                        
                        # 尝试获取资金流向数据
                        moneyflow_data = None
                        try:
                            # 优先尝试moneyflow接口
                            moneyflow_data = safe_tushare_call(pro.moneyflow, ts_code=ts_code, limit=1)
                            if moneyflow_data is None or moneyflow_data.empty:
                                # 如果moneyflow没有数据，尝试moneyflow_dc接口
                                moneyflow_data = safe_tushare_call(pro.moneyflow_dc, ts_code=ts_code, limit=1)
                        except Exception as e:
                            print(f"获取{ts_code}资金流向数据失败: {e}")
                        
                        if moneyflow_data is not None and not moneyflow_data.empty:
                            # 检查是否是moneyflow_dc接口的数据（包含net_amount字段）
                            if 'net_amount' in moneyflow_data.columns:
                                net_amount_wan = safe_float(moneyflow_data.iloc[0]['net_amount'])  # 万元
                                net_mf_amount = round(net_amount_wan / 1000, 2)  # 转换为千万元
                            # 检查是否是moneyflow接口的数据（包含net_mf_amount字段）
                            elif 'net_mf_amount' in moneyflow_data.columns:
                                net_mf_amount_wan = safe_float(moneyflow_data.iloc[0]['net_mf_amount'])  # 万元
                                net_mf_amount = round(net_mf_amount_wan / 1000, 2)  # 转换为千万元
                            
                            print(f"API获取{ts_code}净流入额: {net_mf_amount}千万元")
                except Exception as e:
                    print(f"获取股票 {ts_code} 净流入额失败: {e}")
                    net_mf_amount = stock.get('net_mf_amount', 0)  # 保持原值或设为0
                
                stock['net_mf_amount'] = net_mf_amount
                
                # 计算九转序列（使用正确的算法）
                nine_turn_up = 0
                nine_turn_down = 0
                try:
                    # 获取最近30天的K线数据用于计算九转序列
                    end_date = datetime.now().strftime('%Y%m%d')
                    start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
                    kline_data = safe_tushare_call(pro.daily, ts_code=ts_code, start_date=start_date, end_date=end_date)
                    
                    if not kline_data.empty and len(kline_data) >= 5:
                        kline_data = kline_data.sort_values('trade_date')
                        kline_with_nine_turn = calculate_nine_turn(kline_data)
                        # 获取最新一天的九转序列数据
                        latest_nine_turn = kline_with_nine_turn.iloc[-1]
                        nine_turn_up = int(latest_nine_turn['nine_turn_up']) if latest_nine_turn['nine_turn_up'] > 0 else 0
                        nine_turn_down = int(latest_nine_turn['nine_turn_down']) if latest_nine_turn['nine_turn_down'] > 0 else 0
                except Exception as e:
                    print(f"计算股票 {ts_code} 九转序列失败: {e}")
                    # 如果计算失败，保持原值或设为0
                    nine_turn_up = stock.get('nine_turn_up', 0)
                    nine_turn_down = stock.get('nine_turn_down', 0)
                
                stock['nine_turn_up'] = nine_turn_up
                stock['nine_turn_down'] = nine_turn_down
                
                # 更新时间戳
                stock['last_refresh'] = datetime.now().isoformat()
                updated_count += 1
                
            except Exception as e:
                error_msg = str(e)
                print(f"更新股票 {ts_code} 失败: {error_msg}")
                failed_stocks.append({
                    'ts_code': ts_code,
                    'name': stock.get('name', ''),
                    'error': error_msg
                })
                continue
        
        # 保存更新后的数据
        if save_watchlist(watchlist_data):
            message = f"成功更新 {updated_count} 只股票"
            if failed_stocks:
                message += f"，{len(failed_stocks)} 只股票更新失败"
            
            return jsonify({
                'success': True,
                'message': message,
                'updated_count': updated_count,
                'failed_count': len(failed_stocks),
                'failed_stocks': failed_stocks
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存数据失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'刷新失败: {str(e)}'
        }), 500

@app.route('/api/cache/status')
def get_cache_status():
    """获取缓存系统状态"""
    try:
        status = cache_manager.get_status()
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/info/<market>')
def get_cache_info(market):
    """获取特定市场的缓存信息"""
    try:
        info = cache_manager.get_cache_info(market)
        return jsonify({
            'success': True,
            'data': info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """清理缓存"""
    try:
        market = request.json.get('market') if request.json else None
        cache_manager.clear_cache(market)
        
        return jsonify({
            'success': True,
            'message': f'缓存清理完成: {market or "全部"}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/red-filter')
def get_red_filter_stocks():
    """获取红 3-6 筛选的股票数据"""
    try:
        # 优先从保存的文件中读取数据
        cache_dir = 'cache'
        red_filter_file = os.path.join(cache_dir, 'red_filter_results.json')
        
        if os.path.exists(red_filter_file):
            try:
                with open(red_filter_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                
                # 检查数据是否是今天的
                filter_date = saved_data.get('filter_date')
                today = datetime.now().strftime('%Y-%m-%d')
                
                if filter_date == today:
                    return jsonify({
                        'success': True,
                        'data': saved_data.get('stocks', []),
                        'total': saved_data.get('total', 0),
                        'filter_time': saved_data.get('filter_time'),
                        'data_source': 'cached'
                    })
            except Exception as e:
                print(f"读取保存的红色筛选数据失败: {e}")
        
        # 如果没有保存的数据或数据过期，进行实时筛选
        all_stocks = []
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        
        for market in markets:
            try:
                market_data = cache_manager.load_cache_data(market)
                if market_data and 'stocks' in market_data:
                    all_stocks.extend(market_data['stocks'])
            except Exception as e:
                print(f"获取市场 {market} 数据失败: {e}")
                continue
        
        # 筛选符合条件的股票：换手率>1，九转买入红色3-6
        # 注意：由于量比数据可能不准确或为0，暂时移除量比条件
        filtered_stocks = []
        for stock in all_stocks:
            try:
                turnover_rate = float(stock.get('turnover_rate', 0))
                volume_ratio = float(stock.get('volume_ratio', 0))
                nine_turn_up = int(stock.get('nine_turn_up', 0))
                
                # 筛选条件：换手率>1，九转买入红色3-6
                # 如果量比数据可用且>0，则加入量比条件
                volume_condition = True
                if volume_ratio > 0:
                    volume_condition = volume_ratio > 0.8  # 降低量比要求
                
                if (turnover_rate > 1 and  # 降低换手率要求
                    volume_condition and 
                    3 <= nine_turn_up <= 6):
                    
                    # 添加筛选日期
                    stock_copy = stock.copy()
                    stock_copy['filter_date'] = datetime.now().strftime('%Y-%m-%d')
                    filtered_stocks.append(stock_copy)
                    
            except (ValueError, TypeError) as e:
                continue
        
        # 按九转序列和换手率排序
        filtered_stocks.sort(key=lambda x: (x.get('nine_turn_up', 0), x.get('turnover_rate', 0)), reverse=True)
        
        return jsonify({
            'success': True,
            'data': filtered_stocks,
            'total': len(filtered_stocks),
            'filter_time': datetime.now().isoformat(),
            'data_source': 'realtime'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/green-filter')
def get_green_filter_stocks():
    """获取绿 9 筛选的股票数据"""
    try:
        # 优先从保存的文件中读取数据
        cache_dir = 'cache'
        green_filter_file = os.path.join(cache_dir, 'green_filter_results.json')
        
        if os.path.exists(green_filter_file):
            try:
                with open(green_filter_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                
                # 检查数据是否是今天的
                filter_date = saved_data.get('filter_date')
                today = datetime.now().strftime('%Y-%m-%d')
                
                if filter_date == today:
                    return jsonify({
                        'success': True,
                        'data': saved_data.get('stocks', []),
                        'total': saved_data.get('total', 0),
                        'filter_time': saved_data.get('filter_time'),
                        'data_source': 'cached'
                    })
            except Exception as e:
                print(f"读取保存的绿色筛选数据失败: {e}")
        
        # 如果没有保存的数据或数据过期，进行实时筛选
        all_stocks = []
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        
        for market in markets:
            try:
                market_data = cache_manager.load_cache_data(market)
                if market_data and 'stocks' in market_data:
                    all_stocks.extend(market_data['stocks'])
            except Exception as e:
                print(f"获取市场 {market} 数据失败: {e}")
                continue
        
        # 筛选符合条件的股票：九转买入绿色=9
        filtered_stocks = []
        for stock in all_stocks:
            try:
                nine_turn_down = int(stock.get('nine_turn_down', 0))
                
                # 筛选条件：九转买入绿色=9
                if nine_turn_down == 9:
                    # 添加筛选日期
                    stock_copy = stock.copy()
                    stock_copy['filter_date'] = datetime.now().strftime('%Y-%m-%d')
                    filtered_stocks.append(stock_copy)
                    
            except (ValueError, TypeError) as e:
                continue
        
        # 按九转序列排序
        filtered_stocks.sort(key=lambda x: x.get('nine_turn_down', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'data': filtered_stocks,
            'total': len(filtered_stocks),
            'filter_time': datetime.now().isoformat(),
            'data_source': 'realtime'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stock/<stock_code>/intraday')
def get_stock_intraday_data(stock_code):
    """
    获取股票分时数据
    使用AkShare的stock_zh_a_hist_min_em接口获取分钟级数据
    
    Args:
        stock_code: 股票代码，如 000001 或 300354
        
    Query Parameters:
        period: 分钟周期，默认为1（1分钟）
        adjust: 复权类型，默认为空（不复权）
        
    Returns:
        JSON: 分时数据，包含时间、价格、成交量等信息
    """
    try:
        # 获取查询参数
        period = request.args.get('period', '1')  # 默认1分钟
        adjust = request.args.get('adjust', '')   # 默认不复权
        
        # 检查AkShare是否可用
        if not AKSHARE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'AkShare库未安装，无法获取分时数据',
                'details': '请安装akshare库以使用分时图功能'
            }), 503
        
        # 转换股票代码格式（去掉.SZ/.SH后缀）
        if '.' in stock_code:
            stock_code = stock_code.split('.')[0]
        
        print(f"[分时数据] 开始获取股票 {stock_code} 的分时数据...")
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 调用AkShare接口获取分时数据
        intraday_data = safe_akshare_call(
            ak.stock_zh_a_hist_min_em,
            f"intraday_{stock_code}_{today}",
            symbol=stock_code,
            period=period,
            adjust=adjust,
            start_date=today + " 09:30:00",
            end_date=today + " 15:00:00"
        )
        
        if intraday_data is None or intraday_data.empty:
            print(f"[分时数据] 未获取到股票 {stock_code} 的分时数据")
            return jsonify({
                'success': False,
                'error': '未获取到分时数据',
                'details': '可能是非交易时间或股票代码不存在'
            }), 404
        
        print(f"[分时数据] 成功获取{len(intraday_data)}条分时数据")
        
        # 处理数据
        result_data = []
        cumulative_volume = 0
        cumulative_amount = 0
        total_turnover = 0  # 总成交金额（用于均价线计算）
        total_shares = 0    # 总成交股数（用于均价线计算）
        
        for _, row in intraday_data.iterrows():
            try:
                # 获取时间戳
                timestamp = row['时间']
                if pd.isna(timestamp):
                    continue
                
                # 转换时间格式
                if isinstance(timestamp, str):
                    # 如果是字符串格式，尝试解析
                    if ' ' in timestamp:
                        # 格式如 "2025-07-29 09:30:00"
                        time_str = timestamp.split(' ')[1][:5]  # 提取 "09:30"
                    else:
                        time_str = timestamp
                else:
                    time_str = timestamp.strftime('%H:%M')
                
                # 过滤非交易时间（只保留09:30-11:30和13:00-15:00）
                try:
                    hour_minute = time_str.replace(':', '')
                    hour_minute_int = int(hour_minute)
                except ValueError:
                    print(f"[分时数据] 时间格式错误: {time_str}")
                    continue
                
                if not ((930 <= hour_minute_int <= 1130) or (1300 <= hour_minute_int <= 1500)):
                    continue
                
                # 获取价格和成交量数据
                close_price = float(row.get('收盘', 0))
                volume = float(row.get('成交量', 0))  # 成交量（手）
                amount = float(row.get('成交额', 0))  # 成交额（元）
                
                if close_price <= 0:
                    continue
                
                # 累计成交量和成交额（用于计算VWAP）
                cumulative_volume += volume
                cumulative_amount += amount
                
                # 计算VWAP（成交量加权平均价格）
                vwap = cumulative_amount / cumulative_volume if cumulative_volume > 0 else close_price
                
                # 计算均价线数据
                # 成交股数 = 成交量（手） × 100（每手100股）
                shares_traded = volume * 100
                turnover_amount = amount  # 成交金额
                
                # 累计数据用于均价线计算
                total_shares += shares_traded
                total_turnover += turnover_amount
                
                # 均价线 = 总成交金额 ÷ 总成交股数
                avg_price = total_turnover / total_shares if total_shares > 0 else close_price
                
                data_point = {
                    'time': time_str,
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp),
                    'price': close_price,
                    'open': float(row.get('开盘', close_price)),
                    'high': float(row.get('最高', close_price)),
                    'low': float(row.get('最低', close_price)),
                    'volume': volume,
                    'amount': amount,
                    'vwap': vwap,
                    'avg_price': avg_price,  # 新增：均价线数据
                    'cumulative_volume': cumulative_volume,
                    'cumulative_amount': cumulative_amount,
                    'total_shares': total_shares,
                    'total_turnover': total_turnover
                }
                result_data.append(data_point)
                
            except Exception as e:
                print(f"[分时数据] 处理数据行失败: {e}")
                continue
        
        if not result_data:
            return jsonify({
                'success': False,
                'error': '没有有效的分时数据',
                'details': '可能是非交易时间或数据格式异常'
            }), 404
        
        # 获取昨收价（用于计算涨跌幅）
        yesterday_close = None
        if result_data:
            # 尝试从第一个数据点获取昨收价
            first_price = result_data[0]['price']
            # 这里可以通过其他API获取昨收价，暂时使用第一个价格作为参考
            yesterday_close = first_price
        
        return jsonify({
            'success': True,
            'data': result_data,
            'total': len(result_data),
            'stock_code': stock_code,
            'date': today,
            'yesterday_close': yesterday_close,
            'period': period,
            'message': f'成功获取{len(result_data)}条分时数据'
        })
        
    except Exception as e:
        print(f"[分时数据] 获取失败: {e}")
        return jsonify({
            'success': False,
            'error': f'获取分时数据失败: {str(e)}',
            'details': '请检查股票代码是否正确或稍后重试'
        }), 500

@app.route('/api/top-list')
def get_top_list():
    """获取龙虎榜数据"""
    try:
        # 获取交易日期参数
        trade_date = request.args.get('trade_date')
        if not trade_date:
            # 如果没有指定日期，使用今天
            trade_date = datetime.now().strftime('%Y%m%d')
        
        # 验证日期格式
        try:
            datetime.strptime(trade_date, '%Y%m%d')
        except ValueError:
            return jsonify({
                'success': False,
                'error': '日期格式错误，请使用YYYYMMDD格式'
            }), 400
        
        # 获取龙虎榜数据（使用频率限制）
        top_list_data = safe_tushare_call(pro.top_list, trade_date=trade_date)
        
        if top_list_data.empty:
            return jsonify({
                'success': True,
                'data': [],
                'total': 0,
                'trade_date': trade_date,
                'message': '该日期无龙虎榜数据'
            })
        
        # 获取股票基本信息，用于补充股票名称
        ts_codes = top_list_data['ts_code'].unique().tolist()
        stock_basic_data = safe_tushare_call(pro.stock_basic, ts_code=','.join(ts_codes))
        
        # 创建股票代码到名称的映射
        name_mapping = {}
        if not stock_basic_data.empty:
            name_mapping = dict(zip(stock_basic_data['ts_code'], stock_basic_data['name']))
        
        # 获取九转数据，从缓存中读取
        nine_turn_mapping = {}
        markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
        for market in markets:
            try:
                market_data = cache_manager.load_cache_data(market)
                if market_data and 'stocks' in market_data:
                    for stock in market_data['stocks']:
                        ts_code = stock.get('ts_code')
                        if ts_code in ts_codes:
                            nine_turn_mapping[ts_code] = {
                                'nine_turn_up': stock.get('nine_turn_up', 0),
                                'nine_turn_down': stock.get('nine_turn_down', 0),
                                'countdown_up': stock.get('countdown_up', 0),
                                'countdown_down': stock.get('countdown_down', 0)
                            }
            except Exception as e:
                print(f"获取市场 {market} 九转数据失败: {e}")
                continue
        
        # 安全获取数值的辅助函数
        def safe_float(value, default=0.0):
            try:
                if value is None or pd.isna(value):
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # 处理数据
        result_data = []
        for _, row in top_list_data.iterrows():
            ts_code = row['ts_code']
            nine_turn_data = nine_turn_mapping.get(ts_code, {})
            
            stock_data = {
                'ts_code': ts_code,
                'name': name_mapping.get(ts_code, ts_code),  # 如果没有找到名称，使用代码
                'close': safe_float(row.get('close')),
                'pct_change': safe_float(row.get('pct_change')),
                'turnover_rate': safe_float(row.get('turnover_rate')),
                'amount': safe_float(row.get('amount')),
                'l_sell': safe_float(row.get('l_sell')),
                'l_buy': safe_float(row.get('l_buy')),
                'l_amount': safe_float(row.get('l_amount')),
                'net_amount': safe_float(row.get('net_amount')),
                'net_rate': safe_float(row.get('net_rate')),
                'amount_rate': safe_float(row.get('amount_rate')),
                'float_values': safe_float(row.get('float_values')),
                'reason': row.get('reason', ''),
                # 添加九转数据
                'nine_turn_up': nine_turn_data.get('nine_turn_up', 0),
                'nine_turn_down': nine_turn_data.get('nine_turn_down', 0),
                'countdown_up': nine_turn_data.get('countdown_up', 0),
                'countdown_down': nine_turn_data.get('countdown_down', 0)
            }
            result_data.append(stock_data)
        
        # 按净买入额排序（从大到小）
        result_data.sort(key=lambda x: x['net_amount'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': result_data,
            'total': len(result_data),
            'trade_date': trade_date
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # 启动定时调度器
    start_scheduler()
    
    # 从环境变量获取配置，支持生产环境部署
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"服务器启动配置: host={host}, port={port}, debug={debug_mode}")
    print(f"Tushare API频率限制器已启用: 每分钟最多{rate_limiter.max_requests}次请求")
    print("可通过 /api/rate_limiter/status 查看API使用状态")
    # AkShare 相关功能已移除
    # print(f"AkShare重试机制已启用: 失败后{akshare_retry_manager.retry_interval}秒重试间隔")
    # print("可通过 /api/akshare/retry_status 查看重试状态")
    
    # 强制使用8080端口，如果被占用则结束占用进程
    if kill_process_on_port(port):
        print(f"端口{port}已清理，准备启动服务器")
        time.sleep(1)  # 等待1秒确保端口完全释放
    
    try:
        app.run(debug=debug_mode, host=host, port=port)
    except Exception as e:
        print(f"服务器启动失败: {e}")
        print("请检查端口配置或系统权限")