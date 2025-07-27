#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def check_realtime_data():
    """检查实时数据接口返回的数据"""
    try:
        # 获取实时数据
        response = requests.get('http://127.0.0.1:8080/api/stock/300354/realtime')
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
        
        data = response.json()
        
        print("实时数据接口返回:")
        print("=" * 50)
        
        # 检查spot数据
        if 'spot' in data and data['spot']:
            spot = data['spot']
            print("Spot数据:")
            for key, value in spot.items():
                print(f"  {key}: {value}")
                if isinstance(value, (int, float, str)) and '999' in str(value):
                    print(f"    ⚠️  包含999: {key} = {value}")
        else:
            print("无spot数据")
        
        # 检查其他字段
        print(f"\n其他字段:")
        for key, value in data.items():
            if key != 'spot' and key != 'kline_data' and key != 'minute_data':
                print(f"  {key}: {value}")
                if isinstance(value, (int, float, str)) and '999' in str(value):
                    print(f"    ⚠️  包含999: {key} = {value}")
                    
    except Exception as e:
        print(f"检查失败: {e}")

if __name__ == "__main__":
    check_realtime_data()