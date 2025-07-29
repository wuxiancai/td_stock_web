#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复实时交易数据中涨跌幅和涨跌额计算错误的脚本

问题描述：
- 当前实时交易数据的涨跌幅和涨跌额是基于昨天收盘价计算的
- 正确的计算应该是：(当前价格 - 今天开盘价) / 今天开盘价 * 100

修复方案：
1. 在实时交易数据API中重新计算涨跌幅和涨跌额
2. 使用今天开盘价作为基准，而不是昨天收盘价
"""

import os
import sys

def fix_realtime_change_calculation():
    """修复实时交易数据中的涨跌幅计算错误"""
    
    app_py_path = '/Users/wuxiancai/td_stock_web/app.py'
    
    # 读取原文件内容
    with open(app_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找需要修改的代码段
    old_code = '''        # 转换数据格式，确保所有字段都包含
        data_list = []
        for _, row in realtime_data.iterrows():
            try:
                data_item = {
                    '序号': int(row.get('序号', 0)) if pd.notna(row.get('序号')) else 0,
                    '代码': str(row.get('代码', '')),
                    '名称': str(row.get('名称', '')),
                    '最新价': float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else 0.0,
                    '涨跌幅': float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else 0.0,
                    '涨跌额': float(row.get('涨跌额', 0)) if pd.notna(row.get('涨跌额')) else 0.0,'''
    
    new_code = '''        # 转换数据格式，确保所有字段都包含，并修正涨跌幅计算
        data_list = []
        for _, row in realtime_data.iterrows():
            try:
                # 获取基础数据
                latest_price = float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else 0.0
                open_price = float(row.get('今开', 0)) if pd.notna(row.get('今开')) else 0.0
                yesterday_close = float(row.get('昨收', 0)) if pd.notna(row.get('昨收')) else 0.0
                
                # 重新计算涨跌幅和涨跌额（基于今开价格，而不是昨收价格）
                if open_price > 0:
                    # 正确的涨跌幅：(当前价格 - 今开价格) / 今开价格 * 100
                    corrected_change_percent = ((latest_price - open_price) / open_price) * 100
                    corrected_change_amount = latest_price - open_price
                else:
                    # 如果今开价格为0，则使用昨收价格作为备选
                    if yesterday_close > 0:
                        corrected_change_percent = ((latest_price - yesterday_close) / yesterday_close) * 100
                        corrected_change_amount = latest_price - yesterday_close
                    else:
                        corrected_change_percent = 0.0
                        corrected_change_amount = 0.0
                
                data_item = {
                    '序号': int(row.get('序号', 0)) if pd.notna(row.get('序号')) else 0,
                    '代码': str(row.get('代码', '')),
                    '名称': str(row.get('名称', '')),
                    '最新价': latest_price,
                    '涨跌幅': round(corrected_change_percent, 2),  # 使用修正后的涨跌幅
                    '涨跌额': round(corrected_change_amount, 2),  # 使用修正后的涨跌额'''
    
    # 替换代码
    if old_code in content:
        content = content.replace(old_code, new_code)
        print("✅ 成功修复实时交易数据中的涨跌幅计算逻辑")
    else:
        print("❌ 未找到需要修复的代码段")
        return False
    
    # 写回文件
    with open(app_py_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 修复完成！")
    print("\n修复说明：")
    print("- 涨跌幅现在基于今天开盘价计算：(当前价格 - 今开价格) / 今开价格 * 100")
    print("- 涨跌额现在基于今天开盘价计算：当前价格 - 今开价格")
    print("- 如果今开价格为0，则回退到使用昨收价格")
    
    return True

def verify_fix():
    """验证修复是否成功"""
    app_py_path = '/Users/wuxiancai/td_stock_web/app.py'
    
    with open(app_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查修复后的代码是否存在
    if "corrected_change_percent = ((latest_price - open_price) / open_price) * 100" in content:
        print("✅ 验证成功：修复代码已正确应用")
        return True
    else:
        print("❌ 验证失败：修复代码未找到")
        return False

if __name__ == "__main__":
    print("🔧 开始修复实时交易数据中的涨跌幅计算错误...")
    print("=" * 60)
    
    if fix_realtime_change_calculation():
        if verify_fix():
            print("\n🎉 修复成功！请重启Flask服务器以应用更改。")
        else:
            print("\n❌ 修复验证失败，请检查代码。")
    else:
        print("\n❌ 修复失败，请检查代码。")