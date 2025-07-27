#!/usr/bin/env python3
"""
测试浮点精度修复效果
"""

import requests
import json

def test_precision_fix():
    """测试精度修复效果"""
    print("=== 测试浮点精度修复效果 ===\n")
    
    # 测试实时数据API
    print("1. 测试实时数据API...")
    try:
        response = requests.get('http://127.0.0.1:8080/api/stock/000054/realtime')
        if response.status_code == 200:
            data = response.json()
            spot = data.get('spot', {})
            
            print(f"   实时价格: {spot.get('latest_price')}")
            print(f"   开盘价: {spot.get('open')}")
            print(f"   涨跌额: {spot.get('change_amount')}")
            print(f"   最高价: {spot.get('high')}")
            print(f"   最低价: {spot.get('low')}")
            print(f"   昨收价: {spot.get('pre_close')}")
            
            # 检查是否还有包含"999"的值
            has_999 = False
            for key, value in spot.items():
                if value is not None and str(value).find('999') != -1:
                    print(f"   ⚠️  发现包含'999'的值: {key} = {value}")
                    has_999 = True
            
            if not has_999:
                print("   ✅ 实时数据中没有发现包含'999'的值")
        else:
            print(f"   ❌ API请求失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
    
    print()
    
    # 测试股票详情API
    print("2. 测试股票详情API...")
    try:
        response = requests.get('http://127.0.0.1:8080/api/stock/000054')
        if response.status_code == 200:
            data = response.json()
            kline_data = data.get('kline_data', [])
            
            if kline_data:
                # 检查最近几条K线数据
                recent_data = kline_data[-5:]  # 最近5条
                print(f"   检查最近{len(recent_data)}条K线数据...")
                
                has_999 = False
                for i, item in enumerate(recent_data):
                    # 检查BOLL指标
                    boll_fields = ['boll_upper', 'boll_mid', 'boll_lower']
                    for field in boll_fields:
                        value = item.get(field)
                        if value is not None and str(value).find('999') != -1:
                            print(f"   ⚠️  发现包含'999'的值: 第{i+1}条数据 {field} = {value}")
                            has_999 = True
                    
                    # 检查MACD指标
                    macd_fields = ['macd_dif', 'macd_dea', 'macd_histogram']
                    for field in macd_fields:
                        value = item.get(field)
                        if value is not None and str(value).find('999') != -1:
                            print(f"   ⚠️  发现包含'999'的值: 第{i+1}条数据 {field} = {value}")
                            has_999 = True
                    
                    # 检查KDJ指标
                    kdj_fields = ['kdj_k', 'kdj_d', 'kdj_j']
                    for field in kdj_fields:
                        value = item.get(field)
                        if value is not None and str(value).find('999') != -1:
                            print(f"   ⚠️  发现包含'999'的值: 第{i+1}条数据 {field} = {value}")
                            has_999 = True
                    
                    # 检查RSI指标
                    rsi_value = item.get('rsi')
                    if rsi_value is not None and str(rsi_value).find('999') != -1:
                        print(f"   ⚠️  发现包含'999'的值: 第{i+1}条数据 rsi = {rsi_value}")
                        has_999 = True
                
                if not has_999:
                    print("   ✅ K线数据中没有发现包含'999'的值")
                    
                # 显示最新一条数据的技术指标
                latest = recent_data[-1]
                print(f"\n   最新数据技术指标:")
                print(f"   BOLL上轨: {latest.get('boll_upper')}")
                print(f"   BOLL中轨: {latest.get('boll_mid')}")
                print(f"   BOLL下轨: {latest.get('boll_lower')}")
                print(f"   MACD DIF: {latest.get('macd_dif')}")
                print(f"   MACD DEA: {latest.get('macd_dea')}")
                print(f"   KDJ K: {latest.get('kdj_k')}")
                print(f"   KDJ D: {latest.get('kdj_d')}")
                print(f"   KDJ J: {latest.get('kdj_j')}")
                print(f"   RSI: {latest.get('rsi')}")
            else:
                print("   ❌ 没有获取到K线数据")
        else:
            print(f"   ❌ API请求失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_precision_fix()