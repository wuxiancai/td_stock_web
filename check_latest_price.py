#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def check_latest_price():
    """检查latest_price字段的值"""
    try:
        # 获取股票详情数据
        response = requests.get('http://127.0.0.1:8080/api/stock/300354')
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
        
        data = response.json()
        
        print(f"股票代码: {data.get('ts_code', 'N/A')}")
        print(f"股票名称: {data.get('name', 'N/A')}")
        print("=" * 50)
        
        # 检查latest_price
        latest_price = data.get('latest_price')
        print(f"latest_price: {latest_price}")
        print(f"latest_price类型: {type(latest_price)}")
        
        # 检查是否包含999
        if latest_price and '999' in str(latest_price):
            print(f"⚠️  latest_price包含999: {latest_price}")
        
        # 检查最新K线数据的收盘价
        kline_data = data.get('kline_data', [])
        if kline_data:
            latest_kline = kline_data[-1]  # 最后一条K线数据
            print(f"\n最新K线数据 ({latest_kline.get('trade_date')}):")
            print(f"  开盘价: {latest_kline.get('open')}")
            print(f"  收盘价: {latest_kline.get('close')}")
            print(f"  最高价: {latest_kline.get('high')}")
            print(f"  最低价: {latest_kline.get('low')}")
            
            # 比较latest_price和最新K线的收盘价
            latest_close = latest_kline.get('close')
            if latest_price != latest_close:
                print(f"\n⚠️  数据不一致:")
                print(f"  latest_price: {latest_price}")
                print(f"  最新K线收盘价: {latest_close}")
            else:
                print(f"\n✅ latest_price与最新K线收盘价一致: {latest_price}")
        
        # 检查其他可能包含999的字段
        print(f"\n检查其他字段是否包含999:")
        for key, value in data.items():
            if key != 'kline_data' and isinstance(value, (int, float, str)) and '999' in str(value):
                print(f"  {key}: {value}")
                
    except Exception as e:
        print(f"检查失败: {e}")

if __name__ == "__main__":
    check_latest_price()