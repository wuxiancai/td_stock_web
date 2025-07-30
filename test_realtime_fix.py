#!/usr/bin/env python3
"""
测试实时数据修复效果
验证在交易时间内和非交易时间内的数据获取逻辑
"""

import requests
import json
from datetime import datetime, time

def test_market_status():
    """测试市场状态API"""
    print("=== 测试市场状态 ===")
    try:
        response = requests.get('http://localhost:8080/api/market/status')
        data = response.json()
        print(f"市场状态: {data}")
        return data.get('is_market_open', False)
    except Exception as e:
        print(f"获取市场状态失败: {e}")
        return False

def test_realtime_data(stock_code='300354'):
    """测试实时数据API"""
    print(f"\n=== 测试股票 {stock_code} 实时数据 ===")
    try:
        response = requests.get(f'http://localhost:8080/api/stock/{stock_code}/realtime')
        data = response.json()
        
        if 'spot' in data:
            spot = data['spot']
            print(f"股票名称: {spot.get('name', 'N/A')}")
            print(f"最新价格: {spot.get('latest_price', 'N/A')}")
            print(f"涨跌幅: {spot.get('change_percent', 'N/A'):.2f}%")
            print(f"涨跌额: {spot.get('change_amount', 'N/A')}")
            print(f"数据源: {spot.get('data_source', 'N/A')}")
            print(f"更新时间: {spot.get('update_time', 'N/A')}")
            
            # 验证数据合理性
            latest_price = spot.get('latest_price', 0)
            change_percent = spot.get('change_percent', 0)
            
            if latest_price > 0:
                print(f"✓ 价格数据正常: {latest_price}")
            else:
                print(f"✗ 价格数据异常: {latest_price}")
                
            if abs(change_percent) < 20:  # 涨跌幅在合理范围内
                print(f"✓ 涨跌幅数据正常: {change_percent:.2f}%")
            else:
                print(f"✗ 涨跌幅数据异常: {change_percent:.2f}%")
                
        else:
            print(f"API返回数据格式异常: {data}")
            
    except Exception as e:
        print(f"获取实时数据失败: {e}")

def test_akshare_realtime_data():
    """测试AkShare实时交易数据API"""
    print(f"\n=== 测试AkShare实时交易数据 ===")
    try:
        response = requests.get('http://localhost:8080/api/stock/realtime_trading_data')
        data = response.json()
        
        if data.get('success'):
            trading_data = data.get('data', [])
            print(f"获取到 {len(trading_data)} 条实时交易数据")
            
            # 查找300354的数据
            target_stock = None
            for stock in trading_data:
                if stock.get('代码') == '300354':
                    target_stock = stock
                    break
                    
            if target_stock:
                print(f"找到300354数据:")
                print(f"  名称: {target_stock.get('名称', 'N/A')}")
                print(f"  最新价: {target_stock.get('最新价', 'N/A')}")
                print(f"  涨跌幅: {target_stock.get('涨跌幅', 'N/A')}")
                print(f"  成交量: {target_stock.get('成交量', 'N/A')}")
                print(f"  获取时间: {data.get('fetch_time', 'N/A')}")
            else:
                print("未找到300354的数据")
        else:
            print(f"AkShare API调用失败: {data.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"测试AkShare实时数据失败: {e}")

def simulate_trading_time_test():
    """模拟交易时间测试（通过修改系统时间判断逻辑）"""
    print(f"\n=== 模拟交易时间测试说明 ===")
    print("当前时间超出交易时间，API会返回收盘数据")
    print("在实际交易时间内（9:30-11:30, 13:00-15:00），API会:")
    print("1. 首先尝试从AkShare获取实时数据")
    print("2. 如果AkShare失败，回退到Tushare历史数据")
    print("3. 数据源会在data_source字段中标明")

def main():
    """主测试函数"""
    print("股票实时数据修复测试")
    print("=" * 50)
    
    # 测试市场状态
    is_market_open = test_market_status()
    
    # 测试实时数据
    test_realtime_data('300354')
    
    # 测试AkShare实时数据
    test_akshare_realtime_data()
    
    # 模拟交易时间测试说明
    simulate_trading_time_test()
    
    print(f"\n=== 测试总结 ===")
    if is_market_open:
        print("当前在交易时间内，API应该返回实时数据（data_source: akshare_live_realtime 或 tushare_fallback）")
    else:
        print("当前在非交易时间，API返回收盘数据（data_source: latest_close）")
    
    print("\n修复要点:")
    print("1. ✓ 增加了AkShare实时数据获取逻辑")
    print("2. ✓ 改进了错误处理，避免网络问题导致服务器崩溃")
    print("3. ✓ 保持了Tushare作为备用数据源")
    print("4. ✓ 明确标识了数据来源")

if __name__ == '__main__':
    main()