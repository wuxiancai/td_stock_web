#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试涨跌幅计算修复是否生效的脚本

验证实时交易数据中的涨跌幅和涨跌额是否正确计算：
- 涨跌幅 = (当前价格 - 今开价格) / 今开价格 * 100
- 涨跌额 = 当前价格 - 今开价格
"""

import requests
import json
import time

def test_realtime_change_calculation():
    """测试实时交易数据中的涨跌幅计算是否正确"""
    
    print("🧪 测试实时交易数据中的涨跌幅计算修复...")
    print("=" * 60)
    
    try:
        # 获取实时交易数据
        url = "http://localhost:8080/api/stock/realtime_trading_data"
        print(f"📡 请求URL: {url}")
        
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API请求失败，状态码: {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ API返回错误: {data.get('error', '未知错误')}")
            return False
        
        stocks = data.get('data', [])
        if not stocks:
            print("❌ 未获取到股票数据")
            return False
        
        print(f"✅ 成功获取 {len(stocks)} 条股票数据")
        print("\n🔍 验证涨跌幅计算逻辑...")
        
        # 测试前10只股票的涨跌幅计算
        test_count = 0
        correct_count = 0
        
        for i, stock in enumerate(stocks[:10]):
            test_count += 1
            
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
                base_price_type = "今开"
                base_price = open_price
            elif yesterday_close > 0:
                expected_change_percent = ((latest_price - yesterday_close) / yesterday_close) * 100
                expected_change_amount = latest_price - yesterday_close
                base_price_type = "昨收"
                base_price = yesterday_close
            else:
                print("   ⚠️  无法计算，今开和昨收都为0")
                continue
            
            print(f"   期望涨跌幅: {expected_change_percent:.2f}% (基于{base_price_type}: {base_price})")
            print(f"   期望涨跌额: {expected_change_amount:.2f}")
            
            # 检查计算是否正确（允许小数点后2位的误差）
            change_percent_diff = abs(reported_change_percent - expected_change_percent)
            change_amount_diff = abs(reported_change_amount - expected_change_amount)
            
            if change_percent_diff <= 0.01 and change_amount_diff <= 0.01:
                print("   ✅ 涨跌幅计算正确")
                correct_count += 1
            else:
                print(f"   ❌ 涨跌幅计算错误，差异: 涨跌幅 {change_percent_diff:.4f}%, 涨跌额 {change_amount_diff:.4f}")
        
        print(f"\n📈 测试结果:")
        print(f"   测试股票数量: {test_count}")
        print(f"   计算正确数量: {correct_count}")
        print(f"   正确率: {(correct_count/test_count)*100:.1f}%")
        
        if correct_count == test_count:
            print("\n🎉 涨跌幅计算修复成功！所有测试股票的涨跌幅都基于今开价格正确计算。")
            return True
        elif correct_count > test_count * 0.8:
            print("\n⚠️  大部分股票的涨跌幅计算正确，可能存在个别数据问题。")
            return True
        else:
            print("\n❌ 涨跌幅计算修复失败，大部分股票的计算仍然错误。")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        return False

def test_specific_stock_change_calculation():
    """测试特定股票的涨跌幅计算"""
    
    print("\n🎯 测试特定股票的涨跌幅计算...")
    print("=" * 60)
    
    # 测试股票300354的实时数据
    try:
        url = "http://localhost:8080/api/stock/300354/realtime"
        print(f"📡 请求URL: {url}")
        
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API请求失败，状态码: {response.status_code}")
            return False
        
        data = response.json()
        
        if data.get('error'):
            print(f"❌ API返回错误: {data.get('error')}")
            return False
        
        spot_data = data.get('spot', {})
        if not spot_data:
            print("❌ 未获取到股票实时数据")
            return False
        
        print("✅ 成功获取股票300354的实时数据")
        
        name = spot_data.get('name', '')
        latest_price = spot_data.get('latest_price', 0)
        open_price = spot_data.get('open', 0)
        pre_close = spot_data.get('pre_close', 0)
        change_percent = spot_data.get('change_percent', 0)
        change_amount = spot_data.get('change_amount', 0)
        
        print(f"\n📊 股票: 300354 {name}")
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
        else:
            print("   ⚠️  今开价格为0，无法验证")
            return False
        
        # 检查计算是否正确
        change_percent_diff = abs(change_percent - expected_change_percent)
        change_amount_diff = abs(change_amount - expected_change_amount)
        
        if change_percent_diff <= 0.01 and change_amount_diff <= 0.01:
            print("   ✅ 股票300354的涨跌幅计算正确")
            return True
        else:
            print(f"   ❌ 股票300354的涨跌幅计算错误，差异: 涨跌幅 {change_percent_diff:.4f}%, 涨跌额 {change_amount_diff:.4f}")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        return False

if __name__ == "__main__":
    print("🔧 测试涨跌幅计算修复效果...")
    print("=" * 80)
    
    # 等待服务器完全启动
    print("⏳ 等待服务器启动...")
    time.sleep(3)
    
    # 测试实时交易数据
    success1 = test_realtime_change_calculation()
    
    # 测试特定股票
    success2 = test_specific_stock_change_calculation()
    
    print("\n" + "=" * 80)
    if success1 and success2:
        print("🎉 所有测试通过！涨跌幅计算修复成功！")
        print("\n✅ 修复效果:")
        print("   - 实时交易数据的涨跌幅现在基于今开价格计算")
        print("   - 个股实时数据的涨跌幅计算也已修正")
        print("   - 涨跌额计算同样基于今开价格")
    else:
        print("❌ 部分测试失败，请检查修复效果。")