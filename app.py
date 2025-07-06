import tushare as ts
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import socket

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

@app.route('/api/stocks/<market>')
def get_stocks_by_market(market):
    try:
        page = int(request.args.get('page', 1))
        per_page = 50
        
        # 根据市场获取股票列表
        if market == 'cyb':  # 创业板
            stocks = pro.stock_basic(market='创业板')
        elif market == 'hu':  # 沪A
            stocks = pro.stock_basic(market='主板', exchange='SSE')
        elif market == 'zxb':  # 中小板
            stocks = pro.stock_basic(market='中小板')
        elif market == 'bj':  # 北交所
            stocks = pro.stock_basic(exchange='BSE')
        else:
            return jsonify({'error': '无效的市场类型'}), 400
        
        if stocks.empty:
            return jsonify({'stocks': [], 'total': 0, 'pages': 0})
        
        # 分页
        total = len(stocks)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_stocks = stocks.iloc[start_idx:end_idx]
        
        # 安全获取数值的辅助函数
        def safe_float(value, default=0.0):
            try:
                if value is None or pd.isna(value):
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # 获取每只股票的最新数据
        stock_list = []
        for _, stock in page_stocks.iterrows():
            try:
                # 获取最新价格
                latest_data = pro.daily(ts_code=stock['ts_code'], limit=1)
                daily_basic = pro.daily_basic(ts_code=stock['ts_code'], limit=1)
                
                stock_info = {
                    'ts_code': stock['ts_code'],
                    'name': stock['name'],
                    'industry': stock['industry'],
                    'latest_price': safe_float(latest_data.iloc[0]['close']) if not latest_data.empty else 0,
                    'turnover_rate': safe_float(daily_basic.iloc[0]['turnover_rate']) if not daily_basic.empty and 'turnover_rate' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['turnover_rate']) else 0,
                    'volume_ratio': safe_float(daily_basic.iloc[0]['volume_ratio']) if not daily_basic.empty and 'volume_ratio' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['volume_ratio']) else 0,
                    'amount': safe_float(latest_data.iloc[0]['amount']) if not latest_data.empty else 0,
                    'market_cap': safe_float(daily_basic.iloc[0]['total_mv']) if not daily_basic.empty and 'total_mv' in daily_basic.columns and not pd.isna(daily_basic.iloc[0]['total_mv']) else 0
                }
                stock_list.append(stock_info)
            except:
                # 如果获取数据失败，只返回基本信息
                stock_info = {
                    'ts_code': stock['ts_code'],
                    'name': stock['name'],
                    'industry': stock['industry'],
                    'latest_price': 0,
                    'turnover_rate': 0,
                    'volume_ratio': 0,
                    'amount': 0,
                    'market_cap': 0
                }
                stock_list.append(stock_info)
        
        return jsonify({
            'stocks': stock_list,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'current_page': page
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = find_available_port()
    if port:
        print(f"服务器启动在端口: {port}")
        app.run(debug=True, host='0.0.0.0', port=port)
    else:
        print("无法找到可用端口")