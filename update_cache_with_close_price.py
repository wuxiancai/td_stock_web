#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import tushare as ts
from datetime import datetime
import pandas as pd

def update_indices_cache_with_close_price():
    """更新指数缓存为正确的收盘价"""
    
    # 使用应用程序中的token
    tushare_token = '68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019'
    ts.set_token(tushare_token)
    pro = ts.pro_api()
    
    print("=== 更新指数缓存为收盘价 ===")
    
    # 定义指数映射
    indices_mapping = {
        'sh000001': {'ts_code': '000001.SH', 'name': '上证指数'},
        'sz399001': {'ts_code': '399001.SZ', 'name': '深证成指'},
        'sz399006': {'ts_code': '399006.SZ', 'name': '创业板指'},
        'sh000688': {'ts_code': '000688.SH', 'name': '科创板'}
    }
    
    # 获取2025年7月28日的收盘数据
    target_date = '20250728'
    updated_data = {}
    
    for code, info in indices_mapping.items():
        try:
            print(f"获取 {info['name']} ({info['ts_code']}) 的收盘数据...")
            
            # 获取指定日期的数据
            df = pro.index_daily(ts_code=info['ts_code'], trade_date=target_date)
            
            if not df.empty:
                row = df.iloc[0]
                close_price = row['close']
                change = row['change'] if pd.notna(row['change']) else 0
                pct_chg = row['pct_chg'] if pd.notna(row['pct_chg']) else 0
                vol = row['vol'] if pd.notna(row['vol']) else 0
                
                updated_data[code] = {
                    'name': info['name'],
                    'current_price': close_price,
                    'change_pct': round(pct_chg, 2),
                    'change_amount': round(change, 2),
                    'volume': round(vol / 100, 2),  # 转换为亿手
                    'update_time': '15:00:00'  # 收盘时间
                }
                
                print(f"  收盘价: {close_price:.2f}")
                print(f"  涨跌额: {change:.2f}")
                print(f"  涨跌幅: {pct_chg:.2f}%")
                
            else:
                print(f"  未找到 {target_date} 的数据")
                
        except Exception as e:
            print(f"  获取 {info['name']} 数据失败: {e}")
    
    if updated_data:
        # 更新缓存文件
        cache_file = os.path.join('cache', 'indices_cache.json')
        
        # 确保cache目录存在
        os.makedirs('cache', exist_ok=True)
        
        cache_data = {
            'data': updated_data,
            'fetch_time': '2025-07-28 15:00:00',
            'cache_date': '2025-07-28',
            'cache_time': '15:00:00'
        }
        
        # 备份原缓存文件
        if os.path.exists(cache_file):
            backup_file = cache_file + '.backup'
            with open(cache_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            print(f"原缓存文件已备份到: {backup_file}")
        
        # 写入新的缓存数据
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== 缓存更新完成 ===")
        print(f"缓存文件: {cache_file}")
        print(f"更新时间: {cache_data['fetch_time']}")
        
        # 显示更新后的数据
        print(f"\n=== 更新后的数据 ===")
        for code, data in updated_data.items():
            print(f"{data['name']}: {data['current_price']:.2f} ({data['change_amount']:+.2f}, {data['change_pct']:+.2f}%)")
        
        # 特别显示上证指数的变化
        if 'sh000001' in updated_data:
            old_price = 3589.27
            new_price = updated_data['sh000001']['current_price']
            difference = new_price - old_price
            print(f"\n=== 上证指数价格修正 ===")
            print(f"修正前: {old_price:.2f}")
            print(f"修正后: {new_price:.2f}")
            print(f"差异: {difference:+.2f} 点")
            
    else:
        print("未获取到任何数据，缓存未更新")

if __name__ == "__main__":
    update_indices_cache_with_close_price()