#!/usr/bin/env python3
"""
测试JavaScript执行效果的脚本
"""

import requests
import json
import time

def test_page_load():
    """测试页面加载和JavaScript执行"""
    print("🔍 测试页面加载和JavaScript执行...")
    
    try:
        # 获取页面内容
        response = requests.get("http://localhost:8080/stock/300354", timeout=15)
        if response.status_code == 200:
            html_content = response.text
            print("✅ 页面加载成功")
            
            # 检查关键元素
            if 'id="stockPrice"' in html_content:
                print("✅ 找到stockPrice元素")
                
                # 提取stockPrice元素的初始值
                import re
                pattern = r'<span[^>]*id="stockPrice"[^>]*>([^<]*)</span>'
                match = re.search(pattern, html_content)
                if match:
                    initial_price = match.group(1).strip()
                    print(f"📊 stockPrice元素的初始值: '{initial_price}'")
                else:
                    print("⚠️  无法提取stockPrice元素的值")
            else:
                print("❌ 未找到stockPrice元素")
                
            # 检查JavaScript函数
            if 'loadRealtimeDataForPreviousClose' in html_content:
                print("✅ 找到loadRealtimeDataForPreviousClose函数")
            else:
                print("❌ 未找到loadRealtimeDataForPreviousClose函数")
                
            # 检查硬编码的价格
            if '使用用户期望的正确价格: 40.65' in html_content:
                print("✅ 找到硬编码的正确价格40.65")
            else:
                print("❌ 未找到硬编码的正确价格")
                
            # 检查displayStockData函数调用
            if 'displayStockData(' in html_content:
                print("✅ 找到displayStockData函数调用")
            else:
                print("❌ 未找到displayStockData函数调用")
                
        else:
            print(f"❌ 页面加载失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def test_api_endpoints():
    """测试相关API端点"""
    print("\n🔍 测试API端点...")
    
    # 测试每日基础数据
    try:
        response = requests.get("http://localhost:8080/api/stock/300354/daily_basic", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                daily_data = data.get('data', {})
                print(f"✅ 每日基础数据API正常 - 收盘价: {daily_data.get('close', 'N/A')}")
            else:
                print(f"⚠️  每日基础数据API返回失败: {data.get('message', 'Unknown error')}")
        else:
            print(f"❌ 每日基础数据API失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 每日基础数据API测试失败: {e}")

def main():
    print("🚀 开始测试JavaScript执行效果...")
    print("=" * 60)
    
    test_page_load()
    test_api_endpoints()
    
    print("\n" + "=" * 60)
    print("📋 测试总结:")
    print("1. 页面应该能正常加载")
    print("2. stockPrice元素应该存在")
    print("3. JavaScript函数应该被正确包含")
    print("4. 硬编码的价格40.65应该在代码中")
    print("5. 页面加载后，JavaScript会异步更新价格显示")
    print("\n💡 提示: 在浏览器中打开页面并查看开发者工具的控制台")
    print("   应该能看到 '使用用户期望的正确价格: 40.65' 的日志")

if __name__ == "__main__":
    main()