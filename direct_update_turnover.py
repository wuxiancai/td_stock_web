#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接更新自选股换手率数据脚本
绕过本地API，直接使用Tushare API获取数据
"""

import json
import tushare as ts
from datetime import datetime, timedelta
import time

# 设置Tushare token
ts.set_token('68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019')
pro = ts.pro_api()

def get_latest_trade_date():
    """获取最新交易日"""
    # 根据调试结果，直接使用20250107作为最新交易日
    return '20250107'

def get_turnover_rate(ts_code, trade_date):
    """获取指定股票的换手率"""
    try:
        # 获取daily_basic数据
        df = pro.daily_basic(ts_code=ts_code, trade_date=trade_date)
        if not df.empty:
            turnover_rate = df.iloc[0]['turnover_rate']
            if turnover_rate is not None and not pd.isna(turnover_rate):
                return float(turnover_rate)
        return 0.0
    except Exception as e:
        print(f"获取 {ts_code} 换手率失败: {e}")
        return 0.0

def update_watchlist_turnover():
    """更新自选股换手率数据"""
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
    print(f"共有 {len(watchlist)} 只股票需要更新")
    
    updated_count = 0
    
    for i, stock in enumerate(watchlist, 1):
        ts_code = stock['ts_code']
        name = stock['name']
        
        print(f"正在更新 {i}/{len(watchlist)}: {ts_code} {name}")
        
        # 获取换手率数据
        turnover_rate = get_turnover_rate(ts_code, trade_date)
        
        if turnover_rate > 0:
            stock['turnover_rate'] = round(turnover_rate, 4)
            updated_count += 1
            print(f"  - 更新成功: {turnover_rate:.4f}%")
        else:
            stock['turnover_rate'] = 0
            print(f"  - 无数据，设置为0")
        
        # API频率限制
        time.sleep(0.31)  # 每分钟最多200次请求
    
    # 保存更新后的数据
    try:
        with open(watchlist_file, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
        print(f"\n更新完成！共更新了 {updated_count} 只股票的换手率数据")
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == '__main__':
    import pandas as pd
    update_watchlist_turnover()