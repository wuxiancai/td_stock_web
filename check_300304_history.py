#!/usr/bin/env python3
import requests
import json

def check_300304_history():
    """检查300304的历史数据，验证前收盘价"""
    
    print("=== 检查300304历史数据 ===")
    
    try:
        # 获取K线数据
        response = requests.get('http://localhost:8080/api/stock/300304/kline?period=daily&limit=5')
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                kline_data = data['data']
                print(f"\n最近5天K线数据:")
                for i, item in enumerate(kline_data[-5:]):
                    date = item.get('trade_date', 'N/A')
                    open_price = item.get('open', 0)
                    close_price = item.get('close', 0)
                    adj_ratio = item.get('adj_ratio', 1.0)
                    is_adjusted = item.get('is_adjusted', False)
                    
                    # 计算原始价格
                    if is_adjusted and adj_ratio != 0:
                        original_open = open_price / adj_ratio
                        original_close = close_price / adj_ratio
                    else:
                        original_open = open_price
                        original_close = close_price
                    
                    print(f"日期: {date}")
                    print(f"  复权价格 - 开盘: {open_price:.2f}, 收盘: {close_price:.2f}")
                    print(f"  原始价格 - 开盘: {original_open:.2f}, 收盘: {original_close:.2f}")
                    print(f"  复权比例: {adj_ratio:.6f}, 是否复权: {is_adjusted}")
                    
                    # 计算涨跌幅
                    if i > 0:
                        prev_item = kline_data[-5:][i-1]
                        prev_close = prev_item.get('close', 0)
                        prev_adj_ratio = prev_item.get('adj_ratio', 1.0)
                        prev_is_adjusted = prev_item.get('is_adjusted', False)
                        
                        if prev_is_adjusted and prev_adj_ratio != 0:
                            prev_original_close = prev_close / prev_adj_ratio
                        else:
                            prev_original_close = prev_close
                        
                        change_percent = ((original_close - prev_original_close) / prev_original_close) * 100
                        print(f"  涨跌幅: {change_percent:.2f}% (相对于前一日原始收盘价 {prev_original_close:.2f})")
                    print()
                
                # 检查最新两天的数据
                if len(kline_data) >= 2:
                    today = kline_data[-1]
                    yesterday = kline_data[-2]
                    
                    today_adj_ratio = today.get('adj_ratio', 1.0)
                    yesterday_adj_ratio = yesterday.get('adj_ratio', 1.0)
                    
                    today_original_close = today.get('close', 0) / today_adj_ratio if today_adj_ratio != 0 else today.get('close', 0)
                    yesterday_original_close = yesterday.get('close', 0) / yesterday_adj_ratio if yesterday_adj_ratio != 0 else yesterday.get('close', 0)
                    
                    print(f"关键数据对比:")
                    print(f"昨日原始收盘价: {yesterday_original_close:.2f}")
                    print(f"今日原始收盘价: {today_original_close:.2f}")
                    
                    # 如果当前价格是8.93，计算相对于不同前收盘价的涨跌幅
                    current_price = 8.93
                    print(f"\n当前价格 {current_price} 相对于不同前收盘价的涨跌幅:")
                    print(f"相对于昨日原始收盘价 {yesterday_original_close:.2f}: {((current_price - yesterday_original_close) / yesterday_original_close * 100):.2f}%")
                    print(f"相对于今日原始收盘价 {today_original_close:.2f}: {((current_price - today_original_close) / today_original_close * 100):.2f}%")
                    
                    # 反推：如果涨跌幅是-1.54%，前收盘价应该是多少
                    target_change = -1.54
                    calculated_pre_close = current_price / (1 + target_change / 100)
                    print(f"如果涨跌幅是 {target_change}%，前收盘价应该是: {calculated_pre_close:.2f}")
            else:
                print("获取K线数据失败")
        else:
            print(f"请求失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"检查历史数据时出错: {e}")

if __name__ == "__main__":
    check_300304_history()