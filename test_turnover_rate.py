#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tushare as ts
import pandas as pd
from datetime import datetime, timedelta

# 初始化tushare
ts.set_token('68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019')
pro = ts.pro_api()

def test_turnover_rate():
    """测试换手率数据获取"""
    print("测试换手率数据获取...")
    
    # 测试几个股票代码
    test_codes = ['300084.SZ', '000001.SZ', '600036.SH']
    
    for ts_code in test_codes:
        print(f"\n测试股票: {ts_code}")
        
        # 获取最近几天的daily_basic数据
        for i in range(5):
            try:
                check_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                print(f"  检查日期: {check_date}")
                
                daily_basic = pro.daily_basic(ts_code=ts_code, trade_date=check_date)
                
                if not daily_basic.empty:
                    turnover_rate = daily_basic.iloc[0]['turnover_rate']
                    volume_ratio = daily_basic.iloc[0]['volume_ratio']
                    pe_ttm = daily_basic.iloc[0]['pe_ttm']
                    total_mv = daily_basic.iloc[0]['total_mv']
                    
                    print(f"    换手率: {turnover_rate}%")
                    print(f"    量比: {volume_ratio}")
                    print(f"    市盈率: {pe_ttm}")
                    print(f"    总市值: {total_mv}万元")
                    break
                else:
                    print(f"    {check_date} 无数据")
            except Exception as e:
                print(f"    {check_date} 获取失败: {e}")
        else:
            print(f"  {ts_code} 最近5天都无daily_basic数据")
    
    # 测试获取最新交易日的所有股票换手率数据
    print("\n测试获取最新交易日的换手率数据...")
    try:
        latest_date = datetime.now().strftime('%Y%m%d')
        print(f"查询日期: {latest_date}")
        
        # 获取少量股票的数据进行测试
        daily_basic_all = pro.daily_basic(trade_date=latest_date, limit=10)
        
        if not daily_basic_all.empty:
            print(f"获取到 {len(daily_basic_all)} 条记录")
            print("前5条记录的换手率:")
            for i, row in daily_basic_all.head().iterrows():
                print(f"  {row['ts_code']}: {row['turnover_rate']}%")
        else:
            print(f"  {latest_date} 无daily_basic数据")
            
            # 尝试前一天
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            print(f"尝试前一天: {yesterday}")
            daily_basic_all = pro.daily_basic(trade_date=yesterday, limit=10)
            
            if not daily_basic_all.empty:
                print(f"获取到 {len(daily_basic_all)} 条记录")
                print("前5条记录的换手率:")
                for i, row in daily_basic_all.head().iterrows():
                    print(f"  {row['ts_code']}: {row['turnover_rate']}%")
            else:
                print(f"  {yesterday} 也无daily_basic数据")
                
    except Exception as e:
        print(f"获取最新交易日数据失败: {e}")

if __name__ == '__main__':
    test_turnover_rate()