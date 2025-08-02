#!/usr/bin/env python3
import pandas as pd
import numpy as np
import sys
import os

# 添加当前目录到Python路径
sys.path.append('/Users/wuxiancai/td_stock_web')

# 导入应用程序的函数
from app import calculate_ema15

# 创建测试数据
test_data = {
    'ts_code': ['300520.SZ'] * 30,
    'trade_date': [f'2025070{i:02d}' if i <= 9 else f'20250{i:02d}' for i in range(1, 31)],
    'close': [20 + i * 0.1 for i in range(30)]  # 简单的递增价格
}

df = pd.DataFrame(test_data)
print("原始数据:")
print(df[['trade_date', 'close']].head(10))

# 计算EMA15
result = calculate_ema15(df)
print("\n计算EMA15后:")
print(result[['trade_date', 'close', 'ema15']].head(20))

# 检查是否有非空的EMA15值
non_null_ema15 = result['ema15'].dropna()
print(f"\n非空EMA15值数量: {len(non_null_ema15)}")
if len(non_null_ema15) > 0:
    print(f"EMA15值范围: {non_null_ema15.min():.4f} - {non_null_ema15.max():.4f}")
