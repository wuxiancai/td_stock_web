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

def safe_akshare_call(func, cache_key, *args, **kwargs):
    """安全的AkShare API调用"""
    if not AKSHARE_AVAILABLE or ak is None:
        return None
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"AkShare API调用失败: {e}")
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
                        df.iloc[pos, df.columns.get_loc('nine_turn_up')] = j + 1
            
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
                        df.iloc[pos, df.columns.get_loc('nine_turn_down')] = j + 1
            
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
    
    return df




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stock/<stock_code>')
def stock_detail(stock_code):
    return render_template('stock_detail.html', stock_code=stock_code)

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
            # 交易时间：尝试获取实时数据
            indices_data = get_indices_from_tushare(indices)
            
            if not indices_data:
                print("[指数数据] 实时数据获取失败，返回全0数据等待重试")
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

# AkShare相关函数已删除，现在只使用Tushare获取指数数据

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
        
        # 获取普通日线数据（原始价格，无需复权处理）
        daily_data = safe_tushare_call(pro.daily, ts_code=ts_code, start_date=start_date, end_date=end_date)
        if daily_data.empty:
            return jsonify({'error': '无法获取股票数据'}), 404
        
        # 直接使用原始数据，无需复权处理
        daily_data['adj_factor'] = 1.0
        daily_data['is_adjusted'] = False
        print(f"使用原始价格数据，股票代码: {ts_code}，最新收盘价: {daily_data['close'].iloc[-1]:.2f}")
        
        daily_data = daily_data.sort_values('trade_date').tail(90)
        
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
        
        # 计算当天涨幅
        latest_close = safe_float(daily_data.iloc[-1]['close'])
        pct_chg = 0
        
        # 尝试从daily_data中获取pct_chg字段
        if 'pct_chg' in daily_data.columns and not pd.isna(daily_data.iloc[-1]['pct_chg']):
            pct_chg = safe_float(daily_data.iloc[-1]['pct_chg'])
        elif len(daily_data) >= 2:
            # 如果没有pct_chg字段，从前一天收盘价计算
            yesterday_close = safe_float(daily_data.iloc[-2]['close'])
            if yesterday_close > 0:
                pct_chg = ((latest_close - yesterday_close) / yesterday_close) * 100
        
        # 准备返回数据
        stock_info = {
            'ts_code': ts_code,
            'name': basic_info.iloc[0]['name'],
            'industry': basic_info.iloc[0]['industry'],
            'latest_price': latest_close,
            'pct_chg': pct_chg,  # 添加当天涨幅
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
            'kline_data': daily_data.to_dict('records')
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
        
        # 构造实时数据
        realtime_data = {}
        
        if stock_data:
            # 使用股票数据中的实时信息
            realtime_data['spot'] = {
                'name': stock_data.get('name', ''),
                'latest_price': stock_data.get('latest_price', 0),
                'change_percent': stock_data.get('pct_chg', 0),
                'change_amount': stock_data.get('change_amount', 0),
                'volume': stock_data.get('volume', 0),
                'amount': stock_data.get('amount', 0),
                'turnover_rate': stock_data.get('turnover_rate', 0),
                'volume_ratio': stock_data.get('volume_ratio', 0),
                'pe_ratio': stock_data.get('pe_ttm'),
                'market_cap': stock_data.get('total_mv', 0),
                'open': stock_data.get('open', 0),
                'high': stock_data.get('high', 0),
                'low': stock_data.get('low', 0),
                'pre_close': stock_data.get('pre_close', 0),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': 'live_realtime'  # 标记数据来源
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
                'close_price': stock_data.get('latest_price', 0),
                'change_percent': stock_data.get('pct_chg', 0),
                'main_net_inflow': stock_data.get('net_mf_amount', 0) * 10000
            }
        
        # 添加净流入额
        if stock_data.get('net_mf_amount') is not None:
            realtime_data['net_mf_amount'] = stock_data.get('net_mf_amount', 0)
        
        print(f"[实时数据] 成功获取{ts_code}的实时数据")
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
            
            # 计算涨跌幅
            calculated_change_percent = 0
            calculated_change_amount = 0
            pre_close = 0
            
            if stock_data.get('kline_data') and len(stock_data['kline_data']) > 1:
                current_kline = stock_data['kline_data'][-1]
                prev_kline = stock_data['kline_data'][-2]
                
                current_close = current_kline.get('close', 0)
                prev_close = prev_kline.get('close', 0)
                pre_close = prev_close
                
                if prev_close > 0:
                    calculated_change_amount = current_close - prev_close
                    calculated_change_percent = (calculated_change_amount / prev_close) * 100
                    print(f"[收盘数据] 涨跌幅计算: 当前收盘={current_close:.2f}, 前收盘={prev_close:.2f}, 涨跌幅={calculated_change_percent:.2f}%")
            
            realtime_data['spot'] = {
                'name': stock_data.get('name', ''),
                'latest_price': latest_kline.get('close', 0) if latest_kline else stock_data.get('latest_price', 0),
                'change_percent': calculated_change_percent,
                'change_amount': calculated_change_amount,
                'volume': latest_kline.get('vol', 0) if latest_kline else 0,
                'amount': latest_kline.get('amount', 0) if latest_kline else 0,
                'turnover_rate': stock_data.get('turnover_rate', 0),
                'volume_ratio': 0,  # 非交易时间无法计算量比
                'pe_ratio': stock_data.get('pe_ttm'),
                'market_cap': stock_data.get('total_mv', 0),
                'open': latest_kline.get('open', 0) if latest_kline else 0,
                'high': latest_kline.get('high', 0) if latest_kline else 0,
                'low': latest_kline.get('low', 0) if latest_kline else 0,
                'pre_close': pre_close,
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
        red_filtered_stocks = []
        for stock in all_stocks:
            try:
                turnover_rate = float(stock.get('turnover_rate', 0))
                volume_ratio = float(stock.get('volume_ratio', 0))
                nine_turn_up = int(stock.get('nine_turn_up', 0))
                
                if (turnover_rate > 2 and 
                    volume_ratio > 1 and 
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
        
        # 筛选符合条件的股票：换手率>2，量比>1，九转买入红色3-6
        filtered_stocks = []
        for stock in all_stocks:
            try:
                turnover_rate = float(stock.get('turnover_rate', 0))
                volume_ratio = float(stock.get('volume_ratio', 0))
                nine_turn_up = int(stock.get('nine_turn_up', 0))
                
                # 筛选条件：换手率>2，量比>1，九转买入红色3-6
                if (turnover_rate > 2 and 
                    volume_ratio > 1 and 
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