#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试AKShare实时数据接口
"""

import akshare as ak
import pandas as pd
from datetime import datetime

def test_akshare_realtime():
    """测试AKShare实时数据接口"""
    try:
        print("开始测试AKShare实时数据接口...")
        print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 尝试获取实时数据
        print("调用 ak.stock_zh_a_spot_em()...")
        data = ak.stock_zh_a_spot_em()
        
        if data is not None and not data.empty:
            print(f"✅ 成功获取实时数据，共 {len(data)} 条记录")
            
            # 查找300781
            stock_300781 = data[data['代码'] == '300781']
            if not stock_300781.empty:
                print("\n📊 300781 (因赛集团) 实时数据:")
                for col in ['代码', '名称', '最新价', '涨跌幅', '涨跌额', '今开', '昨收']:
                    if col in stock_300781.columns:
                        value = stock_300781.iloc[0][col]
                        print(f"  {col}: {value}")
            else:
                print("❌ 未找到300781的数据")
                
            # 显示前5条数据作为示例
            print("\n📋 前5条数据示例:")
            print(data.head()[['代码', '名称', '最新价', '涨跌幅']].to_string())
            
        else:
            print("❌ 获取到的数据为空")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_akshare_realtime()