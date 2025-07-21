#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证AkShare获取的股票300304历史数据
"""

import akshare as ak
import pandas as pd

def check_300304_data():
    """检查股票300304的历史数据"""
    print("=== 验证股票300304 (20250717) 的收盘价 ===")
    
    try:
        # 获取股票300304的历史数据
        print("正在获取股票300304的历史数据...")
        stock_data = ak.stock_zh_a_hist(symbol="300304", period="daily", start_date="20250715", end_date="20250718", adjust="")
        
        print(f"获取到 {len(stock_data)} 条数据")
        print("\n最近几天的数据:")
        print(stock_data.to_string())
        
        # 查找20250717的数据
        target_date = "2025-07-17"
        # 转换日期列为字符串进行比较
        stock_data['日期_str'] = stock_data['日期'].astype(str)
        target_data = stock_data[stock_data['日期_str'] == target_date]
        
        if not target_data.empty:
            close_price = target_data.iloc[0]['收盘']
            print(f"\n=== 关键结果 ===")
            print(f"股票300304在{target_date}的收盘价: {close_price}")
            print(f"期望收盘价: 9.07")
            print(f"是否匹配: {'是' if abs(close_price - 9.07) < 0.01 else '否'}")
            
            if abs(close_price - 9.07) < 0.01:
                print("\n✅ 结论: AkShare历史数据返回的是原始价格，无需复权处理！")
            else:
                print(f"\n❌ 结论: AkShare历史数据可能已经复权，实际收盘价: {close_price}")
        else:
            print(f"\n❌ 未找到{target_date}的数据")
            
    except Exception as e:
        print(f"获取数据失败: {e}")

if __name__ == "__main__":
    check_300304_data()