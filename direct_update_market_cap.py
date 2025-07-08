#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接更新自选股市值数据脚本
绕过本地API，直接使用Tushare API获取数据
"""

import json
import tushare as ts
from datetime import datetime, timedelta
import time
import pandas as pd

# 设置Tushare token
ts.set_token('68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019')
pro = ts.pro_api()

def get_latest_trade_date():
    """获取最新交易日"""
    # 根据调试结果，直接使用20250107作为最新交易日
    return '20250107'

def get_market_cap_data(ts_code, trade_date):
    """获取指定股票的市值数据"""
    try:
        # 获取daily_basic数据
        df = pro.daily_basic(ts_code=ts_code, trade_date=trade_date)
        if not df.empty:
            total_mv = df.iloc[0]['total_mv']  # 总市值（万元）
            circ_mv = df.iloc[0]['circ_mv']    # 流通市值（万元）
            
            result = {}
            
            # 总市值数据处理（转换为亿元）
            if total_mv is not None and not pd.isna(total_mv) and total_mv > 0:
                result['total_mv'] = float(total_mv) / 10000  # 万元转亿元
            else:
                result['total_mv'] = 0
            
            # 流通市值数据处理（转换为亿元）
            if circ_mv is not None and not pd.isna(circ_mv) and circ_mv > 0:
                result['circ_mv'] = float(circ_mv) / 10000  # 万元转亿元
            else:
                result['circ_mv'] = 0
                
            return result
        return {'total_mv': 0, 'circ_mv': 0}
    except Exception as e:
        print(f"获取 {ts_code} 市值数据失败: {e}")
        return {'total_mv': 0, 'circ_mv': 0}

def update_watchlist_market_cap():
    """更新自选股市值数据"""
    watchlist_file = '/Users/wuxiancai/td_stock_web/cache/watchlist.json'
    
    # 读取自选股数据
    try:
        with open(watchlist_file, 'r', encoding='utf-8') as f:
            watchlist = json.load(f)
    except Exception as e:
        print(f"读取自选股文件失败: {e}")
        return
    
    # 获取最新交易日
    trade_date = get_latest_trade_date()
    if not trade_date:
        print("无法获取最新交易日")
        return
    
    print(f"使用交易日: {trade_date}")
    print(f"共有 {len(watchlist)} 只股票需要更新市值数据")
    
    updated_count = 0
    
    for i, stock in enumerate(watchlist, 1):
        ts_code = stock['ts_code']
        name = stock['name']
        
        print(f"正在更新 {i}/{len(watchlist)}: {ts_code} {name}")
        
        # 获取市值数据
        market_cap_data = get_market_cap_data(ts_code, trade_date)
        
        # 更新市值数据
        old_total_mv = stock.get('total_mv', 0)
        stock['total_mv'] = market_cap_data['total_mv']
        
        # 添加流通市值数据（如果不存在）
        if 'circ_mv' not in stock:
            stock['circ_mv'] = market_cap_data['circ_mv']
        
        if market_cap_data['total_mv'] > 0:
            updated_count += 1
            print(f"  - 总市值更新成功: {old_total_mv:.2f} -> {market_cap_data['total_mv']:.2f}亿元")
            if market_cap_data['circ_mv'] > 0:
                print(f"  - 流通市值: {market_cap_data['circ_mv']:.2f}亿元")
        else:
            print(f"  - 市值无数据，设置为0")
        
        # API频率限制
        time.sleep(0.31)  # 每分钟最多200次请求
    
    # 保存更新后的数据
    try:
        with open(watchlist_file, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
        print(f"\n更新完成！共更新了 {updated_count} 只股票的市值数据")
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == '__main__':
    update_watchlist_market_cap()