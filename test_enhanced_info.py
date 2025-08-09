#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试增强股票信息获取函数
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
    print("✅ AkShare库已成功导入")
except ImportError:
    ak = None
    AKSHARE_AVAILABLE = False
    print("❌ AkShare库未安装")

def safe_akshare_call(func, operation_name, *args, **kwargs):
    """安全调用AkShare函数"""
    try:
        print(f"[{operation_name}] 调用AkShare函数...")
        result = func(*args, **kwargs)
        print(f"[{operation_name}] ✅ 成功获取数据")
        return result
    except Exception as e:
        print(f"[{operation_name}] ❌ 调用失败: {e}")
        return None

def test_enhanced_stock_info(stock_code):
    """测试增强股票信息获取"""
    print(f"\n=== 测试股票 {stock_code} 的增强信息获取 ===")
    
    if not AKSHARE_AVAILABLE:
        print("❌ AkShare不可用，无法测试")
        return {}
    
    try:
        # 获取个股信息
        print(f"正在获取 {stock_code} 的个股信息...")
        stock_info = safe_akshare_call(
            ak.stock_individual_info_em,
            f"stock_info_{stock_code}",
            symbol=stock_code
        )
        
        if stock_info is not None and not stock_info.empty:
            print(f"✅ 成功获取个股信息，数据行数: {len(stock_info)}")
            print(f"数据列名: {list(stock_info.columns)}")
            
            # 显示原始数据
            print("\n原始数据:")
            for idx, row in stock_info.iterrows():
                item = str(row['item']).strip()
                value = row['value']
                print(f"  {item}: {value}")
            
            # 解析关键信息
            info_dict = {}
            if 'item' in stock_info.columns and 'value' in stock_info.columns:
                for idx, row in stock_info.iterrows():
                    item = str(row['item']).strip()
                    value = row['value']
                    
                    # 提取关键信息
                    if item == '总市值':
                        try:
                            market_cap_yuan = float(value) if value else 0.0
                            info_dict['总市值'] = market_cap_yuan / 100000000  # 转换为亿元
                            print(f"  解析总市值: {value} -> {info_dict['总市值']:.2f}亿")
                        except Exception as e:
                            info_dict['总市值'] = 0.0
                            print(f"  解析总市值失败: {e}")
                    elif item == '流通市值':
                        try:
                            circulating_cap_yuan = float(value) if value else 0.0
                            info_dict['流通市值'] = circulating_cap_yuan / 100000000  # 转换为亿元
                            print(f"  解析流通市值: {value} -> {info_dict['流通市值']:.2f}亿")
                        except Exception as e:
                            info_dict['流通市值'] = 0.0
                            print(f"  解析流通市值失败: {e}")
                    elif item == '市盈率':
                        try:
                            info_dict['市盈率-动态'] = float(value) if value else 0.0
                            print(f"  解析市盈率: {value} -> {info_dict['市盈率-动态']}")
                        except Exception as e:
                            info_dict['市盈率-动态'] = 0.0
                            print(f"  解析市盈率失败: {e}")
                    elif item == '市净率':
                        try:
                            info_dict['市净率'] = float(value) if value else 0.0
                            print(f"  解析市净率: {value} -> {info_dict['市净率']}")
                        except Exception as e:
                            info_dict['市净率'] = 0.0
                            print(f"  解析市净率失败: {e}")
                    elif item == '换手率':
                        try:
                            turnover_str = str(value).replace('%', '') if value else '0'
                            info_dict['换手率'] = float(turnover_str) if turnover_str else 0.0
                            print(f"  解析换手率: {value} -> {info_dict['换手率']}")
                        except Exception as e:
                            info_dict['换手率'] = 0.0
                            print(f"  解析换手率失败: {e}")
            
            print(f"\n解析结果: {info_dict}")
            return info_dict
        else:
            print("❌ 未获取到有效的个股信息")
            return {}
        
    except Exception as e:
        print(f"❌ 获取{stock_code}详细信息失败: {e}")
        import traceback
        traceback.print_exc()
        return {}

def main():
    """主函数"""
    print("=== 增强股票信息获取测试 ===")
    
    # 测试几个不同的股票
    test_stocks = ['300101', '000001', '600519', '000858']
    
    for stock_code in test_stocks:
        result = test_enhanced_stock_info(stock_code)
        print(f"\n{stock_code} 最终结果:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print("-" * 50)

if __name__ == "__main__":
    main()