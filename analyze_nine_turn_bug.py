#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析九转序列计算逻辑的问题
重现计算过程，找出为什么7月14日显示为0
"""

import requests
import json
from datetime import datetime
import pandas as pd

def analyze_nine_turn_bug():
    """分析九转序列计算逻辑的问题"""
    try:
        # 获取股票数据
        response = requests.get('http://localhost:8080/api/stock/000001/realtime', timeout=10)
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
            
        data = response.json()
        kline_data = data.get('kline_data', [])
        
        if not kline_data:
            print("没有K线数据")
            return
            
        print("=== 九转序列计算逻辑分析 ===")
        print(f"总共有 {len(kline_data)} 条K线数据")
        print()
        
        # 转换为DataFrame进行分析
        df = pd.DataFrame(kline_data)
        df['close'] = df['close'].astype(float)
        
        print("最近15天的数据:")
        recent_data = df.tail(15)
        for i, (idx, row) in enumerate(recent_data.iterrows()):
            print(f"{i+1:2d}. {row['trade_date']}: 收盘={row['close']:6.2f}, 红九转={row['nine_turn_up']}, 绿九转={row['nine_turn_down']}")
        
        print()
        print("=== 手动重现九转序列计算逻辑 ===")
        
        # 模拟卖出Setup计算过程
        up_count = 0
        up_positions = []
        
        print("卖出Setup计算过程:")
        for i in range(4, len(df)):
            current_close = df.iloc[i]['close']
            four_days_ago_close = df.iloc[i-4]['close']
            condition_met = current_close > four_days_ago_close
            
            if condition_met:
                up_count += 1
                up_positions.append(i)
                
                # 显示计算过程
                if i >= len(df) - 15:  # 只显示最近15天的计算过程
                    print(f"第{i+1}天 ({df.iloc[i]['trade_date']}): {current_close:6.2f} > {four_days_ago_close:6.2f} ✅ 连续第{up_count}天")
                    
                    if up_count >= 4:
                        print(f"  -> 应该显示序列号: {[j+1 for j in range(min(len(up_positions), 9))]}")
                        print(f"  -> 当前位置应该显示: {min(up_count, 9)}")
                
                # 如果达到9个，重置
                if up_count >= 9:
                    print(f"  -> Setup完成，重置计数")
                    up_count = 0
                    up_positions = []
            else:
                # 条件中断
                if up_count > 0:
                    if i >= len(df) - 15:  # 只显示最近15天的计算过程
                        print(f"第{i+1}天 ({df.iloc[i]['trade_date']}): {current_close:6.2f} <= {four_days_ago_close:6.2f} ❌ 条件中断，清除所有标记")
                        print(f"  -> 之前的{up_count}个位置的标记被清除")
                    up_count = 0
                    up_positions = []
                elif i >= len(df) - 15:
                    print(f"第{i+1}天 ({df.iloc[i]['trade_date']}): {current_close:6.2f} <= {four_days_ago_close:6.2f} ❌ 条件不满足")
        
        print()
        print("=== 问题分析 ===")
        
        # 检查最后几天的情况
        last_day_idx = len(df) - 1
        last_day = df.iloc[last_day_idx]
        
        print(f"最后一天 (7月14日): {last_day['trade_date']}")
        print(f"收盘价: {last_day['close']}")
        print(f"当前九转值: {last_day['nine_turn_up']}")
        
        # 检查是否有后续的条件中断
        print("\n检查是否有条件中断:")
        
        # 从7月14日往后检查（如果有数据的话）
        # 由于7月14日是最后一天，我们需要检查计算逻辑
        
        # 重新计算，看看问题出在哪里
        print("\n=== 重新计算九转序列 ===")
        
        # 手动实现九转序列计算
        df_test = df.copy()
        df_test['nine_turn_up_manual'] = 0
        
        up_count = 0
        up_positions = []
        
        for i in range(4, len(df_test)):
            current_close = df_test.iloc[i]['close']
            four_days_ago_close = df_test.iloc[i-4]['close']
            
            if current_close > four_days_ago_close:
                up_count += 1
                up_positions.append(i)
                
                # 当达到4个时开始显示序列号
                if up_count >= 4:
                    for j, pos in enumerate(up_positions):
                        if j < 9:  # 最多显示9个
                            df_test.iloc[pos, df_test.columns.get_loc('nine_turn_up_manual')] = j + 1
                
                # 如果达到9个，重置
                if up_count >= 9:
                    up_count = 0
                    up_positions = []
            else:
                # 如果中断，清除所有标记
                for pos in up_positions:
                    df_test.iloc[pos, df_test.columns.get_loc('nine_turn_up_manual')] = 0
                up_count = 0
                up_positions = []
        
        print("手动计算结果对比:")
        recent_test = df_test.tail(10)
        for i, (idx, row) in enumerate(recent_test.iterrows()):
            print(f"{row['trade_date']}: 原始={row['nine_turn_up']:2d}, 手动={row['nine_turn_up_manual']:2d}")
        
        print()
        print("=== 结论 ===")
        print("问题可能的原因:")
        print("1. 九转序列计算逻辑中，当条件中断时会清除所有之前的标记")
        print("2. 可能在7月14日之后有数据更新，导致条件中断")
        print("3. 数据更新的时间顺序问题")
        print("4. 计算函数在某个位置被重复调用，导致标记被清除")
        
    except Exception as e:
        print(f"分析过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_nine_turn_bug()