#!/usr/bin/env python3
"""
直接测试EMA15计算的脚本
"""

import pandas as pd
import numpy as np
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def clean_float_precision(value, precision=4):
    """清理浮点数精度"""
    if pd.isna(value) or value is None:
        return None
    try:
        if isinstance(value, (int, float)) and not np.isnan(value) and not np.isinf(value):
            return round(float(value), precision)
        return None
    except (ValueError, TypeError, OverflowError):
        return None

def calculate_ema15(df, period=15):
    """
    计算EMA15指数移动平均线
    """
    try:
        print(f"[EMA15] 开始计算，输入数据形状: {df.shape}")
        
        # 检查是否有close列
        if 'close' not in df.columns:
            print("[EMA15] 错误：数据中没有close列")
            df['ema15'] = None
            return df
        
        # 检查有效的收盘价数据
        valid_close_count = df['close'].notna().sum()
        print(f"[EMA15] 有效收盘价数据数量: {valid_close_count}/{len(df)}")
        
        if valid_close_count == 0:
            print("[EMA15] 错误：没有有效的收盘价数据")
            df['ema15'] = None
            return df
        
        # 计算EMA15
        df['ema15'] = df['close'].ewm(span=period, min_periods=1).mean()
        
        # 检查计算结果
        valid_ema15_count = df['ema15'].notna().sum()
        print(f"[EMA15] 计算完成，有效EMA15数据数量: {valid_ema15_count}/{len(df)}")
        
        # 修复精度
        df['ema15'] = df['ema15'].apply(lambda x: clean_float_precision(x, 4))
        
        # 检查精度修复后的结果
        final_valid_count = df['ema15'].notna().sum()
        print(f"[EMA15] 精度修复后，有效EMA15数据数量: {final_valid_count}/{len(df)}")
        
        # 显示EMA15值的范围
        valid_ema15_values = df['ema15'].dropna()
        if len(valid_ema15_values) > 0:
            print(f"[EMA15] EMA15值范围: {valid_ema15_values.min():.4f} - {valid_ema15_values.max():.4f}")
        
        return df
        
    except Exception as e:
        print(f"[EMA15] 计算失败: {e}")
        df['ema15'] = None
        return df

def test_with_real_data():
    """使用真实数据测试"""
    print("=== 使用真实数据测试EMA15计算 ===")
    
    # 模拟真实股票数据
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    np.random.seed(42)  # 固定随机种子以便重现
    
    # 生成模拟股价数据
    base_price = 25.0
    price_changes = np.random.normal(0, 0.02, 30)  # 2%的日波动
    prices = [base_price]
    
    for change in price_changes[1:]:
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 0.01))  # 确保价格为正
    
    df = pd.DataFrame({
        'trade_date': dates.strftime('%Y-%m-%d'),
        'close': prices,
        'open': [p * (1 + np.random.normal(0, 0.01)) for p in prices],
        'high': [p * (1 + abs(np.random.normal(0, 0.02))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.02))) for p in prices],
    })
    
    print(f"生成测试数据: {len(df)}条记录")
    print("前5条数据:")
    print(df[['trade_date', 'close']].head())
    
    # 计算EMA15
    result_df = calculate_ema15(df.copy())
    
    print("\n计算结果:")
    print("最后10条数据:")
    print(result_df[['trade_date', 'close', 'ema15']].tail(10))
    
    # 验证结果
    valid_ema15 = result_df['ema15'].notna().sum()
    print(f"\n验证结果: {valid_ema15}/{len(result_df)} 条有效EMA15数据")
    
    return result_df

def test_with_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    # 测试1: 空数据
    print("1. 测试空数据:")
    empty_df = pd.DataFrame()
    try:
        result = calculate_ema15(empty_df.copy())
        print("   空数据测试通过")
    except Exception as e:
        print(f"   空数据测试失败: {e}")
    
    # 测试2: 缺少close列
    print("2. 测试缺少close列:")
    no_close_df = pd.DataFrame({'trade_date': ['2024-01-01'], 'open': [25.0]})
    result = calculate_ema15(no_close_df.copy())
    print(f"   结果: ema15列存在={('ema15' in result.columns)}")
    
    # 测试3: 包含NaN值
    print("3. 测试包含NaN值:")
    nan_df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'close': [25.0, np.nan, 26.0]
    })
    result = calculate_ema15(nan_df.copy())
    print(f"   有效EMA15数据: {result['ema15'].notna().sum()}/{len(result)}")
    
    # 测试4: 极值数据
    print("4. 测试极值数据:")
    extreme_df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'close': [0.01, 1000000.0, 25.0]
    })
    result = calculate_ema15(extreme_df.copy())
    print(f"   EMA15值: {result['ema15'].tolist()}")

def test_json_serialization():
    """测试JSON序列化"""
    print("\n=== 测试JSON序列化 ===")
    
    # 创建测试数据
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'close': [25.0, 25.5, 26.0]
    })
    
    result_df = calculate_ema15(df.copy())
    
    # 模拟API返回的JSON格式
    import json
    
    try:
        data_list = []
        for _, row in result_df.iterrows():
            item = {
                'trade_date': row['trade_date'],
                'close': float(row['close']) if pd.notna(row['close']) else None,
                'ema15': float(row['ema15']) if pd.notna(row['ema15']) else None
            }
            data_list.append(item)
        
        # 尝试JSON序列化
        json_str = json.dumps(data_list, ensure_ascii=False, indent=2)
        print("JSON序列化成功:")
        print(json_str)
        
        # 尝试反序列化
        parsed_data = json.loads(json_str)
        print(f"JSON反序列化成功，包含{len(parsed_data)}条记录")
        
    except Exception as e:
        print(f"JSON序列化失败: {e}")

if __name__ == "__main__":
    print("开始EMA15直接测试...")
    
    # 运行所有测试
    test_with_real_data()
    test_with_edge_cases()
    test_json_serialization()
    
    print("\n测试完成！")