#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分时图缓存功能测试脚本
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from cache_manager import cache_manager
    print("✅ 成功导入 cache_manager")
except ImportError as e:
    print(f"❌ 导入 cache_manager 失败: {e}")
    sys.exit(1)

def test_intraday_cache_path():
    """测试分时图缓存路径生成"""
    print("\n🔍 测试分时图缓存路径生成...")
    
    # 测试默认日期
    path1 = cache_manager.get_intraday_cache_file_path("000001")
    print(f"默认日期路径: {path1}")
    
    # 测试指定日期
    path2 = cache_manager.get_intraday_cache_file_path("000001", "2025-02-02")
    print(f"指定日期路径: {path2}")
    
    # 验证路径格式
    expected_pattern = "cache/intraday/000001/"
    if expected_pattern in path1:
        print("✅ 路径格式正确")
    else:
        print("❌ 路径格式错误")

def test_save_and_load_intraday_data():
    """测试分时图数据保存和加载"""
    print("\n💾 测试分时图数据保存和加载...")
    
    # 创建测试数据
    test_stock_code = "000001"
    test_data = [
        {
            'time': '09:30',
            'timestamp': '2025-02-02 09:30:00',
            'price': 10.50,
            'open': 10.45,
            'high': 10.55,
            'low': 10.40,
            'volume': 1000,
            'amount': 10500,
            'vwap': 10.50,
            'avg_price': 10.50,
            'cumulative_volume': 1000,
            'cumulative_amount': 10500,
            'total_shares': 100000,
            'total_turnover': 1050000
        },
        {
            'time': '09:31',
            'timestamp': '2025-02-02 09:31:00',
            'price': 10.52,
            'open': 10.50,
            'high': 10.55,
            'low': 10.48,
            'volume': 800,
            'amount': 8416,
            'vwap': 10.51,
            'avg_price': 10.51,
            'cumulative_volume': 1800,
            'cumulative_amount': 18916,
            'total_shares': 180000,
            'total_turnover': 1891600
        }
    ]
    
    # 测试保存
    try:
        result = cache_manager.save_intraday_data(test_stock_code, test_data)
        if result:
            print(f"✅ 成功保存 {len(test_data)} 条分时数据")
        else:
            print("❌ 保存分时数据失败")
            return
    except Exception as e:
        print(f"❌ 保存分时数据异常: {e}")
        return
    
    # 测试加载
    try:
        loaded_data = cache_manager.load_intraday_data(test_stock_code)
        if loaded_data:
            print(f"✅ 成功加载 {len(loaded_data)} 条分时数据")
            
            # 验证数据完整性
            if len(loaded_data) == len(test_data):
                print("✅ 数据条数正确")
            else:
                print(f"❌ 数据条数不匹配: 期望 {len(test_data)}, 实际 {len(loaded_data)}")
            
            # 验证第一条数据
            first_item = loaded_data[0]
            if first_item['time'] == '09:30' and first_item['price'] == 10.50:
                print("✅ 数据内容正确")
            else:
                print("❌ 数据内容不匹配")
                
        else:
            print("❌ 加载分时数据失败")
    except Exception as e:
        print(f"❌ 加载分时数据异常: {e}")

def test_cache_file_structure():
    """测试缓存文件结构"""
    print("\n📁 测试缓存文件结构...")
    
    cache_dir = "cache/intraday"
    if os.path.exists(cache_dir):
        print(f"✅ 缓存目录存在: {cache_dir}")
        
        # 列出股票目录
        stock_dirs = [d for d in os.listdir(cache_dir) if os.path.isdir(os.path.join(cache_dir, d))]
        if stock_dirs:
            print(f"📂 找到 {len(stock_dirs)} 个股票缓存目录:")
            for stock_dir in stock_dirs[:5]:  # 只显示前5个
                stock_path = os.path.join(cache_dir, stock_dir)
                cache_files = [f for f in os.listdir(stock_path) if f.endswith('.json')]
                print(f"  - {stock_dir}: {len(cache_files)} 个缓存文件")
        else:
            print("📂 暂无股票缓存目录")
    else:
        print(f"❌ 缓存目录不存在: {cache_dir}")

def test_cleanup_old_cache():
    """测试清理过期缓存"""
    print("\n🧹 测试清理过期缓存...")
    
    try:
        cache_manager.cleanup_old_intraday_cache()
        print("✅ 清理过期缓存完成")
    except Exception as e:
        print(f"❌ 清理过期缓存失败: {e}")

def main():
    """主测试函数"""
    print("🚀 开始分时图缓存功能测试")
    print("=" * 50)
    
    # 运行各项测试
    test_intraday_cache_path()
    test_save_and_load_intraday_data()
    test_cache_file_structure()
    test_cleanup_old_cache()
    
    print("\n" + "=" * 50)
    print("✨ 分时图缓存功能测试完成")

if __name__ == "__main__":
    main()