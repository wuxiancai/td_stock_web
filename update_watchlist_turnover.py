#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新自选股数据，为现有股票添加换手率字段
"""

import json
import os
import sys
import requests
from datetime import datetime

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
    except Exception as e:
        print(f"保存失败: {e}")
        return False

def get_stock_data(ts_code):
    """从本地API获取股票数据"""
    try:
        response = requests.get(f'http://localhost:8080/api/stock/{ts_code}', timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                return data
    except Exception as e:
        print(f"获取股票 {ts_code} 数据失败: {e}")
    return None

def update_watchlist_turnover():
    """更新自选股换手率数据"""
    print("开始更新自选股换手率数据...")
    
    # 加载现有自选股数据
    watchlist_data = load_watchlist()
    if not watchlist_data:
        print("没有找到自选股数据")
        return
    
    print(f"找到 {len(watchlist_data)} 只自选股")
    
    updated_count = 0
    for i, stock in enumerate(watchlist_data):
        ts_code = stock.get('ts_code')
        if not ts_code:
            continue
            
        print(f"正在更新 {i+1}/{len(watchlist_data)}: {ts_code} {stock.get('name', '')}")
        
        # 强制更新所有股票的换手率数据
        if 'turnover_rate' in stock and stock['turnover_rate'] is not None and stock['turnover_rate'] > 0:
            print(f"  - 当前换手率数据: {stock['turnover_rate']:.2f}%，强制更新...")
        else:
            print(f"  - 当前换手率数据: {stock.get('turnover_rate', 0):.2f}%，需要更新...")
        
        # 获取最新股票数据
        stock_data = get_stock_data(ts_code)
        if stock_data and 'turnover_rate' in stock_data:
            stock['turnover_rate'] = stock_data['turnover_rate']
            updated_count += 1
            print(f"  - 更新换手率: {stock_data['turnover_rate']:.2f}%")
        else:
            # 如果获取失败，设置为0
            stock['turnover_rate'] = 0
            print(f"  - 获取数据失败，设置为0")
    
    # 保存更新后的数据
    if save_watchlist(watchlist_data):
        print(f"\n更新完成！共更新了 {updated_count} 只股票的换手率数据")
    else:
        print("\n保存失败！")

if __name__ == '__main__':
    update_watchlist_turnover()