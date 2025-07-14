#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AkShare重试机制
验证定时重试功能是否正常工作
"""

import requests
import json
import time
from datetime import datetime

def test_retry_mechanism():
    """测试重试机制"""
    base_url = "http://localhost:8080"
    
    print("=== AkShare重试机制测试 ===")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 查看当前重试状态
    print("1. 查看当前重试状态:")
    try:
        response = requests.get(f"{base_url}/api/akshare/retry_status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                retry_data = data['data']
                print(f"   总失败请求数: {retry_data['total_failed_requests']}")
                print(f"   重试间隔: {retry_data['retry_interval_minutes']} 分钟")
                
                if retry_data['failed_requests']:
                    print("   失败的请求:")
                    for req in retry_data['failed_requests']:
                        print(f"     - {req['request_key']}:")
                        print(f"       失败次数: {req['failure_count']}")
                        print(f"       最后错误: {req['last_error'][:100]}...")
                        print(f"       下次重试: {req['next_retry_in_seconds']}秒后")
                        print(f"       可立即重试: {req['can_retry_now']}")
                else:
                    print("   ✅ 当前没有失败的请求")
            else:
                print(f"   ❌ 获取重试状态失败: {data.get('error', '未知错误')}")
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    print()
    
    # 2. 测试实时数据接口（可能触发重试机制）
    print("2. 测试实时数据接口:")
    test_stocks = ['000001', '000002', '600519']
    
    for stock_code in test_stocks:
        print(f"   测试股票 {stock_code}:")
        try:
            response = requests.get(f"{base_url}/api/stock/{stock_code}/realtime", timeout=15)
            if response.status_code == 200:
                data = response.json()
                
                # 检查各个数据源的状态
                spot_status = "✅ 成功" if data.get('spot') else "❌ 失败"
                minute_status = "✅ 成功" if data.get('minute_data') else "❌ 失败"
                kline_status = "✅ 成功" if data.get('kline_data') else "❌ 失败"
                money_flow_status = "✅ 成功" if data.get('money_flow') else "❌ 失败"
                
                print(f"     实时行情: {spot_status}")
                print(f"     分时数据: {minute_status}")
                print(f"     K线数据: {kline_status}")
                print(f"     资金流向: {money_flow_status}")
                
                # 如果有实时行情数据，显示关键信息
                if data.get('spot'):
                    spot = data['spot']
                    print(f"     价格: {spot.get('latest_price', 'N/A')}")
                    print(f"     换手率: {spot.get('turnover_rate', 'N/A')}%")
                    print(f"     量比: {spot.get('volume_ratio', 'N/A')}")
                
            else:
                print(f"     ❌ HTTP错误: {response.status_code}")
                if response.text:
                    try:
                        error_data = response.json()
                        print(f"     错误信息: {error_data.get('error', '未知错误')}")
                    except:
                        print(f"     响应内容: {response.text[:200]}...")
                        
        except Exception as e:
            print(f"     ❌ 请求失败: {e}")
        
        print()
    
    # 3. 再次查看重试状态（看是否有新的失败记录）
    print("3. 测试后的重试状态:")
    try:
        response = requests.get(f"{base_url}/api/akshare/retry_status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                retry_data = data['data']
                print(f"   总失败请求数: {retry_data['total_failed_requests']}")
                
                if retry_data['failed_requests']:
                    print("   新增失败的请求:")
                    for req in retry_data['failed_requests']:
                        print(f"     - {req['request_key']}:")
                        print(f"       失败次数: {req['failure_count']}")
                        print(f"       最后错误: {req['last_error'][:100]}...")
                        print(f"       首次失败: {req['first_failure_time']}")
                        print(f"       最后尝试: {req['last_attempt_time']}")
                        print(f"       下次重试: {req['next_retry_in_seconds']}秒后")
                else:
                    print("   ✅ 没有失败的请求")
            else:
                print(f"   ❌ 获取重试状态失败: {data.get('error', '未知错误')}")
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    print()
    print("=== 测试完成 ===")
    print()
    print("说明:")
    print("- 如果网络正常，所有数据源应该都能成功获取")
    print("- 如果出现网络错误，失败的请求会被记录，5分钟后自动重试")
    print("- 可以通过 /api/akshare/retry_status 接口监控重试状态")
    print("- 系统会在每天凌晨2点自动清理超过24小时的失败记录")

if __name__ == "__main__":
    test_retry_mechanism()