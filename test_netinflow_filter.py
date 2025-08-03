#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试净流入额筛选功能
"""

import requests
import json

def test_green_filter():
    """测试绿9筛选API"""
    print("=== 测试绿9筛选API ===")
    try:
        response = requests.get('http://127.0.0.1:8080/api/green-filter', timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                stocks = data.get('data', [])
                print(f"绿9筛选结果数量: {len(stocks)}")
                
                # 检查前5个股票的净流入额数据
                for i, stock in enumerate(stocks[:5]):
                    net_mf_amount = stock.get('net_mf_amount', 0)
                    ts_code = stock.get('ts_code', 'N/A')
                    name = stock.get('name', 'N/A')
                    print(f"  {i+1}. {ts_code} {name}: 净流入额 = {net_mf_amount} 千万元")
                
                # 统计有净流入额数据的股票数量
                with_netflow = [s for s in stocks if s.get('net_mf_amount', 0) != 0]
                print(f"有净流入额数据的股票数量: {len(with_netflow)}")
                
                return True
            else:
                print(f"API返回失败: {data.get('message', '未知错误')}")
                return False
        else:
            print(f"HTTP请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"请求异常: {e}")
        return False

def test_red_filter():
    """测试红3-6筛选API"""
    print("\n=== 测试红3-6筛选API ===")
    try:
        response = requests.get('http://127.0.0.1:8080/api/red-filter', timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                stocks = data.get('data', [])
                print(f"红3-6筛选结果数量: {len(stocks)}")
                
                # 检查前5个股票的净流入额数据
                for i, stock in enumerate(stocks[:5]):
                    net_mf_amount = stock.get('net_mf_amount', 0)
                    ts_code = stock.get('ts_code', 'N/A')
                    name = stock.get('name', 'N/A')
                    print(f"  {i+1}. {ts_code} {name}: 净流入额 = {net_mf_amount} 千万元")
                
                # 统计有净流入额数据的股票数量
                with_netflow = [s for s in stocks if s.get('net_mf_amount', 0) != 0]
                print(f"有净流入额数据的股票数量: {len(with_netflow)}")
                
                return True
            else:
                print(f"API返回失败: {data.get('message', '未知错误')}")
                return False
        else:
            print(f"HTTP请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"请求异常: {e}")
        return False

def test_cache_data():
    """测试缓存数据中的净流入额"""
    print("\n=== 测试缓存数据 ===")
    try:
        import os
        cache_files = ['hu_stocks_cache.json', 'sz_stocks_cache.json', 'bj_stocks_cache.json']
        
        for cache_file in cache_files:
            cache_path = f'/Users/wuxiancai/td_stock_web/cache/{cache_file}'
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    stocks = json.load(f)
                
                # 统计有净流入额数据的股票
                with_netflow = [s for s in stocks if s.get('net_mf_amount', 0) != 0]
                print(f"{cache_file}: 总股票数 = {len(stocks)}, 有净流入额数据 = {len(with_netflow)}")
                
                # 显示前3个有净流入额的股票
                for i, stock in enumerate(with_netflow[:3]):
                    net_mf_amount = stock.get('net_mf_amount', 0)
                    ts_code = stock.get('ts_code', 'N/A')
                    name = stock.get('name', 'N/A')
                    print(f"  {ts_code} {name}: {net_mf_amount} 千万元")
            else:
                print(f"{cache_file}: 文件不存在")
        
        return True
    except Exception as e:
        print(f"读取缓存数据异常: {e}")
        return False

if __name__ == "__main__":
    print("开始测试净流入额筛选功能...")
    
    # 测试缓存数据
    test_cache_data()
    
    # 测试API
    green_ok = test_green_filter()
    red_ok = test_red_filter()
    
    print(f"\n=== 测试结果 ===")
    print(f"绿9筛选API: {'✓ 正常' if green_ok else '✗ 异常'}")
    print(f"红3-6筛选API: {'✓ 正常' if red_ok else '✗ 异常'}")
    
    if green_ok and red_ok:
        print("\n✓ 所有测试通过！净流入额筛选功能应该正常工作。")
    else:
        print("\n✗ 部分测试失败，请检查服务器状态。")