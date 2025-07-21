#!/usr/bin/env python3
import requests
import json

# 获取300304的实时数据
response = requests.get("http://localhost:8080/api/stock/300304/realtime")
data = response.json()

# 分析K线数据
kline = data['kline_data'][-1]  # 最新K线
prev_kline = data['kline_data'][-2]  # 前一日K线

print('=== 300304 云意电气 数据分析 ===')
print()

print('最新K线数据 (今日):')
print(f'日期: {kline["trade_date"]}')
print(f'复权因子 adj_factor: {kline["adj_factor"]}')
print(f'复权比例 adj_ratio: {kline["adj_ratio"]}')
print(f'复权后收盘价: {kline["close"]}')
print(f'原始收盘价: {kline["close"] / kline["adj_ratio"]:.2f}')

print()
print('前一日K线数据 (昨日):')
print(f'日期: {prev_kline["trade_date"]}')
print(f'复权因子 adj_factor: {prev_kline["adj_factor"]}')
print(f'复权比例 adj_ratio: {prev_kline["adj_ratio"]}')
print(f'复权后收盘价: {prev_kline["close"]}')
print(f'原始收盘价: {prev_kline["close"] / prev_kline["adj_ratio"]:.2f}')

print()
print('实时数据:')
spot = data['spot']
print(f'当前价格: {spot["latest_price"]}')
print(f'前收盘价: {spot["pre_close"]:.4f}')
print(f'涨跌幅: {spot["change_percent"]:.2f}%')

print()
print('正确计算:')
# 昨日原始收盘价
yesterday_original_close = prev_kline["close"] / prev_kline["adj_ratio"]
# 今日分时价格（原始价格）
current_price = spot["latest_price"]
# 正确涨跌幅
correct_change_percent = ((current_price - yesterday_original_close) / yesterday_original_close) * 100

print(f'昨日原始收盘价: {yesterday_original_close:.2f}')
print(f'今日当前价格: {current_price}')
print(f'正确涨跌幅: {correct_change_percent:.2f}%')

print()
print('检查今日K线数据:')
print(f'今日原始收盘价: {kline["close"] / kline["adj_ratio"]:.2f}')
print(f'今日复权收盘价: {kline["close"]:.2f}')

print()
print('分析问题:')
print(f'API返回的前收盘价: {spot["pre_close"]:.2f}')
print(f'计算得出的昨日原始收盘价: {yesterday_original_close:.2f}')
print(f'差异: {abs(spot["pre_close"] - yesterday_original_close):.4f}')

# 检查是否应该使用今日K线的前收盘价
if 'pre_close' in kline:
    print(f'今日K线中的前收盘价: {kline.get("pre_close", "无数据")}')

# 尝试其他可能的前收盘价来源
print()
print('尝试不同的前收盘价计算:')
# 方法1：使用今日K线的开盘价作为参考
if 'open' in kline:
    today_original_open = kline["open"] / kline["adj_ratio"]
    print(f'今日原始开盘价: {today_original_open:.2f}')

# 方法2：检查是否有其他字段
print('K线数据字段:', list(kline.keys()))