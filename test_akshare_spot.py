#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AkShare实时行情接口获取换手率和量比数据
"""

import akshare as ak
import pandas as pd
from datetime import datetime

def test_spot_data():
    """测试实时行情数据获取"""
    try:
        print("正在获取实时行情数据...")
        spot_data = ak.stock_zh_a_spot_em()
        
        if spot_data.empty:
            print("❌ 获取实时行情数据失败：数据为空")
            return
        
        print(f"✅ 成功获取实时行情数据，共 {len(spot_data)} 只股票")
        
        # 查看数据列名
        print("\n📊 数据列名：")
        print(spot_data.columns.tolist())
        
        # 测试几只热门股票
        test_stocks = ['000001', '000002', '600519', '300059']
        
        for stock_code in test_stocks:
            print(f"\n🔍 测试股票 {stock_code}:")
            stock_data = spot_data[spot_data['代码'] == stock_code]
            
            if stock_data.empty:
                print(f"  ❌ 未找到股票 {stock_code} 的数据")
                continue
            
            stock_info = stock_data.iloc[0]
            print(f"  股票名称: {stock_info['名称']}")
            print(f"  最新价: {stock_info['最新价']}")
            print(f"  涨跌幅: {stock_info['涨跌幅']}%")
            print(f"  成交额: {stock_info['成交额']}")
            
            # 重点检查换手率和量比
            if '换手率' in stock_info:
                turnover_rate = stock_info['换手率']
                print(f"  🎯 换手率: {turnover_rate}% (类型: {type(turnover_rate)})")
                if pd.isna(turnover_rate) or turnover_rate == '-' or turnover_rate == 0:
                    print(f"    ⚠️  换手率数据无效")
                else:
                    print(f"    ✅ 换手率数据有效")
            else:
                print(f"  ❌ 没有换手率字段")
            
            if '量比' in stock_info:
                volume_ratio = stock_info['量比']
                print(f"  🎯 量比: {volume_ratio} (类型: {type(volume_ratio)})")
                if pd.isna(volume_ratio) or volume_ratio == '-' or volume_ratio == 0:
                    print(f"    ⚠️  量比数据无效")
                else:
                    print(f"    ✅ 量比数据有效")
            else:
                print(f"  ❌ 没有量比字段")
        
        # 统计有效数据
        print("\n📈 数据统计:")
        if '换手率' in spot_data.columns:
            valid_turnover = spot_data[spot_data['换手率'].notna() & (spot_data['换手率'] != '-') & (spot_data['换手率'] != 0)]
            print(f"  有效换手率数据: {len(valid_turnover)}/{len(spot_data)} ({len(valid_turnover)/len(spot_data)*100:.1f}%)")
        
        if '量比' in spot_data.columns:
            valid_volume_ratio = spot_data[spot_data['量比'].notna() & (spot_data['量比'] != '-') & (spot_data['量比'] != 0)]
            print(f"  有效量比数据: {len(valid_volume_ratio)}/{len(spot_data)} ({len(valid_volume_ratio)/len(spot_data)*100:.1f}%)")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_individual_stock():
    """测试单只股票的详细数据"""
    try:
        print("\n\n🔍 测试单只股票详细数据 (平安银行 000001):")
        
        # 获取单只股票的实时数据
        stock_code = '000001'
        spot_data = ak.stock_zh_a_spot_em()
        
        if not spot_data.empty:
            stock_data = spot_data[spot_data['代码'] == stock_code]
            if not stock_data.empty:
                stock_info = stock_data.iloc[0]
                print("\n📋 完整数据:")
                for col in stock_info.index:
                    value = stock_info[col]
                    print(f"  {col}: {value} (类型: {type(value)})")
        
    except Exception as e:
        print(f"❌ 单股测试失败: {e}")

if __name__ == "__main__":
    print(f"🚀 开始测试 AkShare 实时行情接口 - {datetime.now()}")
    print("=" * 60)
    
    test_spot_data()
    test_individual_stock()
    
    print("\n" + "=" * 60)
    print("🏁 测试完成")