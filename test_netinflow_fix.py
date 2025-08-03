#!/usr/bin/env python3
"""
测试净流入额显示修复
验证股票详情页面和红3-6筛选页面的净流入额显示是否一致
"""

import requests
import json

def test_netinflow_apis():
    """测试净流入额相关的API"""
    base_url = "http://127.0.0.1:5000"
    stock_code = "000858.SZ"
    
    print("=== 测试净流入额API ===")
    
    # 1. 测试资金流向API
    print(f"\n1. 测试资金流向API: /api/stock/{stock_code}/moneyflow")
    try:
        response = requests.get(f"{base_url}/api/stock/{stock_code}/moneyflow")
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                net_mf_amount = data['data'][0].get('net_mf_amount')
                print(f"   净流入额 (千万元): {net_mf_amount}")
                
                # 模拟前端格式化函数
                if net_mf_amount is not None:
                    if abs(net_mf_amount) >= 10:
                        formatted = f"{(net_mf_amount / 10):.3f}亿元"
                    else:
                        formatted = f"{(net_mf_amount * 1000):.0f}万元"
                    print(f"   格式化后显示: {formatted}")
                else:
                    print("   净流入额为空")
            else:
                print(f"   API返回失败: {data}")
        else:
            print(f"   API请求失败: {response.status_code}")
    except Exception as e:
        print(f"   API请求异常: {e}")
    
    # 2. 测试实时交易数据API
    print(f"\n2. 测试实时交易数据API: /api/stock/realtime_trading_data")
    try:
        response = requests.get(f"{base_url}/api/stock/realtime_trading_data")
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                # 查找当前股票的数据
                stock_data = None
                for item in data['data']:
                    if item.get('代码') == stock_code or item.get('代码') == stock_code[:6]:
                        stock_data = item
                        break
                
                if stock_data:
                    net_mf_amount = stock_data.get('net_mf_amount')
                    print(f"   净流入额: {net_mf_amount}")
                    if net_mf_amount is None:
                        print("   ✓ 确认实时交易数据API不包含净流入额字段")
                else:
                    print(f"   未找到股票 {stock_code} 的数据")
            else:
                print(f"   API返回失败: {data}")
        else:
            print(f"   API请求失败: {response.status_code}")
    except Exception as e:
        print(f"   API请求异常: {e}")
    
    # 3. 测试红3-6筛选API
    print(f"\n3. 测试红3-6筛选API: /api/filter/red_3_6")
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
                    print(f"   净流入额 (千万元): {net_mf_amount}")
                    
                    # 模拟前端格式化函数
                    if net_mf_amount is not None:
                        if abs(net_mf_amount) >= 10:
                            formatted = f"{(net_mf_amount / 10):.3f}亿"
                        else:
                            formatted = f"{(net_mf_amount * 1000):.0f}万"
                        print(f"   格式化后显示: {formatted}")
                    else:
                        print("   净流入额为空")
                else:
                    print(f"   未找到股票 {stock_code} 的数据")
            else:
                print(f"   API返回失败: {data}")
        else:
            print(f"   API请求失败: {response.status_code}")
    except Exception as e:
        print(f"   API请求异常: {e}")

def main():
    print("净流入额显示修复测试")
    print("=" * 50)
    
    test_netinflow_apis()
    
    print("\n=== 总结 ===")
    print("修复内容:")
    print("1. 股票详情页面的页面顶部净流入额现在使用资金流向API数据")
    print("2. 移除了对实时交易数据API中不存在的净流入额字段的错误引用")
    print("3. 确保两个页面使用相同的数据源和格式化逻辑")
    print("\n预期结果:")
    print("- 红3-6筛选页面: 使用formatNetMfAmount函数，显示'亿'或'万'")
    print("- 股票详情页面: 使用formatMoneyflowValue函数，显示'亿元'或'万元'")
    print("- 两个页面的数值应该一致，只是单位显示略有不同")

if __name__ == "__main__":
    main()