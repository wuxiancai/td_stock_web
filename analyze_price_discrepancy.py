#!/usr/bin/env python3
import requests
import json

def analyze_300304_price_discrepancy():
    """分析300304价格差异问题"""
    
    print("=== 300304 云意电气 价格差异分析 ===")
    
    # 根据用户截图，当前价格应该是38.55，涨跌幅应该是-1.54%
    expected_current_price = 38.55
    expected_change_percent = -1.54
    
    # 计算期望的前收盘价
    expected_pre_close = expected_current_price / (1 + expected_change_percent / 100)
    
    print(f"根据用户截图的期望数据:")
    print(f"当前价格: {expected_current_price}")
    print(f"涨跌幅: {expected_change_percent}%")
    print(f"计算出的前收盘价: {expected_pre_close:.2f}")
    print()
    
    try:
        # 获取API返回的实时数据
        response = requests.get('http://localhost:8080/api/stock/300304/realtime')
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                spot = data['data']['spot']
                api_current_price = spot['latest_price']
                api_pre_close = spot['pre_close']
                api_change_percent = spot['change_percent']
                
                print(f"API返回的数据:")
                print(f"当前价格: {api_current_price}")
                print(f"前收盘价: {api_pre_close}")
                print(f"涨跌幅: {api_change_percent:.2f}%")
                print()
                
                # 分析差异
                price_ratio = expected_current_price / api_current_price
                print(f"价格差异分析:")
                print(f"期望价格 / API价格 = {expected_current_price} / {api_current_price} = {price_ratio:.4f}")
                
                # 检查是否是复权问题
                if abs(price_ratio - 4.32) < 0.1:  # 大约4.32倍的差异
                    print("可能的问题：API返回的是复权后价格，而用户看到的是原始价格")
                    print("建议：检查复权因子的应用逻辑")
                elif abs(price_ratio - 1.0) < 0.1:
                    print("价格基本一致，可能是涨跌幅计算的前收盘价有问题")
                else:
                    print(f"价格差异较大，比例为 {price_ratio:.2f}，需要进一步调查数据源")
                
                print()
                print(f"如果API当前价格 {api_current_price} 是正确的:")
                print(f"要达到 {expected_change_percent}% 的涨跌幅，前收盘价应该是: {api_current_price / (1 + expected_change_percent / 100):.2f}")
                print(f"但API显示的前收盘价是: {api_pre_close}")
                
            else:
                print("API返回失败")
        else:
            print(f"请求失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"分析过程中出错: {e}")

if __name__ == "__main__":
    analyze_300304_price_discrepancy()