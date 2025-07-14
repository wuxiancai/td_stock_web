#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控AkShare重试机制
实时查看重试状态和自动重试过程
"""

import requests
import json
import time
from datetime import datetime

def monitor_retry_status():
    """监控重试状态"""
    base_url = "http://localhost:8080"
    
    print("=== AkShare重试机制监控 ===")
    print("按 Ctrl+C 停止监控")
    print()
    
    last_status = None
    
    try:
        while True:
            try:
                response = requests.get(f"{base_url}/api/akshare/retry_status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['success']:
                        retry_data = data['data']
                        
                        # 检查状态是否有变化
                        current_status = json.dumps(retry_data, sort_keys=True)
                        if current_status != last_status:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 重试状态更新:")
                            print(f"总失败请求数: {retry_data['total_failed_requests']}")
                            print(f"重试间隔: {retry_data['retry_interval_minutes']} 分钟")
                            
                            if retry_data['failed_requests']:
                                print("失败的请求:")
                                for req in retry_data['failed_requests']:
                                    print(f"  📍 {req['request_key']}:")
                                    print(f"     失败次数: {req['failure_count']}")
                                    print(f"     最后错误: {req['last_error'][:80]}...")
                                    
                                    if req['can_retry_now']:
                                        print(f"     🔄 可立即重试")
                                    else:
                                        print(f"     ⏰ {req['next_retry_in_seconds']}秒后重试")
                            else:
                                print("✅ 当前没有失败的请求")
                            
                            last_status = current_status
                        else:
                            # 状态没变化，只显示倒计时
                            if retry_data['failed_requests']:
                                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] 等待重试中...", end="", flush=True)
                    else:
                        print(f"\n❌ 获取重试状态失败: {data.get('error', '未知错误')}")
                else:
                    print(f"\n❌ HTTP错误: {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"\n❌ 请求失败: {e}")
            except Exception as e:
                print(f"\n❌ 未知错误: {e}")
            
            time.sleep(5)  # 每5秒检查一次
            
    except KeyboardInterrupt:
        print("\n\n监控已停止")

def test_single_request():
    """测试单个请求以触发重试机制"""
    base_url = "http://localhost:8080"
    
    print("=== 测试单个请求 ===")
    print("这将尝试获取股票实时数据，可能触发重试机制")
    print()
    
    stock_code = input("请输入股票代码 (默认: 000001): ").strip() or "000001"
    
    try:
        print(f"正在获取 {stock_code} 的实时数据...")
        response = requests.get(f"{base_url}/api/stock/{stock_code}/realtime", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n数据获取结果:")
            print(f"实时行情: {'✅ 成功' if data.get('spot') else '❌ 失败'}")
            print(f"分时数据: {'✅ 成功' if data.get('minute_data') else '❌ 失败'}")
            print(f"K线数据: {'✅ 成功' if data.get('kline_data') else '❌ 失败'}")
            print(f"资金流向: {'✅ 成功' if data.get('money_flow') else '❌ 失败'}")
            
            if data.get('spot'):
                spot = data['spot']
                print(f"\n股票信息:")
                print(f"名称: {spot.get('name', 'N/A')}")
                print(f"价格: {spot.get('latest_price', 'N/A')}")
                print(f"涨跌幅: {spot.get('change_percent', 'N/A')}%")
                print(f"换手率: {spot.get('turnover_rate', 'N/A')}%")
                print(f"量比: {spot.get('volume_ratio', 'N/A')}")
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            if response.text:
                try:
                    error_data = response.json()
                    print(f"错误信息: {error_data.get('error', '未知错误')}")
                except:
                    print(f"响应内容: {response.text[:200]}...")
                    
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print("\n请使用监控功能查看重试状态")

def main():
    """主函数"""
    while True:
        print("\n=== AkShare重试机制工具 ===")
        print("1. 监控重试状态")
        print("2. 测试单个请求")
        print("3. 退出")
        
        choice = input("\n请选择操作 (1-3): ").strip()
        
        if choice == '1':
            monitor_retry_status()
        elif choice == '2':
            test_single_request()
        elif choice == '3':
            print("再见！")
            break
        else:
            print("无效选择，请重试")

if __name__ == "__main__":
    main()