#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def simulate_frontend_display():
    """模拟前端显示逻辑"""
    try:
        # 获取实时数据
        response = requests.get('http://127.0.0.1:8080/api/stock/300354/realtime')
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
        
        data = response.json()
        
        print("模拟前端显示逻辑:")
        print("=" * 50)
        
        # 模拟displayRealtimeData函数的逻辑
        if 'spot' in data and data['spot']:
            spot = data['spot']
            
            # 模拟第1172行: document.getElementById('realtimePrice').textContent = '¥' + (quote.latest_price || '-');
            latest_price = spot.get('latest_price')
            realtime_price_display = f"¥{latest_price}" if latest_price else "¥-"
            print(f"realtimePrice显示: {realtime_price_display}")
            
            # 模拟第1179行: document.getElementById('openPrice').textContent = '¥' + quote.open.toFixed(2);
            open_price = spot.get('open')
            if open_price and open_price > 0:
                open_price_display = f"¥{open_price:.2f}"
                print(f"openPrice显示: {open_price_display}")
            else:
                print(f"openPrice显示: -")
            
            # 检查所有可能显示为999的字段
            print(f"\n所有spot字段:")
            for key, value in spot.items():
                if isinstance(value, (int, float)):
                    formatted_value = f"¥{value:.2f}"
                    print(f"  {key}: {value} -> {formatted_value}")
                    if '999' in formatted_value:
                        print(f"    ⚠️  格式化后包含999!")
                else:
                    print(f"  {key}: {value}")
        else:
            print("无spot数据")
                    
    except Exception as e:
        print(f"模拟失败: {e}")

if __name__ == "__main__":
    simulate_frontend_display()