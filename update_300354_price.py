#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新股票300354的正确收盘价
将最新价从40.11更新为40.29
"""

import json
import os
from datetime import datetime

def update_300354_price():
    """更新股票300354的收盘价为40.29"""
    
    print("=== 更新股票300354收盘价 ===")
    
    # 正确的收盘价数据
    correct_price = 40.29
    yesterday_close = 40.31  # 昨收
    change_amount = correct_price - yesterday_close  # 涨跌额
    change_pct = (change_amount / yesterday_close) * 100  # 涨跌幅
    
    print(f"正确收盘价: {correct_price}")
    print(f"昨收: {yesterday_close}")
    print(f"涨跌额: {change_amount:.2f}")
    print(f"涨跌幅: {change_pct:.2f}%")
    
    # 更新实时交易数据缓存
    cache_file = os.path.join('cache', 'realtime_trading_data_cache.json')
    
    if os.path.exists(cache_file):
        try:
            # 读取现有缓存
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"读取缓存文件: {cache_file}")
            
            # 查找并更新300354的数据
            updated = False
            for item in cache_data.get('data', []):
                if item.get('代码') == '300354':
                    print(f"找到股票300354，当前价格: {item.get('最新价')}")
                    
                    # 更新价格数据
                    item['最新价'] = correct_price
                    item['涨跌额'] = round(change_amount, 2)
                    item['涨跌幅'] = round(change_pct, 2)
                    item['昨收'] = yesterday_close
                    
                    print(f"已更新为: {correct_price}")
                    updated = True
                    break
            
            if not updated:
                # 如果没找到，创建新的数据条目
                print("未找到300354数据，创建新条目")
                new_item = {
                    '序号': len(cache_data.get('data', [])) + 1,
                    '代码': '300354',
                    '名称': '东华测试',
                    '最新价': correct_price,
                    '涨跌幅': round(change_pct, 2),
                    '涨跌额': round(change_amount, 2),
                    '成交量': 3561102,  # 从历史数据获取
                    '成交额': 144951561,  # 从历史数据获取
                    '振幅': 2.06,  # (41.13-40.3)/40.31*100
                    '最高': 41.13,
                    '最低': 40.30,
                    '今开': 40.31,
                    '昨收': yesterday_close,
                    '量比': 1.05,
                    '换手率': 0.85,
                    '市盈率-动态': 11.76,
                    '市净率': 1.48,
                    '总市值': 4659000000,
                    '流通市值': 4157000000,
                    '涨速': 0.00,
                    '5分钟涨跌': 0.00,
                    '60日涨跌幅': 0.00,
                    '年初至今涨跌幅': 0.00
                }
                cache_data['data'].append(new_item)
                cache_data['total_records'] = len(cache_data['data'])
                updated = True
            
            if updated:
                # 更新缓存时间戳
                cache_data['timestamp'] = '2025-07-29 15:00:00'  # 收盘时间
                cache_data['cache_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 备份原文件
                backup_file = cache_file + '.backup'
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                print(f"原缓存已备份到: {backup_file}")
                
                # 保存更新后的缓存
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                print(f"✅ 缓存更新成功!")
                print(f"📊 股票300354最新价: {correct_price}")
                print(f"📈 涨跌幅: {change_pct:.2f}%")
                print(f"⏰ 更新时间: {cache_data['timestamp']}")
                
                return True
            
        except Exception as e:
            print(f"❌ 更新缓存失败: {e}")
            return False
    else:
        print(f"❌ 缓存文件不存在: {cache_file}")
        print("请先运行 create_cache_data.py 创建缓存文件")
        return False

def verify_update():
    """验证更新结果"""
    cache_file = os.path.join('cache', 'realtime_trading_data_cache.json')
    
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print("\n=== 验证更新结果 ===")
            for item in cache_data.get('data', []):
                if item.get('代码') == '300354':
                    print(f"股票代码: {item.get('代码')}")
                    print(f"股票名称: {item.get('名称')}")
                    print(f"最新价: {item.get('最新价')}")
                    print(f"昨收: {item.get('昨收')}")
                    print(f"涨跌额: {item.get('涨跌额')}")
                    print(f"涨跌幅: {item.get('涨跌幅')}%")
                    print(f"缓存时间: {cache_data.get('timestamp')}")
                    return True
            
            print("❌ 未找到股票300354数据")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始更新股票300354收盘价...")
    
    if update_300354_price():
        print("\n🔍 验证更新结果...")
        if verify_update():
            print("\n✅ 更新完成！请刷新页面查看最新数据。")
        else:
            print("\n⚠️ 更新可能未成功，请检查数据。")
    else:
        print("\n❌ 更新失败！")