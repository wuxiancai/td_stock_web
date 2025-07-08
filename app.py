import tushare as ts
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

app = Flask(__name__)
CORS(app)

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
ts.set_token('68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019')
pro = ts.pro_api()

# 包装tushare API调用的函数
def safe_tushare_call(func, *args, **kwargs):
    """安全的tushare API调用，自动处理频率限制"""
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
    计算九转序列和Countdown - 完整TD Sequential算法
    Setup阶段（1-9）：
    - 买入Setup（看跌转涨）：当日收盘价 < 4个交易日前的收盘价，连续满足9次
    - 卖出Setup（看涨转跌）：当日收盘价 > 4个交易日前的收盘价，连续满足9次
    
    Countdown阶段（1-13）：
    - 买入Countdown（寻找反弹）：收盘价 <= 2天前最低价，满足13次（不要求连续）
    - 卖出Countdown（寻找见顶）：收盘价 >= 2天前最高价，满足13次（不要求连续）
    
    规则：
    1. Setup阶段：连续满足条件，中断则全部清除
    2. Countdown阶段：Setup完成后开始，标注1-13，可被新Setup中断
    3. Countdown不要求连续，只要满足条件就计数
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
            
            # 实时显示序列号（从第1个开始）
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
            
            # 实时显示序列号（从第1个开始）
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
            
        # 如果强制刷新，清除相关缓存
        if force_refresh:
            print(f"强制刷新股票数据: {ts_code}")
            # 这里可以添加清除特定股票缓存的逻辑
        
        # 获取基本信息（使用频率限制）
        basic_info = safe_tushare_call(pro.stock_basic, ts_code=ts_code)
        if basic_info.empty:
            return jsonify({'error': '股票代码不存在'}), 404
        
        # 获取最近90天的日K线数据（使用频率限制）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')
        
        daily_data = safe_tushare_call(pro.daily, ts_code=ts_code, start_date=start_date, end_date=end_date)
        if daily_data.empty:
            return jsonify({'error': '无法获取股票数据'}), 404
        
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
        
        # 获取资金流向数据（尝试两个接口，使用频率限制）
        moneyflow_data = None
        try:
            # 优先尝试moneyflow_dc接口（需要5000积分，数据更详细）
            moneyflow_data = safe_tushare_call(pro.moneyflow_dc, ts_code=ts_code, limit=1)
            if moneyflow_data.empty:
                # 如果moneyflow_dc没有数据，尝试moneyflow接口（需要2000积分）
                moneyflow_data = safe_tushare_call(pro.moneyflow, ts_code=ts_code, limit=1)
        except Exception as e:
            print(f"获取资金流向数据失败: {e}")
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
        
        # 添加资金流向数据（如果可用）
        if moneyflow_data is not None and not moneyflow_data.empty:
            # 检查是否是moneyflow_dc接口的数据（包含net_amount字段）
            if 'net_amount' in moneyflow_data.columns:
                stock_info['moneyflow'] = {
                    'net_amount': safe_float(moneyflow_data.iloc[0]['net_amount']),  # 主力净流入额（万元）
                    'net_amount_rate': safe_float(moneyflow_data.iloc[0]['net_amount_rate']),  # 主力净流入净占比
                    'buy_elg_amount': safe_float(moneyflow_data.iloc[0]['buy_elg_amount']),  # 超大单净流入额
                    'buy_lg_amount': safe_float(moneyflow_data.iloc[0]['buy_lg_amount']),  # 大单净流入额
                    'buy_md_amount': safe_float(moneyflow_data.iloc[0]['buy_md_amount']),  # 中单净流入额
                    'buy_sm_amount': safe_float(moneyflow_data.iloc[0]['buy_sm_amount']),  # 小单净流入额
                    'data_source': 'moneyflow_dc'
                }
            # 检查是否是moneyflow接口的数据（包含net_mf_amount字段）
            elif 'net_mf_amount' in moneyflow_data.columns:
                stock_info['moneyflow'] = {
                    'net_amount': safe_float(moneyflow_data.iloc[0]['net_mf_amount']),  # 净流入额（万元）
                    'buy_elg_amount': safe_float(moneyflow_data.iloc[0]['buy_elg_amount']),  # 特大单买入金额
                    'sell_elg_amount': safe_float(moneyflow_data.iloc[0]['sell_elg_amount']),  # 特大单卖出金额
                    'buy_lg_amount': safe_float(moneyflow_data.iloc[0]['buy_lg_amount']),  # 大单买入金额
                    'sell_lg_amount': safe_float(moneyflow_data.iloc[0]['sell_lg_amount']),  # 大单卖出金额
                    'data_source': 'moneyflow'
                }
        else:
            stock_info['moneyflow'] = None
        
        return jsonify(stock_info)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
                
                # 先返回基本信息，避免长时间等待
                all_stocks_data = []
                for i, (_, stock) in enumerate(stocks.iterrows()):
                    # 先添加基本信息
                    stock_info = {
                        'ts_code': stock['ts_code'],
                        'name': stock['name'],
                        'industry': stock['industry'],
                        'latest_price': 0,
                        'pct_chg': 0,  # 添加当天涨幅字段
                        'turnover_rate': 0,
                        'volume_ratio': 0,
                        'amount': 0,
                        'market_cap': 0,
                        'pe_ttm': 0,
                        'nine_turn_up': 0,
                        'nine_turn_down': 0,
                        'last_update': current_date
                    }
                    all_stocks_data.append(stock_info)
                    
                    # 每处理10只股票打印一次进度
                    if (i + 1) % 10 == 0:
                        print(f"已处理 {i + 1}/{len(stocks)} 只股票")
                
                print(f"完成{market}市场基本信息获取，共{len(all_stocks_data)}只股票")
                
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
        print(f"已启动后台线程更新{market}市场实时数据")
        
        return jsonify({
            'success': True, 
            'message': f'{market}市场数据刷新已启动',
            'total_stocks': len(all_stocks_data)
        })
        
    except Exception as e:
        print(f"强制刷新{market}市场数据失败: {e}")
        return jsonify({'error': str(e)}), 500

# 定时任务功能
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

def start_scheduler():
    """启动定时调度器"""
    # 设置定时任务：工作日下午5点执行
    schedule.every().monday.at("17:00").do(auto_sync_all_markets)
    schedule.every().tuesday.at("17:00").do(auto_sync_all_markets)
    schedule.every().wednesday.at("17:00").do(auto_sync_all_markets)
    schedule.every().thursday.at("17:00").do(auto_sync_all_markets)
    schedule.every().friday.at("17:00").do(auto_sync_all_markets)
    
    print("定时任务已设置：工作日下午5点自动同步所有A股数据")
    
    # 在后台线程中运行调度器
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("定时调度器已启动")

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
        valid_priorities = ['purple', 'red', 'blue', 'green']
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
    
    try:
        app.run(debug=debug_mode, host=host, port=port)
    except Exception as e:
        print(f"服务器启动失败: {e}")
        # 如果指定端口失败，尝试查找可用端口（仅在开发模式下）
        if debug_mode:
            available_port = find_available_port()
            if available_port:
                print(f"尝试使用可用端口: {available_port}")
                app.run(debug=debug_mode, host=host, port=available_port)
            else:
                print("无法找到可用端口")
        else:
            raise