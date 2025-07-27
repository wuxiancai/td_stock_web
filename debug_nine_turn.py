#!/usr/bin/env python3
"""
调试九转序列数据的脚本
"""
import requests
import json

def debug_nine_turn_data():
    try:
        # 获取股票数据
        response = requests.get('http://localhost:8080/api/stock/300354')
        if response.status_code != 200:
            print(f"API请求失败: {response.status_code}")
            return
        
        data = response.json()
        kline_data = data.get('kline_data', [])
        
        print(f"总共有 {len(kline_data)} 条K线数据")
        print()
        
        # 查看最后20条数据的九转序列值
        print("最后20条数据的九转序列值:")
        for i, item in enumerate(kline_data[-20:]):
            idx = len(kline_data) - 20 + i
            nine_up = item.get('nine_turn_up', 0)
            nine_down = item.get('nine_turn_down', 0)
            countdown_up = item.get('countdown_up', 0)
            countdown_down = item.get('countdown_down', 0)
            
            if nine_up > 0 or nine_down > 0 or countdown_up > 0 or countdown_down > 0:
                print(f"索引 {idx}: nine_turn_up={nine_up}, nine_turn_down={nine_down}, countdown_up={countdown_up}, countdown_down={countdown_down}")
                print(f"  -> 日期: {item.get('trade_date', 'N/A')}, 收盘价: {item.get('close', 'N/A')}")
        
        # 查找所有有九转序列值的数据
        print()
        print("所有有九转序列值的数据:")
        count = 0
        for i, item in enumerate(kline_data):
            nine_up = item.get('nine_turn_up', 0)
            nine_down = item.get('nine_turn_down', 0)
            countdown_up = item.get('countdown_up', 0)
            countdown_down = item.get('countdown_down', 0)
            
            if nine_up > 0 or nine_down > 0 or countdown_up > 0 or countdown_down > 0:
                count += 1
                print(f"索引 {i}: nine_turn_up={nine_up}, nine_turn_down={nine_down}, countdown_up={countdown_up}, countdown_down={countdown_down}")
                print(f"  -> 日期: {item.get('trade_date', 'N/A')}, 收盘价: {item.get('close', 'N/A')}")
                if count > 30:  # 限制输出数量
                    print("... (更多数据)")
                    break
        
        # 检查是否有异常大的值（可能是索引）
        print()
        print("检查异常值:")
        for i, item in enumerate(kline_data):
            nine_up = item.get('nine_turn_up', 0)
            nine_down = item.get('nine_turn_down', 0)
            countdown_up = item.get('countdown_up', 0)
            countdown_down = item.get('countdown_down', 0)
            
            # 九转序列值应该在1-9之间，Countdown应该在1-13之间
            if nine_up > 9 or nine_down > 9 or countdown_up > 13 or countdown_down > 13:
                print(f"异常值在索引 {i}: nine_turn_up={nine_up}, nine_turn_down={nine_down}, countdown_up={countdown_up}, countdown_down={countdown_down}")
                print(f"  -> 日期: {item.get('trade_date', 'N/A')}, 收盘价: {item.get('close', 'N/A')}")
                
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    debug_nine_turn_data()