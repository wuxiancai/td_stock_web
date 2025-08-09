#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试批量实时数据内容
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_sina_batch_realtime_data
from datetime import datetime

def main():
    print("批量实时数据测试")
    print("测试时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 60)
    
    try:
        # 获取批量实时数据
        batch_data = get_sina_batch_realtime_data()
        
        if batch_data is not None and not batch_data.empty:
            print(f"✅ 批量数据获取成功，共{len(batch_data)}只股票")
            print("\n当前批量数据包含的股票列表:")
            print("-" * 60)
            
            for idx, row in batch_data.iterrows():
                code = row['代码']
                name = row['名称']
                price = row['最新价']
                change_pct = row['涨跌幅']
                market_cap = row['总市值']
                
                print(f"{idx+1:2d}. {code} {name:8s} 价格:{price:7.2f} 涨跌:{change_pct:6.2f}% 市值:{market_cap:8.2f}亿")
            
            print("-" * 60)
            
            # 查找300101
            stock_300101 = batch_data[batch_data['代码'] == '300101']
            
            if not stock_300101.empty:
                print("\n✅ 在批量数据中找到300101:")
                row = stock_300101.iloc[0]
                print("详细数据:")
                for col in batch_data.columns:
                    value = row[col]
                    if isinstance(value, float):
                        print(f"  {col}: {value:.4f}")
                    else:
                        print(f"  {col}: {value}")
            else:
                print("\n❌ 批量数据中未找到300101")
                print("300101不在当前的热门股票列表中")
                
        else:
            print("❌ 批量数据获取失败")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()