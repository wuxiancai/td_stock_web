#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查上证指数价格差异的脚本
比较不同数据源的上证指数价格
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import json

def check_cache_data():
    """检查本地缓存的上证指数价格"""
    print("=== 本地缓存数据 ===")
    
    cache_file = "cache/indices_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"缓存时间: {cache_data.get('fetch_time', 'N/A')}")
            print(f"缓存日期: {cache_data.get('cache_date', 'N/A')}")
            print()
            
            # 检查data字段中的sh000001
            data = cache_data.get('data', {})
            if 'sh000001' in data:
                sh_data = data['sh000001']
                print(f"上证指数缓存数据:")
                print(f"   名称: {sh_data.get('name', 'N/A')}")
                print(f"   当前价格: {sh_data.get('current_price', 'N/A')}")
                print(f"   更新时间: {sh_data.get('update_time', 'N/A')}")
                print(f"   涨跌额: {sh_data.get('change_amount', 'N/A')}")
                print(f"   涨跌幅: {sh_data.get('change_pct', 'N/A')}%")
                print(f"   成交额: {sh_data.get('volume', 'N/A')}")
                
                return sh_data.get('current_price')
            else:
                print("缓存中未找到上证指数数据")
                return None
                
        except Exception as e:
            print(f"读取缓存文件失败: {e}")
            return None
    else:
        print("缓存文件不存在")
        return None

def check_akshare_data():
    """检查AKShare的上证指数价格"""
    try:
        import akshare as ak
        print("=== AKShare 上证指数数据 ===")
        
        # 获取沪深重要指数
        print("1. 获取沪深重要指数...")
        df_important = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
        if df_important is not None and not df_important.empty:
            shanghai_data = df_important[df_important['名称'].str.contains('上证指数')]
            if not shanghai_data.empty:
                for _, row in shanghai_data.iterrows():
                    print(f"   名称: {row['名称']}")
                    print(f"   代码: {row['代码']}")
                    print(f"   最新价: {row['最新价']}")
                    print(f"   涨跌额: {row['涨跌额']}")
                    print(f"   涨跌幅: {row['涨跌幅']}%")
                    print(f"   成交额: {row['成交额']}")
                    print()
                    return row['最新价']
        
        return None
            
    except ImportError:
        print("AKShare 未安装")
        return None
    except Exception as e:
        print(f"AKShare 获取数据失败: {e}")
        return None

def check_tushare_data():
    """检查Tushare的上证指数价格"""
    try:
        import tushare as ts
        
        # 使用应用程序中的token
        tushare_token = '68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019'
        
        ts.set_token(tushare_token)
        pro = ts.pro_api()
        
        print("=== Tushare 上证指数数据 ===")
        
        # 获取2025年7月28日的数据
        target_date = '20250728'
        df = pro.index_daily(ts_code='000001.SH', trade_date=target_date)
        
        if df is not None and not df.empty:
            row = df.iloc[0]
            print(f"日期: {row['trade_date']}")
            print(f"收盘价: {row['close']:.2f}")
            print(f"涨跌额: {row['change']:.2f}")
            print(f"涨跌幅: {row['pct_chg']:.2f}%")
            print(f"成交额: {row['amount'] / 10:.2f}亿")
            print(f"最高价: {row['high']:.2f}")
            print(f"最低价: {row['low']:.2f}")
            print(f"开盘价: {row['open']:.2f}")
            
            return row['close']
        else:
            print(f"未找到 {target_date} 的数据")
            return None
            
    except ImportError:
        print("Tushare 未安装")
        return None
    except Exception as e:
        print(f"Tushare 获取数据失败: {e}")
        return None

def main():
    """主函数"""
    print("检查上证指数价格差异")
    print("=" * 50)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查本地缓存数据
    cached_price = check_cache_data()
    
    # 检查AKShare数据
    akshare_price = check_akshare_data()
    
    # 检查Tushare数据
    tushare_price = check_tushare_data()
    
    print()
    print("=" * 50)
    
    # 数据对比
    if cached_price is not None and tushare_price is not None:
        difference = abs(cached_price - tushare_price)
        print(f"=== 数据对比结果 ===")
        print(f"缓存价格: {cached_price:.4f}")
        print(f"Tushare价格: {tushare_price:.2f}")
        print(f"价格差异: {difference:.4f} 点")
        
        if difference < 0.01:
            print("✅ 价格数据一致")
        else:
            print("⚠️  价格存在差异")
            
        # 与用户报告的正确价格对比
        correct_price = 3597.94
        cache_diff = abs(cached_price - correct_price)
        tushare_diff = abs(tushare_price - correct_price)
        
        print(f"\n=== 与正确价格对比 ===")
        print(f"用户报告正确价格: {correct_price:.2f}")
        print(f"缓存与正确价格差异: {cache_diff:.4f} 点")
        print(f"Tushare与正确价格差异: {tushare_diff:.4f} 点")
        
        if cache_diff < 0.01 and tushare_diff < 0.01:
            print("✅ 所有数据源价格正确")
        elif cache_diff < 0.01:
            print("✅ 缓存价格已修正为正确价格")
        elif tushare_diff < 0.01:
            print("✅ Tushare价格正确")
    
    print("检查完成")
    print()
    print("说明:")
    print("- 如果不同数据源的价格存在差异，可能是由于:")
    print("  1. 数据更新时间不同")
    print("  2. 数据源的数据质量差异")
    print("  3. 网络延迟或数据传输问题")
    print("  4. 数据源的计算方法差异")
    print("- 建议以官方权威数据源为准")

if __name__ == "__main__":
    main()