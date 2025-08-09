#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动更新缓存数据
"""

import sys
import os
import json
from datetime import datetime

# 添加当前目录到Python路径
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

def get_enhanced_stock_info_manual(stock_code):
    """手动获取增强股票信息"""
    try:
        if not AKSHARE_AVAILABLE:
            print(f"[增强信息] AkShare不可用，跳过{stock_code}")
            return {}
        
        print(f"[增强信息] 开始获取{stock_code}的详细信息...")
        
        # 获取个股信息
        stock_info = safe_akshare_call(
            ak.stock_individual_info_em,
            f"stock_info_{stock_code}",
            symbol=stock_code
        )
        
        if stock_info is not None and not stock_info.empty:
            info_dict = {}
            print(f"[增强信息] 成功获取{stock_code}的原始数据，行数: {len(stock_info)}")
            print(f"[增强信息] 数据列: {list(stock_info.columns)}")
            
            if 'item' in stock_info.columns and 'value' in stock_info.columns:
                print(f"[增强信息] 开始解析{stock_code}的详细字段...")
                for idx, row in stock_info.iterrows():
                    item = str(row['item']).strip()
                    value = row['value']
                    print(f"[增强信息] 字段: {item} = {value}")
                    
                    # 提取关键信息
                    if item == '总市值':
                        try:
                            market_cap_yuan = float(value) if value else 0.0
                            info_dict['总市值'] = market_cap_yuan / 100000000  # 转换为亿元
                            print(f"[增强信息] ✅ 解析总市值: {value} -> {info_dict['总市值']:.2f}亿")
                        except Exception as e:
                            info_dict['总市值'] = 0.0
                            print(f"[增强信息] ❌ 解析总市值失败: {e}")
                    elif item == '流通市值':
                        try:
                            circulating_cap_yuan = float(value) if value else 0.0
                            info_dict['流通市值'] = circulating_cap_yuan / 100000000  # 转换为亿元
                            print(f"[增强信息] ✅ 解析流通市值: {value} -> {info_dict['流通市值']:.2f}亿")
                        except Exception as e:
                            info_dict['流通市值'] = 0.0
                            print(f"[增强信息] ❌ 解析流通市值失败: {e}")
                    elif item == '市盈率':
                        try:
                            info_dict['市盈率-动态'] = float(value) if value else 0.0
                            print(f"[增强信息] ✅ 解析市盈率: {value} -> {info_dict['市盈率-动态']}")
                        except Exception as e:
                            info_dict['市盈率-动态'] = 0.0
                            print(f"[增强信息] ❌ 解析市盈率失败: {e}")
                    elif item == '市净率':
                        try:
                            info_dict['市净率'] = float(value) if value else 0.0
                            print(f"[增强信息] ✅ 解析市净率: {value} -> {info_dict['市净率']}")
                        except Exception as e:
                            info_dict['市净率'] = 0.0
                            print(f"[增强信息] ❌ 解析市净率失败: {e}")
                    elif item == '换手率':
                        try:
                            turnover_str = str(value).replace('%', '') if value else '0'
                            info_dict['换手率'] = float(turnover_str) if turnover_str else 0.0
                            print(f"[增强信息] ✅ 解析换手率: {value} -> {info_dict['换手率']}")
                        except Exception as e:
                            info_dict['换手率'] = 0.0
                            print(f"[增强信息] ❌ 解析换手率失败: {e}")
            
            print(f"[增强信息] {stock_code}最终解析结果: {info_dict}")
            return info_dict
        else:
            print(f"[增强信息] 未获取到{stock_code}的有效数据")
            return {}
        
    except Exception as e:
        print(f"[增强信息] 获取{stock_code}详细信息失败: {e}")
        import traceback
        traceback.print_exc()
        return {}

def update_300101_cache_data():
    """更新300101的缓存数据"""
    try:
        print("=== 手动更新300101缓存数据 ===")
        
        # 读取现有缓存
        cache_file = 'cache/realtime_trading_data_cache.json'
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 查找300101数据
        stocks = cache_data.get('data', [])
        found_300101 = False
        
        for i, stock in enumerate(stocks):
            if stock.get('代码') == '300101':
                found_300101 = True
                print(f"找到300101数据，当前状态:")
                print(f"  总市值: {stock.get('总市值')}亿")
                print(f"  流通市值: {stock.get('流通市值')}亿")
                print(f"  振幅: {stock.get('振幅')}%")
                print(f"  市盈率-动态: {stock.get('市盈率-动态')}")
                
                # 获取增强信息
                enhanced_info = get_enhanced_stock_info_manual('300101')
                
                # 重新计算振幅
                high = stock.get('最高', 0)
                low = stock.get('最低', 0)
                pre_close = stock.get('昨收', 0)
                
                if pre_close > 0 and high > low and low > 0:
                    amplitude = ((high - low) / pre_close) * 100
                else:
                    amplitude = 0.0
                
                # 更新数据
                stock.update({
                    '振幅': amplitude,
                    '总市值': enhanced_info.get('总市值', 0.0),
                    '流通市值': enhanced_info.get('流通市值', 0.0),
                    '市盈率-动态': enhanced_info.get('市盈率-动态', 0.0),
                    '市净率': enhanced_info.get('市净率', 0.0),
                    '换手率': enhanced_info.get('换手率', 0.0)
                })
                
                print(f"\n更新后的300101数据:")
                print(f"  总市值: {stock.get('总市值')}亿")
                print(f"  流通市值: {stock.get('流通市值')}亿")
                print(f"  振幅: {stock.get('振幅'):.2f}%")
                print(f"  市盈率-动态: {stock.get('市盈率-动态')}")
                print(f"  市净率: {stock.get('市净率')}")
                
                break
        
        if found_300101:
            # 更新缓存时间
            cache_data['fetch_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cache_data['cache_time'] = datetime.now().strftime('%H:%M:%S')
            
            # 保存更新后的缓存
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 成功更新300101缓存数据")
            return True
        else:
            print("❌ 未找到300101数据")
            return False
            
    except Exception as e:
        print(f"❌ 更新缓存失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=== 手动缓存数据更新工具 ===")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 更新300101缓存数据
    if update_300101_cache_data():
        print("\n=== 更新完成，请刷新前端页面查看效果 ===")
    else:
        print("\n=== 更新失败 ===")

if __name__ == "__main__":
    main()