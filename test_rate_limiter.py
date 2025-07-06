#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare API频率限制器测试脚本
用于验证频率限制功能是否正常工作
"""

import sys
import os
import time
import requests
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_rate_limiter_api():
    """测试频率限制器API端点"""
    base_url = "http://localhost:8080"
    
    print("=== Tushare API频率限制器测试 ===")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 测试频率限制器状态API
        print("1. 测试频率限制器状态API...")
        response = requests.get(f"{base_url}/api/rate_limiter/status")
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                status_info = data['data']
                print("✓ 频率限制器状态API正常")
                print(f"  - 已使用请求数: {status_info['used_requests']}")
                print(f"  - 剩余请求数: {status_info['remaining_requests']}")
                print(f"  - 每分钟最大请求数: {status_info['max_requests_per_minute']}")
                print(f"  - 当前时间: {status_info['current_time_formatted']}")
                if status_info['next_reset_time_formatted']:
                    print(f"  - 下次重置时间: {status_info['next_reset_time_formatted']}")
                    print(f"  - 距离重置还有: {status_info['seconds_until_reset']}秒")
                else:
                    print("  - 下次重置时间: 无需重置")
            else:
                print(f"✗ API返回错误: {data.get('message', '未知错误')}")
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务器，请确保应用正在运行 (python app.py)")
        return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    print()
    
    # 测试股票数据API（会触发tushare调用）
    print("2. 测试股票数据API（验证频率限制生效）...")
    try:
        # 获取一只股票的数据
        test_stock = "000001.SZ"  # 平安银行
        print(f"获取股票 {test_stock} 的数据...")
        
        start_time = time.time()
        response = requests.get(f"{base_url}/api/stock/{test_stock}")
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                print(f"✓ 股票数据获取成功")
                print(f"  - 股票名称: {data.get('name', 'N/A')}")
                print(f"  - 最新价格: {data.get('latest_price', 'N/A')}")
                print(f"  - 请求耗时: {end_time - start_time:.2f}秒")
            else:
                print(f"✗ 股票数据获取失败: {data['error']}")
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"✗ 股票数据测试失败: {e}")
    
    print()
    
    # 再次检查频率限制器状态
    print("3. 检查API调用后的频率限制器状态...")
    try:
        response = requests.get(f"{base_url}/api/rate_limiter/status")
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                status_info = data['data']
                print("✓ 频率限制器状态更新正常")
                print(f"  - 已使用请求数: {status_info['used_requests']}")
                print(f"  - 剩余请求数: {status_info['remaining_requests']}")
            else:
                print(f"✗ API返回错误: {data.get('message', '未知错误')}")
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
    except Exception as e:
        print(f"✗ 状态检查失败: {e}")
    
    print()
    print("=== 测试完成 ===")
    print("\n使用说明:")
    print("1. 频率限制器会自动限制tushare API调用频率，确保每分钟不超过199次")
    print("2. 当达到限制时，系统会自动等待，直到可以继续发送请求")
    print("3. 可以通过 /api/rate_limiter/status 实时监控API使用情况")
    print("4. 在高频数据更新时，系统会自动调节请求速度")
    
    return True

def test_local_rate_limiter():
    """测试本地频率限制器类"""
    print("=== 本地频率限制器类测试 ===")
    
    # 导入频率限制器类
    try:
        from app import TushareRateLimiter
        
        # 创建测试用的限制器（每分钟最多5次请求，便于测试）
        test_limiter = TushareRateLimiter(max_requests_per_minute=5)
        
        print("1. 测试正常请求...")
        for i in range(3):
            start_time = time.time()
            test_limiter.wait_if_needed()
            end_time = time.time()
            print(f"  请求 {i+1}: 等待时间 {end_time - start_time:.3f}秒")
        
        print("\n2. 测试频率限制...")
        print("快速发送6次请求（超过限制）...")
        for i in range(6):
            start_time = time.time()
            test_limiter.wait_if_needed()
            end_time = time.time()
            remaining = test_limiter.get_remaining_requests()
            print(f"  请求 {i+1}: 等待时间 {end_time - start_time:.3f}秒, 剩余请求数: {remaining}")
        
        print("\n3. 测试状态信息...")
        status = test_limiter.get_status()
        print(f"  已使用: {status['used_requests']}")
        print(f"  剩余: {status['remaining_requests']}")
        print(f"  最大: {status['max_requests_per_minute']}")
        
        print("\n✓ 本地频率限制器测试完成")
        
    except ImportError as e:
        print(f"✗ 无法导入频率限制器类: {e}")
        return False
    except Exception as e:
        print(f"✗ 本地测试失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Tushare API频率限制器测试工具")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        # 只测试本地频率限制器类
        test_local_rate_limiter()
    else:
        # 测试API端点（需要服务器运行）
        print("提示: 请确保应用服务器正在运行 (python app.py)")
        print("如果只想测试本地类，请使用: python test_rate_limiter.py --local")
        print()
        
        success = test_rate_limiter_api()
        if not success:
            print("\n如果服务器未运行，可以尝试本地测试:")
            print("python test_rate_limiter.py --local")