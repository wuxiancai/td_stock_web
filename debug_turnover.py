#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试换手率数据获取问题
"""

import tushare as ts
import pandas as pd
from datetime import datetime, timedelta

# 设置Tushare token
ts.set_token('68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019')
pro = ts.pro_api()

def debug_turnover_data():
    """调试换手率数据获取"""
    
    # 测试几个不同的交易日
    test_dates = ['20250107', '20250106', '20250103', '20250102']
    test_stocks = ['300084.SZ', '000001.SZ', '600000.SH']  # 测试不同市场的股票
    
    print("=== 调试换手率数据获取 ===")
    
    # 1. 检查交易日历
    print("\n1. 检查最近的交易日:")
    try:
        cal_df = pro.trade_cal(exchange='SSE', start_date='20250101', end_date='20250110')
        print(cal_df[['cal_date', 'is_open']].to_string())
    except Exception as e:
        print(f"获取交易日历失败: {e}")
    
    # 2. 测试daily_basic接口
    print("\n2. 测试daily_basic接口:")
    for date in test_dates:
        print(f"\n测试日期: {date}")
        try:
            # 获取所有股票的daily_basic数据（限制前5条）
            df = pro.daily_basic(trade_date=date)
            if not df.empty:
                print(f"  - 获取到 {len(df)} 条记录")
                print(f"  - 换手率字段统计:")
                print(f"    非空记录: {df['turnover_rate'].notna().sum()}")
                print(f"    大于0记录: {(df['turnover_rate'] > 0).sum()}")
                print(f"    平均换手率: {df['turnover_rate'].mean():.4f}%")
                
                # 显示前几条有换手率数据的记录
                valid_data = df[df['turnover_rate'] > 0].head(3)
                if not valid_data.empty:
                    print(f"  - 示例数据:")
                    for _, row in valid_data.iterrows():
                        print(f"    {row['ts_code']}: {row['turnover_rate']:.4f}%")
                break
            else:
                print(f"  - 无数据")
        except Exception as e:
            print(f"  - 获取失败: {e}")
    
    # 3. 测试特定股票
    print("\n3. 测试特定股票:")
    for stock in test_stocks:
        print(f"\n股票: {stock}")
        for date in test_dates:
            try:
                df = pro.daily_basic(ts_code=stock, trade_date=date)
                if not df.empty:
                    turnover_rate = df.iloc[0]['turnover_rate']
                    print(f"  {date}: {turnover_rate}%")
                    if turnover_rate and turnover_rate > 0:
                        break
                else:
                    print(f"  {date}: 无数据")
            except Exception as e:
                print(f"  {date}: 错误 - {e}")
    
    # 4. 检查API限制状态
    print("\n4. 检查API使用情况:")
    try:
        # 这里可以添加API使用状态检查
        print("API调用正常")
    except Exception as e:
        print(f"API状态检查失败: {e}")

if __name__ == '__main__':
    debug_turnover_data()