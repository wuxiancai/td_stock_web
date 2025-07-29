#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Tushare获取上证指数数据
"""

import os
import pandas as pd
from datetime import datetime, timedelta

def test_tushare_shanghai():
    """测试Tushare获取上证指数数据"""
    try:
        import tushare as ts
        
        # 使用应用程序中的token
        tushare_token = '68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019'
        
        ts.set_token(tushare_token)
        pro = ts.pro_api()
        
        print("=== Tushare 上证指数详细数据 ===")
        
        # 获取最近10天的数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
        
        print(f"查询日期范围: {start_date} 到 {end_date}")
        
        # 获取上证指数数据
        df = pro.index_daily(ts_code='000001.SH', start_date=start_date, end_date=end_date)
        
        if df is not None and not df.empty:
            # 按日期降序排序
            df = df.sort_values('trade_date', ascending=False)
            
            print("\n上证指数最近几天的数据:")
            print("日期\t\t收盘价\t\t涨跌额\t\t涨跌幅\t\t成交额(亿)")
            print("-" * 70)
            
            for _, row in df.head(10).iterrows():
                trade_date = row['trade_date']
                close_price = row['close']
                change = row['change'] if pd.notna(row['change']) else 0
                pct_chg = row['pct_chg'] if pd.notna(row['pct_chg']) else 0
                amount = row['amount'] / 10 if pd.notna(row['amount']) else 0
                
                print(f"{trade_date}\t{close_price:.2f}\t\t{change:.2f}\t\t{pct_chg:.2f}%\t\t{amount:.2f}")
            
            # 检查2025-07-28的数据
            target_date = '20250728'
            target_row = df[df['trade_date'] == target_date]
            
            if not target_row.empty:
                row = target_row.iloc[0]
                print(f"\n=== 2025-07-28 上证指数数据 ===")
                print(f"收盘价: {row['close']:.2f}")
                print(f"涨跌额: {row['change']:.2f}")
                print(f"涨跌幅: {row['pct_chg']:.2f}%")
                print(f"成交额: {row['amount'] / 10:.2f}亿")
                print(f"最高价: {row['high']:.2f}")
                print(f"最低价: {row['low']:.2f}")
                print(f"开盘价: {row['open']:.2f}")
                
                # 与缓存数据对比
                cached_price = 3589.27
                tushare_price = row['close']
                difference = tushare_price - cached_price
                
                print(f"\n=== 数据对比 ===")
                print(f"缓存价格: {cached_price:.2f}")
                print(f"Tushare价格: {tushare_price:.2f}")
                print(f"差异: {difference:.2f} 点")
                print(f"用户报告正确价格: 3597.94")
                print(f"与用户报告差异: {3597.94 - tushare_price:.2f} 点")
                
            else:
                print(f"\n未找到 {target_date} 的数据")
                
        else:
            print("未获取到任何数据")
            
    except ImportError:
        print("Tushare 未安装")
    except Exception as e:
        print(f"Tushare 获取数据失败: {e}")

if __name__ == "__main__":
    test_tushare_shanghai()