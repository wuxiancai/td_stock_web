#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def check_20250725_data():
    """检查20250725这一天的具体数据"""
    try:
        # 获取股票数据
        response = requests.get('http://127.0.0.1:8080/api/stock/300354')
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
        
        data = response.json()
        kline_data = data.get('kline_data', [])
        
        print(f"股票代码: {data.get('ts_code', 'N/A')}")
        print(f"股票名称: {data.get('name', 'N/A')}")
        print(f"总共K线数据条数: {len(kline_data)}")
        print("=" * 60)
        
        # 查找20250725的数据
        target_date = '20250725'
        found_data = None
        
        for i, kline in enumerate(kline_data):
            if kline.get('trade_date') == target_date:
                found_data = kline
                print(f"找到{target_date}的数据 (第{i+1}条):")
                print(json.dumps(kline, indent=2, ensure_ascii=False))
                break
        
        if not found_data:
            print(f"❌ 未找到{target_date}的数据")
            # 显示最近几天的数据作为参考
            print("\n最近5天的数据:")
            for kline in kline_data[-5:]:
                date = kline.get('trade_date', 'N/A')
                open_price = kline.get('open', 'N/A')
                close_price = kline.get('close', 'N/A')
                print(f"  {date}: 开盘={open_price}, 收盘={close_price}")
        else:
            print(f"\n✅ 找到{target_date}的数据")
            print(f"开盘价: {found_data.get('open', 'N/A')}")
            print(f"收盘价: {found_data.get('close', 'N/A')}")
            print(f"最高价: {found_data.get('high', 'N/A')}")
            print(f"最低价: {found_data.get('low', 'N/A')}")
            
            # 检查是否有999值
            for key, value in found_data.items():
                if isinstance(value, (int, float, str)) and '999' in str(value):
                    print(f"⚠️  发现包含999的字段: {key} = {value}")
            
    except Exception as e:
        print(f"检查失败: {e}")

if __name__ == "__main__":
    check_20250725_data()