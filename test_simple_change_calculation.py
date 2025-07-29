#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的涨跌幅计算测试脚本

专门测试个股实时数据的涨跌幅计算是否正确
"""

import requests
import json
import time

def test_individual_stock_change_calculation():
    """测试个股实时数据中的涨跌幅计算"""
    
    print("🎯 测试个股实时数据的涨跌幅计算...")
    print("=" * 60)
    
    # 测试多只股票
    test_stocks = ['300354', '000001', '600036', '000002', '600519']
    
    for stock_code in test_stocks:
        try:
            url = f"http://localhost:8080/api/stock/{stock_code}/realtime"
            print(f"\n📡 测试股票 {stock_code}...")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ API请求失败，状态码: {response.status_code}")
                continue
            
            data = response.json()
            
            if data.get('error'):
                print(f"❌ API返回错误: {data.get('error')}")
                continue
            
            spot_data = data.get('spot', {})
            if not spot_data:
                print("❌ 未获取到股票实时数据")
                continue
            
            name = spot_data.get('name', '')
            latest_price = spot_data.get('latest_price', 0)
            open_price = spot_data.get('open', 0)
            pre_close = spot_data.get('pre_close', 0)
            change_percent = spot_data.get('change_percent', 0)
            change_amount = spot_data.get('change_amount', 0)
            
            print(f"📊 股票: {stock_code} {name}")
            print(f"   最新价: {latest_price}")
            print(f"   今开: {open_price}")
            print(f"   昨收: {pre_close}")
            print(f"   报告涨跌幅: {change_percent}%")
            print(f"   报告涨跌额: {change_amount}")
            
            # 计算期望的涨跌幅和涨跌额
            if open_price > 0:
                expected_change_percent = ((latest_price - open_price) / open_price) * 100
                expected_change_amount = latest_price - open_price
                print(f"   期望涨跌幅: {expected_change_percent:.2f}% (基于今开)")
                print(f"   期望涨跌额: {expected_change_amount:.2f}")
                
                # 检查计算是否正确（允许小数点后2位的误差）
                change_percent_diff = abs(change_percent - expected_change_percent)
                change_amount_diff = abs(change_amount - expected_change_amount)
                
                if change_percent_diff <= 0.01 and change_amount_diff <= 0.01:
                    print("   ✅ 涨跌幅计算正确")
                else:
                    print(f"   ❌ 涨跌幅计算错误，差异: 涨跌幅 {change_percent_diff:.4f}%, 涨跌额 {change_amount_diff:.4f}")
            else:
                print("   ⚠️  今开价格为0，无法验证")
                
        except Exception as e:
            print(f"❌ 测试股票 {stock_code} 时出现错误: {e}")

def test_realtime_trading_data_sample():
    """测试实时交易数据的样本"""
    
    print("\n🧪 测试实时交易数据样本...")
    print("=" * 60)
    
    try:
        url = "http://localhost:8080/api/stock/realtime_trading_data"
        print(f"📡 请求URL: {url}")
        
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API请求失败，状态码: {response.status_code}")
            return
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ API返回错误: {data.get('error', '未知错误')}")
            return
        
        stocks = data.get('data', [])
        if not stocks:
            print("❌ 未获取到股票数据")
            return
        
        print(f"✅ 成功获取 {len(stocks)} 条股票数据")
        print(f"📊 数据来源: {data.get('data_source', '未知')}")
        print(f"🕐 获取时间: {data.get('fetch_time', '未知')}")
        
        # 只测试前3只股票
        for i, stock in enumerate(stocks[:3]):
            code = stock.get('代码', '')
            name = stock.get('名称', '')
            latest_price = stock.get('最新价', 0)
            open_price = stock.get('今开', 0)
            yesterday_close = stock.get('昨收', 0)
            reported_change_percent = stock.get('涨跌幅', 0)
            reported_change_amount = stock.get('涨跌额', 0)
            
            print(f"\n📊 股票 {i+1}: {code} {name}")
            print(f"   最新价: {latest_price}")
            print(f"   今开: {open_price}")
            print(f"   昨收: {yesterday_close}")
            print(f"   报告涨跌幅: {reported_change_percent}%")
            print(f"   报告涨跌额: {reported_change_amount}")
            
            # 计算期望的涨跌幅和涨跌额
            if open_price > 0:
                expected_change_percent = ((latest_price - open_price) / open_price) * 100
                expected_change_amount = latest_price - open_price
                print(f"   期望涨跌幅: {expected_change_percent:.2f}% (基于今开: {open_price})")
                print(f"   期望涨跌额: {expected_change_amount:.2f}")
                
                # 检查计算是否正确
                change_percent_diff = abs(reported_change_percent - expected_change_percent)
                change_amount_diff = abs(reported_change_amount - expected_change_amount)
                
                if change_percent_diff <= 0.01 and change_amount_diff <= 0.01:
                    print("   ✅ 涨跌幅计算正确")
                else:
                    print(f"   ❌ 涨跌幅计算错误，差异: 涨跌幅 {change_percent_diff:.4f}%, 涨跌额 {change_amount_diff:.4f}")
            else:
                print("   ⚠️  今开价格为0，无法验证")
                
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")

if __name__ == "__main__":
    print("🔧 简化的涨跌幅计算测试...")
    print("=" * 80)
    
    # 等待服务器启动
    print("⏳ 等待服务器启动...")
    time.sleep(3)
    
    # 测试个股实时数据
    test_individual_stock_change_calculation()
    
    # 测试实时交易数据样本
    test_realtime_trading_data_sample()
    
    print("\n" + "=" * 80)
    print("🏁 测试完成！")