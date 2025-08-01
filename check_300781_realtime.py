#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def check_stock_300781():
    """检查300781股票的实时数据"""
    try:
        # 获取实时交易数据
        response = requests.get("http://localhost:8080/api/stock/realtime_trading_data")
        data = response.json()
        
        print(f"数据源: {data.get('data_source', 'Unknown')}")
        print(f"获取时间: {data.get('fetch_time', 'Unknown')}")
        print(f"是否缓存数据: {data.get('is_cached_data', False)}")
        print(f"总记录数: {data.get('total_records', 0)}")
        print(f"消息: {data.get('message', '')}")
        print("-" * 50)
        
        # 查找300781
        stocks = data.get('data', [])
        found_300781 = None
        
        for stock in stocks:
            if stock.get('代码') == '300781':
                found_300781 = stock
                break
        
        if found_300781:
            print("找到300781股票数据:")
            print(f"  股票代码: {found_300781.get('代码')}")
            print(f"  股票名称: {found_300781.get('名称')}")
            print(f"  最新价: {found_300781.get('最新价')}")
            print(f"  今开: {found_300781.get('今开')}")
            print(f"  昨收: {found_300781.get('昨收')}")
            print(f"  最高: {found_300781.get('最高')}")
            print(f"  最低: {found_300781.get('最低')}")
            print(f"  涨跌幅: {found_300781.get('涨跌幅')}%")
            print(f"  涨跌额: {found_300781.get('涨跌额')}")
            print(f"  成交量: {found_300781.get('成交量')}")
            print(f"  成交额: {found_300781.get('成交额')}")
            print(f"  换手率: {found_300781.get('换手率')}%")
            print(f"  量比: {found_300781.get('量比')}")
        else:
            print("未找到300781股票数据")
            print("让我检查前几条数据的格式:")
            for i, stock in enumerate(stocks[:3]):
                print(f"  股票{i+1}: 代码={stock.get('代码')}, 名称={stock.get('名称')}, 最新价={stock.get('最新价')}")
        
    except Exception as e:
        print(f"获取数据失败: {e}")

if __name__ == "__main__":
    check_stock_300781()