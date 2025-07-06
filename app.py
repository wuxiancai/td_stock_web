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

app = Flask(__name__)
CORS(app)

# Tushare配置
ts.set_token('68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019')
pro = ts.pro_api()

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

def get_cache_file_path(market):
    """获取缓存文件路径"""
    cache_dir = 'cache'
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return os.path.join(cache_dir, f'{market}_stocks_cache.json')

def load_cache_data(market):
    """加载缓存数据"""
    cache_file = get_cache_file_path(market)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None

def save_cache_data(market, data):
    """保存缓存数据"""
    cache_file = get_cache_file_path(market)
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

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
            
            # 获取最新价格和基本面数据
            latest_data = pro.daily(ts_code=stock_info['ts_code'], limit=1)
            daily_basic = pro.daily_basic(ts_code=stock_info['ts_code'], limit=1)
            
            # 获取最近30天的K线数据用于计算九转序列
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=45)).strftime('%Y%m%d')
            kline_data = pro.daily(ts_code=stock_info['ts_code'], start_date=start_date, end_date=end_date)
            
            # 更新实时数据
            if not latest_data.empty:
                stock_info['latest_price'] = safe_float(latest_data.iloc[0]['close'])
                stock_info['amount'] = safe_float(latest_data.iloc[0]['amount'])
            
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
            print(f"更新股票{stock_info['ts_code']}数据失败: {e}")
            # 即使失败也标记为已处理
            stock_info['data_loaded'] = False
            stock_info['last_update'] = current_date
            continue
        
        # 避免API频率限制
        time.sleep(0.5)
    
    # 检查更新是否被取消
    if market in update_status and update_status[market].get('status') == 'cancelled':
        print(f"{market}市场更新被取消，不保存最终状态")
        return
    
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
    
    # 更新全局状态
    update_status[market] = {
        'total': len(working_stocks_list),
        'completed': len(working_stocks_list),
        'status': 'complete',
        'end_time': time.time()
    }
    
    print(f"完成{market}市场所有股票数据的渐进式更新！")

def calculate_nine_turn(df):
    """
    计算九转序列 - 标准算法
    上涨九转：当日收盘价 > 4个交易日前的收盘价，连续满足条件
    下跌九转：当日收盘价 < 4个交易日前的收盘价，连续满足条件
    规则：
    1. 只有连续6天满足条件时才开始显示序列1-6
    2. 第7、8、9天继续满足条件则显示7、8、9
    3. 如果中途中断，则前面的序列全部消失
    """
    df = df.copy()
    df['nine_turn_up'] = 0
    df['nine_turn_down'] = 0
    
    # 计算上涨九转序列
    up_count = 0
    up_positions = []  # 记录满足条件的位置
    
    for i in range(4, len(df)):  # 从第5个数据开始，因为需要比较4天前的数据
        # 当日收盘价 > 4个交易日前的收盘价
        if df.iloc[i]['close'] > df.iloc[i-4]['close']:
            up_count += 1
            up_positions.append(i)
            
            # 只有连续3天或以上满足条件时才开始显示
            if up_count >= 3:
                # 显示所有序列号
                for j, pos in enumerate(up_positions):
                    if j < 9:  # 最多显示9个
                        df.iloc[pos, df.columns.get_loc('nine_turn_up')] = j + 1
            
            # 如果达到9个，停止计数
            if up_count >= 9:
                up_count = 0
                up_positions = []
        else:
            # 如果中断，清除所有标记
            for pos in up_positions:
                df.iloc[pos, df.columns.get_loc('nine_turn_up')] = 0
            up_count = 0
            up_positions = []
    
    # 计算下跌九转序列
    down_count = 0
    down_positions = []  # 记录满足条件的位置
    
    for i in range(4, len(df)):  # 从第5个数据开始，因为需要比较4天前的数据
        # 当日收盘价 < 4个交易日前的收盘价
        if df.iloc[i]['close'] < df.iloc[i-4]['close']:
            down_count += 1
            down_positions.append(i)
            
            # 只有连续3天或以上满足条件时才开始显示
            if down_count >= 3:
                # 显示所有序列号
                for j, pos in enumerate(down_positions):
                    if j < 9:  # 最多显示9个
                        df.iloc[pos, df.columns.get_loc('nine_turn_down')] = j + 1
            
            # 如果达到9个，停止计数
            if down_count >= 9:
                down_count = 0
                down_positions = []
        else:
            # 如果中断，清除所有标记
            for pos in down_positions:
                df.iloc[pos, df.columns.get_loc('nine_turn_down')] = 0
            down_count = 0
            down_positions = []
    
    return df



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stock/<stock_code>')
def stock_detail(stock_code):
    return render_template('stock_detail.html', stock_code=stock_code)

@app.route('/api/stock/<stock_code>')
def get_stock_data(stock_code):
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
            # 如果已经包含后缀，直接使用
            ts_code = stock_code
        
        # 获取基本信息
        basic_info = pro.stock_basic(ts_code=ts_code)
        if basic_info.empty:
            return jsonify({'error': '股票代码不存在'}), 404
        
        # 获取最近90天的日K线数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')
        
        daily_data = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if daily_data.empty:
            return jsonify({'error': '无法获取股票数据'}), 404
        
        daily_data = daily_data.sort_values('trade_date').tail(90)
        
        # 获取最新的财务数据，尝试多个交易日
        daily_basic = pd.DataFrame()
        for i in range(10):  # 尝试最近10个交易日
            try:
                check_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                daily_basic = pro.daily_basic(ts_code=ts_code, trade_date=check_date)
                if not daily_basic.empty:
                    break
            except:
                continue
        
        # 计算九转序列
        daily_data = calculate_nine_turn(daily_data)
        
        # 确保所有数值字段不为None
        numeric_columns = ['open', 'high', 'low', 'close', 'vol', 'amount', 'nine_turn_up', 'nine_turn_down']
        for col in numeric_columns:
            if col in daily_data.columns:
                daily_data[col] = daily_data[col].fillna(0)
        
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
        
        # 获取资金流向数据（尝试两个接口）
        moneyflow_data = None
        try:
            # 优先尝试moneyflow_dc接口（需要5000积分，数据更详细）
            moneyflow_data = pro.moneyflow_dc(ts_code=ts_code, limit=1)
            if moneyflow_data.empty:
                # 如果moneyflow_dc没有数据，尝试moneyflow接口（需要2000积分）
                moneyflow_data = pro.moneyflow(ts_code=ts_code, limit=1)
        except Exception as e:
            print(f"获取资金流向数据失败: {e}")
            # 如果积分不足或其他错误，继续执行但不包含资金流向数据
            pass
        
        # 准备返回数据
        stock_info = {
            'ts_code': ts_code,
            'name': basic_info.iloc[0]['name'],
            'industry': basic_info.iloc[0]['industry'],
            'latest_price': safe_float(daily_data.iloc[-1]['close']),
            'market_cap': safe_float(daily_basic.iloc[0]['total_mv']) if not daily_basic.empty and 'total_mv' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['total_mv']) else 0,
            'turnover_rate': safe_float(daily_basic.iloc[0]['turnover_rate']) if not daily_basic.empty and 'turnover_rate' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['turnover_rate']) else 0,
            'pe_ttm': safe_float(daily_basic.iloc[0]['pe_ttm']) if not daily_basic.empty and 'pe_ttm' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['pe_ttm']) and daily_basic.iloc[0]['pe_ttm'] > 0 else None,
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
        per_page = 100  # 每页显示100行数据
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
            # 没有缓存，需要全量更新
            need_full_update = True
            print(f"首次获取{market}市场数据，进行全量更新")
        elif latest_cache_date < current_date:
            # 有缓存但不是最新，需要增量更新
            need_incremental_update = True
            days_diff = get_trading_days_between(latest_cache_date, current_date)
            print(f"{market}市场数据需要增量更新，距离上次更新{days_diff}天")
        else:
            print(f"{market}市场数据已是最新，使用缓存")
        
        if need_full_update:
            # 全量更新：获取股票列表
            if market == 'cyb':  # 创业板
                stocks = pro.stock_basic(market='创业板')
            elif market == 'hu':  # 沪A
                stocks = pro.stock_basic(market='主板', exchange='SSE')
            elif market == 'zxb':  # 中小板
                stocks = pro.stock_basic(market='中小板')
            elif market == 'kcb':  # 科创板
                # 科创板股票代码以688开头，需要单独获取
                stocks = pro.stock_basic(market='科创板', exchange='SSE')
                print(f"获取到{len(stocks)}只科创板股票")
            elif market == 'bj':  # 北交所
                stocks = pro.stock_basic(exchange='BSE')
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
                    'turnover_rate': 0,
                    'volume_ratio': 0,
                    'amount': 0,
                    'market_cap': 0,
                    'pe_ttm': 0,
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
            
        elif need_incremental_update:
            # 增量更新：只更新价格等实时数据
            all_stocks_data = cache_data['stocks']
            
            # 批量更新股票的最新数据
            for stock_info in all_stocks_data:
                try:
                    # 获取最新价格和基本面数据
                    latest_data = pro.daily(ts_code=stock_info['ts_code'], limit=1)
                    daily_basic = pro.daily_basic(ts_code=stock_info['ts_code'], limit=1)
                    
                    # 更新实时数据
                    stock_info['latest_price'] = safe_float(latest_data.iloc[0]['close']) if not latest_data.empty else stock_info.get('latest_price', 0)
                    stock_info['turnover_rate'] = safe_float(daily_basic.iloc[0]['turnover_rate']) if not daily_basic.empty and 'turnover_rate' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['turnover_rate']) else stock_info.get('turnover_rate', 0)
                    stock_info['volume_ratio'] = safe_float(daily_basic.iloc[0]['volume_ratio']) if not daily_basic.empty and 'volume_ratio' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['volume_ratio']) else stock_info.get('volume_ratio', 0)
                    stock_info['amount'] = safe_float(latest_data.iloc[0]['amount']) if not latest_data.empty else stock_info.get('amount', 0)
                    stock_info['market_cap'] = safe_float(daily_basic.iloc[0]['total_mv']) if not daily_basic.empty and 'total_mv' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['total_mv']) else stock_info.get('market_cap', 0)
                    stock_info['pe_ttm'] = safe_float(daily_basic.iloc[0]['pe_ttm']) if not daily_basic.empty and 'pe_ttm' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['pe_ttm']) else stock_info.get('pe_ttm', 0)
                    stock_info['last_update'] = current_date
                    
                except Exception as e:
                    print(f"增量更新股票{stock_info['ts_code']}数据失败: {e}")
                    # 更新失败时保持原有数据
                    stock_info['last_update'] = current_date
            
            # 更新缓存
            cache_data['last_update_date'] = current_date
            cache_data['stocks'] = all_stocks_data
            save_cache_data(market, cache_data)
            
        else:
            # 使用缓存数据
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
                'is_cached': not (need_full_update or need_incremental_update),
                'force_refreshed': force_refresh
            }
        })
    
    except Exception as e:
        print(f"获取{market}市场数据失败: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = find_available_port()
    if port:
        print(f"服务器启动在端口: {port}")
        app.run(debug=True, host='0.0.0.0', port=port)
    else:
        print("无法找到可用端口")