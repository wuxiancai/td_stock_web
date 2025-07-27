#!/usr/bin/env python3
"""
测试九转序列重置逻辑
验证当完成1-9序列后是否正确重置
"""

import requests
import json

def test_nine_turn_reset():
    """测试九转序列重置功能"""
    
    # 获取九转数据
    url = "http://127.0.0.1:8080/api/stock/300354/nine_turn?days=200&freq=daily"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                nine_turn_data = data['data']
                stock_info = data['stock_info']
                
                print(f"股票: {stock_info['name']} ({stock_info['ts_code']})")
                print(f"总记录数: {stock_info['total_records']}")
                print(f"买入信号总数: {stock_info['buy_signals']}")
                print(f"卖出信号总数: {stock_info['sell_signals']}")
                print(f"完整买入序列: {stock_info['complete_buy_turns']}")
                print(f"完整卖出序列: {stock_info['complete_sell_turns']}")
                print("-" * 50)
                
                # 检查是否有连续的9出现
                buy_nines = []
                sell_nines = []
                
                for i, record in enumerate(nine_turn_data):
                    if record['buy_signal'] == 9:
                        buy_nines.append((i, record['trade_date']))
                    if record['sell_signal'] == 9:
                        sell_nines.append((i, record['trade_date']))
                
                print(f"买入信号第9天出现位置:")
                for idx, date in buy_nines:
                    print(f"  索引 {idx}: {date}")
                
                print(f"卖出信号第9天出现位置:")
                for idx, date in sell_nines:
                    print(f"  索引 {idx}: {date}")
                
                # 检查是否有连续的9（这应该不存在）
                print("\n检查连续9的情况:")
                consecutive_buy_nines = []
                consecutive_sell_nines = []
                
                for i in range(len(buy_nines) - 1):
                    if buy_nines[i+1][0] - buy_nines[i][0] == 1:
                        consecutive_buy_nines.append((buy_nines[i], buy_nines[i+1]))
                
                for i in range(len(sell_nines) - 1):
                    if sell_nines[i+1][0] - sell_nines[i][0] == 1:
                        consecutive_sell_nines.append((sell_nines[i], sell_nines[i+1]))
                
                if consecutive_buy_nines:
                    print(f"❌ 发现连续买入9: {consecutive_buy_nines}")
                else:
                    print("✅ 没有连续买入9，重置逻辑正确")
                
                if consecutive_sell_nines:
                    print(f"❌ 发现连续卖出9: {consecutive_sell_nines}")
                else:
                    print("✅ 没有连续卖出9，重置逻辑正确")
                
                # 显示最近几个有信号的记录
                print("\n最近10个有信号的记录:")
                recent_signals = []
                for record in nine_turn_data[-50:]:  # 查看最近50个记录
                    if record['buy_signal'] > 0 or record['sell_signal'] > 0:
                        recent_signals.append(record)
                
                for record in recent_signals[-10:]:  # 显示最近10个
                    buy_sig = record['buy_signal'] if record['buy_signal'] > 0 else ""
                    sell_sig = record['sell_signal'] if record['sell_signal'] > 0 else ""
                    print(f"  {record['trade_date']}: 买入={buy_sig}, 卖出={sell_sig}")
                
            else:
                print(f"API返回错误: {data}")
        else:
            print(f"HTTP错误: {response.status_code}")
            
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    test_nine_turn_reset()