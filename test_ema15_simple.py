#!/usr/bin/env python3
import pandas as pd
import numpy as np

def clean_float_precision(value, decimal_places=2):
    """简化版的clean_float_precision函数"""
    try:
        if value is None or pd.isna(value):
            return 0.0
        float_value = float(value)
        if not np.isfinite(float_value):
            return 0.0
        return float_value
    except (ValueError, TypeError):
        return 0.0

def calculate_ema15(df, period=15):
    """简化版的EMA15计算函数"""
    df = df.copy()
    
    # 计算EMA15
    df['ema15'] = df['close'].ewm(span=period, min_periods=1).mean()
    
    # 应用精度修复
    df['ema15'] = df['ema15'].apply(lambda x: clean_float_precision(x, 4))
    
    return df

# 创建测试数据，模拟真实的股票数据格式
test_data = {
    'ts_code': ['300520.SZ'] * 20,
    'trade_date': ['20250701', '20250702', '20250703', '20250704', '20250705',
                   '20250708', '20250709', '20250710', '20250711', '20250712',
                   '20250715', '20250716', '20250717', '20250718', '20250719',
                   '20250722', '20250723', '20250724', '20250725', '20250726'],
    'open': [24.5, 24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4,
             25.5, 25.6, 25.7, 25.8, 25.9, 26.0, 26.1, 26.2, 26.3, 26.4],
    'close': [24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4, 25.5,
              25.6, 25.7, 25.8, 25.9, 26.0, 26.1, 26.2, 26.3, 26.4, 26.5],
    'high': [24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7,
             25.8, 25.9, 26.0, 26.1, 26.2, 26.3, 26.4, 26.5, 26.6, 26.7],
    'low': [24.4, 24.5, 24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3,
            25.4, 25.5, 25.6, 25.7, 25.8, 25.9, 26.0, 26.1, 26.2, 26.3],
    'vol': [1000] * 20,
    'amount': [25000] * 20
}

df = pd.DataFrame(test_data)
print("原始数据:")
print(df[['trade_date', 'close']].head(10))

# 计算EMA15
result = calculate_ema15(df)
print("\n计算EMA15后:")
print(result[['trade_date', 'close', 'ema15']].tail(10))

# 模拟JSON序列化过程
data_list = []
for _, row in result.iterrows():
    data_list.append({
        'ts_code': row['ts_code'],
        'trade_date': row['trade_date'],
        'close': float(row['close']) if pd.notna(row['close']) else None,
        'ema15': float(row['ema15']) if pd.notna(row['ema15']) else None
    })

print("\nJSON序列化后的最后5条数据:")
for item in data_list[-5:]:
    print(f"日期: {item['trade_date']}, 收盘: {item['close']}, EMA15: {item['ema15']}")

# 检查是否有None值
none_count = sum(1 for item in data_list if item['ema15'] is None)
print(f"\nEMA15为None的数量: {none_count}")