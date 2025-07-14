#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试九转序列计算问题
分析为什么7月14日没有显示红色数字9
"""

import requests
import json
from datetime import datetime

def debug_nine_turn():
    """调试九转序列计算"""
    try:
        # 获取股票数据
        response = requests.get('http://localhost:8080/api/stock/000001/realtime', timeout=10)
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
            
        print(f"API响应状态码: {response.status_code}")
        print(f"API响应内容: {response.text[:500]}...")  # 只显示前500个字符
        data = response.json()
        kline_data = data.get('kline_data', [])
        
        if not kline_data:
            print("没有K线数据")
            return
            
        print("=== 九转序列调试分析 ===")
        print(f"总共有 {len(kline_data)} 条K线数据")
        print()
        
        # 显示最近15天的数据
        print("最近15天的K线数据:")
        recent_data = kline_data[-15:] if len(kline_data) >= 15 else kline_data
        
        for i, item in enumerate(recent_data):
            date = item['trade_date']
            close = float(item['close'])
            nine_up = item.get('nine_turn_up', 0)
            nine_down = item.get('nine_turn_down', 0)
            
            print(f"{i+1:2d}. {date}: 收盘={close:6.2f}, 红九转={nine_up}, 绿九转={nine_down}")
        
        print()
        
        # 手动验证九转序列计算逻辑
        print("=== 手动验证九转序列计算 ===")
        
        # 找到最后10天的数据进行分析
        last_10 = kline_data[-10:] if len(kline_data) >= 10 else kline_data
        
        print("检查卖出Setup条件（红色九转）:")
        print("条件: 当日收盘价 > 4个交易日前的收盘价")
        print()
        
        for i in range(4, len(last_10)):
            current = last_10[i]
            four_days_ago = last_10[i-4]
            
            current_close = float(current['close'])
            four_days_ago_close = float(four_days_ago['close'])
            
            condition_met = current_close > four_days_ago_close
            
            print(f"{current['trade_date']}: {current_close:6.2f} > {four_days_ago_close:6.2f} ({four_days_ago['trade_date']}) = {condition_met}")
        
        print()
        
        # 分析7月14日的具体情况
        if len(kline_data) >= 5:
            latest = kline_data[-1]  # 7月14日
            four_days_ago = kline_data[-5]  # 7月10日
            
            latest_close = float(latest['close'])
            four_days_ago_close = float(four_days_ago['close'])
            
            print("=== 7月14日详细分析 ===")
            print(f"7月14日收盘价: {latest_close}")
            print(f"7月10日收盘价: {four_days_ago_close}")
            print(f"条件满足: {latest_close} > {four_days_ago_close} = {latest_close > four_days_ago_close}")
            print(f"当前九转值: {latest.get('nine_turn_up', 0)}")
            
            if latest_close > four_days_ago_close:
                print("✅ 条件满足，应该继续九转序列")
                
                # 检查前面的连续性
                print("\n检查前面的连续性:")
                consecutive_count = 0
                for i in range(len(kline_data)-1, 3, -1):  # 从最新往前检查
                    current = kline_data[i]
                    four_days_before = kline_data[i-4]
                    
                    current_close = float(current['close'])
                    four_days_before_close = float(four_days_before['close'])
                    
                    if current_close > four_days_before_close:
                        consecutive_count += 1
                        print(f"{current['trade_date']}: ✅ 连续第{consecutive_count}天")
                    else:
                        print(f"{current['trade_date']}: ❌ 条件中断")
                        break
                
                print(f"\n连续满足条件的天数: {consecutive_count}")
                
                if consecutive_count >= 9:
                    print("🔴 应该显示红色数字9！")
                elif consecutive_count >= 4:
                    print(f"🔴 应该显示红色数字{consecutive_count}")
                else:
                    print("⚪ 连续天数不足4天，不显示")
            else:
                print("❌ 条件不满足，九转序列中断")
        
        print()
        print("=== 可能的问题原因 ===")
        print("1. 数据更新时间问题 - 7月14日数据可能还未完全更新")
        print("2. 计算逻辑中的边界条件处理")
        print("3. 数据源的日期格式或时区问题")
        print("4. 九转序列重置逻辑的触发")
        
    except Exception as e:
        print(f"调试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_nine_turn()