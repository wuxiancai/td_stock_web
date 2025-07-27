#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import pandas as pd
import numpy as np

def check_backend_data_processing():
    """检查后端数据处理中可能导致999显示的问题"""
    try:
        print("=== 检查后端数据处理中的999问题 ===")
        
        # 1. 检查实时数据API
        print("\n1. 检查实时数据API返回值:")
        response = requests.get('http://127.0.0.1:8080/api/stock/300354/realtime')
        if response.status_code == 200:
            data = response.json()
            spot = data.get('spot', {})
            
            print(f"latest_price: {spot.get('latest_price')} (类型: {type(spot.get('latest_price'))})")
            print(f"open: {spot.get('open')} (类型: {type(spot.get('open'))})")
            print(f"change_amount: {spot.get('change_amount')} (类型: {type(spot.get('change_amount'))})")
            
            # 检查是否有包含999的字段
            for key, value in spot.items():
                if isinstance(value, (int, float)):
                    str_value = str(value)
                    if '999' in str_value:
                        print(f"⚠️  发现包含999的字段: {key} = {value}")
                        print(f"   字符串表示: '{str_value}'")
                        print(f"   科学计数法: {value:e}")
                        
                        # 检查浮点数精度问题
                        if isinstance(value, float):
                            print(f"   精确值: {value:.20f}")
                            print(f"   toFixed(2)模拟: {value:.2f}")
        
        # 2. 检查股票详情API
        print("\n2. 检查股票详情API返回值:")
        response = requests.get('http://127.0.0.1:8080/api/stock/300354')
        if response.status_code == 200:
            data = response.json()
            
            print(f"latest_price: {data.get('latest_price')} (类型: {type(data.get('latest_price'))})")
            
            # 检查K线数据中的999
            kline_data = data.get('kline_data', [])
            if kline_data:
                latest_kline = kline_data[-1]
                print(f"最新K线数据:")
                for key, value in latest_kline.items():
                    if isinstance(value, (int, float)) and value is not None:
                        str_value = str(value)
                        if '999' in str_value:
                            print(f"⚠️  K线数据包含999: {key} = {value}")
                            print(f"   字符串表示: '{str_value}'")
                            if isinstance(value, float):
                                print(f"   精确值: {value:.20f}")
        
        # 3. 模拟浮点数精度问题
        print("\n3. 模拟浮点数精度问题:")
        test_values = [
            41.01 - 40.31,  # 模拟开盘价减去最新价
            -1.26,  # 模拟变动金额
            -1.259999999999998,  # 实际观察到的值
        ]
        
        for i, value in enumerate(test_values):
            print(f"测试值{i+1}: {value}")
            print(f"  精确表示: {value:.20f}")
            print(f"  字符串表示: '{str(value)}'")
            print(f"  包含999: {'999' in str(value)}")
            print(f"  toFixed(2): {value:.2f}")
            print()
        
        # 4. 检查NaN和无穷大值
        print("4. 检查特殊数值:")
        special_values = [np.nan, np.inf, -np.inf, 999, 999.0, 999.99]
        for value in special_values:
            print(f"值: {value}, 字符串: '{str(value)}', 包含999: {'999' in str(value)}")
        
        # 5. 检查JSON序列化后的值
        print("\n5. 检查JSON序列化:")
        test_data = {
            'change_amount': -1.259999999999998,
            'latest_price': 40.31,
            'open': 41.01
        }
        
        json_str = json.dumps(test_data)
        print(f"JSON序列化结果: {json_str}")
        print(f"JSON中包含999: {'999' in json_str}")
        
        # 解析回来检查
        parsed_data = json.loads(json_str)
        for key, value in parsed_data.items():
            if isinstance(value, (int, float)):
                str_value = str(value)
                if '999' in str_value:
                    print(f"⚠️  JSON解析后包含999: {key} = {value}")
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_backend_data_processing()