#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def check_realtime_latest_price():
    """专门检查实时数据中的latest_price字段"""
    try:
        # 获取实时数据
        response = requests.get('http://127.0.0.1:8080/api/stock/300354/realtime')
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
        
        data = response.json()
        
        print("实时数据接口返回:")
        print("=" * 50)
        
        # 检查spot数据中的latest_price
        if 'spot' in data and data['spot']:
            spot = data['spot']
            latest_price = spot.get('latest_price')
            print(f"spot.latest_price: {latest_price}")
            print(f"类型: {type(latest_price)}")
            print(f"字符串表示: '{str(latest_price)}'")
            
            # 检查是否包含999
            if latest_price and '999' in str(latest_price):
                print(f"⚠️  latest_price包含999!")
                print(f"  原始值: {latest_price}")
                print(f"  字符串: '{str(latest_price)}'")
                print(f"  使用toFixed(2): {latest_price:.2f}")
            else:
                print(f"✅ latest_price不包含999")
                print(f"  使用toFixed(2): {latest_price:.2f}")
                
            # 检查其他可能的价格字段
            price_fields = ['open', 'high', 'low', 'pre_close', 'change_amount']
            for field in price_fields:
                value = spot.get(field)
                if value and '999' in str(value):
                    print(f"⚠️  {field}包含999: {value}")
        else:
            print("无spot数据")
                    
    except Exception as e:
        print(f"检查失败: {e}")

if __name__ == "__main__":
    check_realtime_latest_price()