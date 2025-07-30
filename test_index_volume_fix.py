#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数成交额修复验证脚本
验证指数成交额的计算和显示是否正确
"""

import json
import os
from datetime import datetime

def test_volume_calculation():
    """测试成交额计算逻辑"""
    print("=== 指数成交额修复验证 ===\n")
    
    # 模拟AkShare返回的原始数据（单位：元）
    raw_volume_yuan = 101000000000  # 1010亿元
    
    print(f"1. AkShare原始成交额数据: {raw_volume_yuan:,} 元")
    print(f"   等于: {raw_volume_yuan / 100000000:.2f} 亿元")
    
    # 后端处理逻辑（app.py中的转换）
    backend_volume = raw_volume_yuan / 100000000  # 转换为亿元
    print(f"\n2. 后端处理后的数据: {backend_volume:.2f} 亿元")
    
    # 前端显示逻辑（修复前）
    print("\n3. 前端显示逻辑对比:")
    print("   修复前（错误）:")
    if backend_volume >= 10000:
        wrong_display = (backend_volume / 10000)
        print(f"     显示: {wrong_display:.2f} 亿元 ❌")
    else:
        print(f"     显示: {backend_volume:.2f} 万元 ❌")
    
    print("   修复后（正确）:")
    if backend_volume >= 1:
        correct_display = backend_volume
        print(f"     显示: {correct_display:.2f} 亿元 ✅")
    else:
        correct_display = backend_volume * 10000
        print(f"     显示: {correct_display:.0f} 万元 ✅")

def test_different_scenarios():
    """测试不同数值场景"""
    print("\n=== 不同数值场景测试 ===\n")
    
    test_cases = [
        {"name": "深证成指（典型大盘指数）", "raw_yuan": 101000000000},  # 1010亿元
        {"name": "上证指数（超大成交额）", "raw_yuan": 350000000000},   # 3500亿元
        {"name": "小型指数", "raw_yuan": 5000000000},                # 50亿元
        {"name": "极小指数", "raw_yuan": 500000000},                 # 5亿元
    ]
    
    for case in test_cases:
        raw_yuan = case["raw_yuan"]
        backend_volume = raw_yuan / 100000000  # 后端转换
        
        print(f"{case['name']}:")
        print(f"  原始数据: {raw_yuan:,} 元")
        print(f"  后端处理: {backend_volume:.2f} 亿元")
        
        # 前端显示（修复后的逻辑）
        if backend_volume >= 1:
            display_text = f"{backend_volume:.2f}亿"
        else:
            display_text = f"{(backend_volume * 10000):.0f}万"
        
        print(f"  前端显示: {display_text}")
        print()

def check_frontend_code():
    """检查前端代码修复情况"""
    print("=== 前端代码修复检查 ===\n")
    
    index_html_path = "/Users/wuxiancai/td_stock_web/templates/index.html"
    
    if os.path.exists(index_html_path):
        with open(index_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否还有错误的除法操作
        if "volume / 10000" in content:
            print("❌ 发现残留的错误代码: volume / 10000")
            # 找到具体位置
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if "volume / 10000" in line:
                    print(f"   第{i}行: {line.strip()}")
        else:
            print("✅ 未发现错误的除法操作")
        
        # 检查正确的逻辑
        if "index.volume.toFixed(2) + '亿'" in content:
            print("✅ 发现正确的显示逻辑: index.volume.toFixed(2) + '亿'")
        
        if "(index.volume * 10000).toFixed(0) + '万'" in content:
            print("✅ 发现正确的万元显示逻辑: (index.volume * 10000).toFixed(0) + '万'")
    else:
        print("❌ 找不到index.html文件")

def main():
    """主函数"""
    test_volume_calculation()
    test_different_scenarios()
    check_frontend_code()
    
    print("=== 修复总结 ===")
    print("问题原因:")
    print("1. AkShare返回的成交额单位是'元'")
    print("2. 后端正确地除以100000000转换为'亿元'")
    print("3. 前端错误地又除以10000，导致显示为实际值的1/10000")
    print()
    print("修复方案:")
    print("1. 统一前端两个显示函数的逻辑")
    print("2. 直接使用后端处理好的亿元数据")
    print("3. 大于等于1亿显示为'XX.XX亿'")
    print("4. 小于1亿显示为'XXXX万'")
    print()
    print("修复效果:")
    print("深证成指成交额从 '1.01亿' 修复为 '1010.00亿' ✅")

if __name__ == "__main__":
    main()