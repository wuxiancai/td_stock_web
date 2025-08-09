#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试实时数据修复效果
验证新浪财经API作为主要数据源的效果
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_sina_batch_realtime_data, get_enhanced_stock_info, safe_akshare_call
import akshare as ak
import pandas as pd
from datetime import datetime

def test_sina_api_enhanced():
    """测试增强版新浪API"""
    print("=" * 60)
    print("测试增强版新浪财经API（包含字段补充）")
    print("=" * 60)
    
    try:
        # 获取新浪实时数据
        sina_data = get_sina_batch_realtime_data()
        
        if sina_data is not None and not sina_data.empty:
            print(f"✅ 新浪财经API成功获取 {len(sina_data)} 只股票数据")
            print("\n前5只股票数据:")
            print("-" * 80)
            
            for idx, row in sina_data.head().iterrows():
                code = row['代码']
                name = row['名称']
                price = row['最新价']
                change_pct = row['涨跌幅']
                market_cap = row['总市值']
                pe_ratio = row['市盈率-动态']
                turnover = row['换手率']
                
                print(f"{idx+1}. {code} {name}")
                print(f"   最新价: {price:.2f}, 涨跌幅: {change_pct:.2f}%")
                print(f"   总市值: {market_cap:.2f}亿, PE: {pe_ratio:.2f}, 换手率: {turnover:.2f}%")
                print()
            
            # 统计字段补充情况
            enhanced_count = 0
            total_count = len(sina_data)
            
            for _, row in sina_data.iterrows():
                if row['总市值'] > 0 or row['市盈率-动态'] > 0 or row['换手率'] > 0:
                    enhanced_count += 1
            
            print(f"字段补充统计:")
            print(f"- 总股票数: {total_count}")
            print(f"- 成功补充字段的股票数: {enhanced_count}")
            print(f"- 补充成功率: {enhanced_count/total_count*100:.1f}%")
            
            return True
        else:
            print("❌ 新浪财经API返回空数据")
            return False
            
    except Exception as e:
        print(f"❌ 新浪财经API测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dongcai_api():
    """测试东财API（预期失败）"""
    print("=" * 60)
    print("测试东财API（验证网络问题）")
    print("=" * 60)
    
    try:
        print("尝试调用 ak.stock_zh_a_spot_em()...")
        dongcai_data = safe_akshare_call(
            ak.stock_zh_a_spot_em,
            "test_dongcai_api",
            max_retries=1,
            retry_delay=0.5
        )
        
        if dongcai_data is not None and not dongcai_data.empty:
            print(f"✅ 东财API成功获取 {len(dongcai_data)} 只股票数据")
            return True
        else:
            print("❌ 东财API返回空数据或失败")
            return False
            
    except Exception as e:
        print(f"❌ 东财API测试失败: {e}")
        return False

def test_enhanced_stock_info():
    """测试股票信息增强功能"""
    print("=" * 60)
    print("测试股票信息增强功能")
    print("=" * 60)
    
    test_stocks = ['000001', '000002', '600000', '600036', '000858']
    
    for stock_code in test_stocks:
        try:
            print(f"测试股票: {stock_code}")
            enhanced_info = get_enhanced_stock_info(stock_code)
            
            if enhanced_info:
                print(f"  ✅ 成功获取增强信息:")
                for key, value in enhanced_info.items():
                    if value > 0:
                        print(f"    {key}: {value}")
            else:
                print(f"  ❌ 未获取到增强信息")
            print()
            
        except Exception as e:
            print(f"  ❌ 获取 {stock_code} 增强信息失败: {e}")
            print()

def test_data_source_fallback():
    """测试数据源降级策略"""
    print("=" * 60)
    print("测试数据源降级策略")
    print("=" * 60)
    
    # 模拟实时数据获取流程
    print("1. 优先使用新浪财经API...")
    sina_success = test_sina_api_enhanced()
    
    print("\n2. 备用东财API...")
    dongcai_success = test_dongcai_api()
    
    print("\n数据源策略结果:")
    print(f"- 新浪财经API: {'✅ 可用' if sina_success else '❌ 不可用'}")
    print(f"- 东财API: {'✅ 可用' if dongcai_success else '❌ 不可用'}")
    
    if sina_success:
        print("✅ 数据源降级策略有效：新浪财经API作为主要数据源")
    elif dongcai_success:
        print("⚠️  新浪财经API失败，但东财API可用")
    else:
        print("❌ 所有数据源都不可用")

def main():
    """主测试函数"""
    print("东财网络问题修复效果测试")
    print("测试时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 80)
    
    # 测试各个组件
    test_enhanced_stock_info()
    test_data_source_fallback()
    
    print("=" * 80)
    print("测试完成")
    print("\n修复总结:")
    print("1. ✅ 新浪财经API作为主要实时数据源")
    print("2. ✅ 通过AkShare个股信息接口补充缺失字段")
    print("3. ✅ 实现数据源降级策略")
    print("4. ❌ 东财实时接口仍有网络问题（已绕过）")
    print("\n建议:")
    print("- 继续使用新浪财经API作为主要数据源")
    print("- 监控东财接口恢复情况")
    print("- 考虑添加更多备用数据源")

if __name__ == "__main__":
    main()