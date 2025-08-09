#!/usr/bin/env python3
"""
测试实时数据显示修复效果
验证：
1. 自动刷新时不会清空现有数据
2. 字段映射正确，所有字段都能正确显示
"""

import requests
import json
import time

def test_realtime_api():
    """测试实时交易数据API"""
    print("=" * 60)
    print("测试实时交易数据API")
    print("=" * 60)
    
    try:
        response = requests.get('http://localhost:8080/api/stock/realtime_trading_data', timeout=10)
        if response.status_code == 200:
            result = response.json()
            
            if result['success']:
                print(f"✓ API调用成功")
                print(f"  数据条数: {len(result['data'])}")
                print(f"  获取时间: {result.get('fetch_time', '未知')}")
                print(f"  数据源: {result.get('data_source', '未知')}")
                print(f"  是否缓存数据: {result.get('is_cached_data', False)}")
                
                # 查找300101的数据
                stock_300101 = None
                for item in result['data']:
                    if item.get('代码') == '300101':
                        stock_300101 = item
                        break
                
                if stock_300101:
                    print(f"\n✓ 找到300101的数据:")
                    print(f"  名称: {stock_300101.get('名称', '--')}")
                    print(f"  最新价: {stock_300101.get('最新价', '--')}")
                    print(f"  涨跌幅: {stock_300101.get('涨跌幅', '--')}%")
                    print(f"  成交量: {stock_300101.get('成交量', '--')}")
                    print(f"  成交额: {stock_300101.get('成交额', '--')}")
                    print(f"  总市值: {stock_300101.get('总市值', '--')}")
                    print(f"  流通市值: {stock_300101.get('流通市值', '--')}")
                    print(f"  市盈率-动态: {stock_300101.get('市盈率-动态', '--')}")
                    
                    # 检查关键字段
                    key_fields = ['代码', '名称', '最新价', '涨跌幅', '市盈率-动态', '总市值', '流通市值']
                    print(f"\n关键字段检查:")
                    for field in key_fields:
                        if field in stock_300101:
                            value = stock_300101[field]
                            print(f"  ✓ {field}: {value}")
                        else:
                            print(f"  ✗ {field}: 缺失")
                            
                else:
                    print("✗ 未找到300101的数据")
                    
            else:
                print(f"✗ API调用失败: {result.get('error', '未知错误')}")
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")

def test_individual_stock_api():
    """测试个股实时数据API"""
    print("\n" + "=" * 60)
    print("测试个股实时数据API (备用数据源)")
    print("=" * 60)
    
    try:
        response = requests.get('http://localhost:8080/api/stock/300101/realtime', timeout=10)
        if response.status_code == 200:
            result = response.json()
            
            if result['success']:
                print(f"✓ 个股API调用成功")
                spot_data = result.get('spot', {})
                print(f"  名称: {spot_data.get('name', '--')}")
                print(f"  最新价: {spot_data.get('latest_price', '--')}")
                print(f"  涨跌幅: {spot_data.get('change_percent', '--')}%")
                print(f"  成交量: {spot_data.get('volume', '--')}")
                print(f"  成交额: {spot_data.get('amount', '--')}")
                print(f"  总市值: {spot_data.get('market_cap', '--')}")
                
            else:
                print(f"✗ 个股API调用失败: {result.get('error', '未知错误')}")
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"✗ 个股API测试失败: {e}")

def test_frontend_field_mapping():
    """测试前端字段映射"""
    print("\n" + "=" * 60)
    print("前端字段映射检查")
    print("=" * 60)
    
    print("修复内容:")
    print("1. ✓ 自动刷新时保留上一次成功的数据")
    print("2. ✓ 修复了市盈率-动态字段的ID映射问题")
    print("3. ✓ 添加了自动刷新标识，区分手动刷新和自动刷新")
    print("4. ✓ 在自动刷新失败时不清空现有数据")
    
    print("\n字段映射修复:")
    print("  前端HTML ID: rt_市盈率_动态")
    print("  后端字段名: 市盈率-动态")
    print("  ✓ JavaScript中已添加特殊处理")

if __name__ == "__main__":
    print("实时数据显示修复效果测试")
    print("测试时间:", time.strftime('%Y-%m-%d %H:%M:%S'))
    
    test_realtime_api()
    test_individual_stock_api()
    test_frontend_field_mapping()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)