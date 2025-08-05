#!/usr/bin/env python3
"""
调试API返回的净流入额数据
检查实际的数据单位和值
"""

import requests
import json

def debug_netinflow_data():
    """调试净流入额数据"""
    base_url = "http://127.0.0.1:5000"
    stock_code = "000858.SZ"
    
    print("=== 调试净流入额数据 ===")
    
    # 1. 测试资金流向API
    print(f"\n1. 资金流向API: /api/stock/{stock_code}/moneyflow")
    try:
        response = requests.get(f"{base_url}/api/stock/{stock_code}/moneyflow")
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                moneyflow_data = data['data'][0]
                net_mf_amount = moneyflow_data.get('net_mf_amount')
                print(f"   原始净流入额: {net_mf_amount}")
                print(f"   数据类型: {type(net_mf_amount)}")
                
                # 显示完整的moneyflow数据
                print(f"   完整数据: {json.dumps(moneyflow_data, indent=2, ensure_ascii=False)}")
                
                if net_mf_amount is not None:
                    # 测试不同的转换逻辑
                    print(f"\n   转换测试:")
                    print(f"   如果是千万元单位:")
                    if abs(net_mf_amount) >= 10:
                        formatted1 = f"{(net_mf_amount / 10):.3f}亿元"
                    else:
                        formatted1 = f"{(net_mf_amount * 1000):.0f}万元"
                    print(f"     当前逻辑: {formatted1}")
                    
                    print(f"   如果是万元单位:")
                    if abs(net_mf_amount) >= 100000:
                        formatted2 = f"{(net_mf_amount / 100000):.3f}亿元"
                    else:
                        formatted2 = f"{net_mf_amount:.0f}万元"
                    print(f"     万元逻辑: {formatted2}")
                    
                    print(f"   如果是元单位:")
                    if abs(net_mf_amount) >= 100000000:
                        formatted3 = f"{(net_mf_amount / 100000000):.3f}亿元"
                    elif abs(net_mf_amount) >= 10000:
                        formatted3 = f"{(net_mf_amount / 10000):.0f}万元"
                    else:
                        formatted3 = f"{net_mf_amount:.0f}元"
                    print(f"     元逻辑: {formatted3}")
                    
                    print(f"   如果直接是亿元单位:")
                    formatted4 = f"{net_mf_amount:.3f}亿元"
                    print(f"     亿元逻辑: {formatted4}")
                    
            else:
                print(f"   API返回失败: {data}")
        else:
            print(f"   API请求失败: {response.status_code}")
    except Exception as e:
        print(f"   API请求异常: {e}")
    
    # 2. 测试红3-6筛选API
    print(f"\n2. 红3-6筛选API: /api/filter/red_3_6")
    try:
        response = requests.get(f"{base_url}/api/filter/red_3_6")
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                # 查找测试股票
                stock_data = None
                for item in data['data']:
                    if item.get('ts_code') == stock_code:
                        stock_data = item
                        break
                
                if stock_data:
                    net_mf_amount = stock_data.get('net_mf_amount')
                    print(f"   原始净流入额: {net_mf_amount}")
                    print(f"   数据类型: {type(net_mf_amount)}")
                    
                    if net_mf_amount is not None:
                        # 红3-6页面的转换逻辑
                        if abs(net_mf_amount) >= 10:
                            formatted = f"{(net_mf_amount / 10):.3f}亿"
                        else:
                            formatted = f"{(net_mf_amount * 1000):.0f}万"
                        print(f"   红3-6页面格式化: {formatted}")
                else:
                    print(f"   未找到股票 {stock_code} 的数据")
            else:
                print(f"   API返回失败: {data}")
        else:
            print(f"   API请求失败: {response.status_code}")
    except Exception as e:
        print(f"   API请求异常: {e}")

def main():
    print("净流入额数据单位调试")
    print("=" * 50)
    
    debug_netinflow_data()
    
    print("\n=== 分析 ===")
    print("根据你说应该显示 '9.214 亿'，而当前显示 '9214.191亿元'")
    print("这说明:")
    print("1. 如果API返回的是 92.14191，那么数据单位应该是千万元，当前逻辑正确")
    print("2. 如果API返回的是 9214.191，那么数据单位可能是万元")
    print("3. 如果API返回的是 9.214191，那么数据单位已经是亿元")
    print("需要检查实际的API返回值来确定正确的转换逻辑")

if __name__ == "__main__":
    main()