#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from cache_manager import OptimizedCacheManager

def debug_red_filter():
    """调试红色筛选条件"""
    cache_manager = OptimizedCacheManager()
    
    # 获取所有股票数据
    all_stocks = []
    markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
    
    for market in markets:
        try:
            market_data = cache_manager.load_cache_data(market)
            if market_data and 'stocks' in market_data:
                all_stocks.extend(market_data['stocks'])
        except Exception as e:
            print(f"获取市场 {market} 数据失败: {e}")
            continue
    
    print(f"总股票数: {len(all_stocks)}")
    
    # 统计九转序列数据
    nine_turn_stats = {}
    turnover_stats = {}
    volume_stats = {}
    
    red_candidates = []
    
    for stock in all_stocks:
        try:
            turnover_rate = float(stock.get('turnover_rate', 0))
            volume_ratio = float(stock.get('volume_ratio', 0))
            nine_turn_up = int(stock.get('nine_turn_up', 0))
            
            # 统计九转序列
            if nine_turn_up > 0:
                nine_turn_stats[nine_turn_up] = nine_turn_stats.get(nine_turn_up, 0) + 1
            
            # 统计换手率
            if turnover_rate > 0:
                if turnover_rate > 5:
                    turnover_stats['> 5'] = turnover_stats.get('> 5', 0) + 1
                elif turnover_rate > 2:
                    turnover_stats['2-5'] = turnover_stats.get('2-5', 0) + 1
                elif turnover_rate > 1:
                    turnover_stats['1-2'] = turnover_stats.get('1-2', 0) + 1
                else:
                    turnover_stats['0-1'] = turnover_stats.get('0-1', 0) + 1
            
            # 统计量比
            if volume_ratio > 0:
                if volume_ratio > 2:
                    volume_stats['> 2'] = volume_stats.get('> 2', 0) + 1
                elif volume_ratio > 1:
                    volume_stats['1-2'] = volume_stats.get('1-2', 0) + 1
                elif volume_ratio > 0.8:
                    volume_stats['0.8-1'] = volume_stats.get('0.8-1', 0) + 1
                else:
                    volume_stats['0-0.8'] = volume_stats.get('0-0.8', 0) + 1
            else:
                volume_stats['0'] = volume_stats.get('0', 0) + 1
            
            # 检查红色筛选条件
            if 3 <= nine_turn_up <= 6:
                volume_condition = True
                if volume_ratio > 0:
                    volume_condition = volume_ratio > 0.8
                
                if turnover_rate > 1 and volume_condition:
                    red_candidates.append({
                        'ts_code': stock.get('ts_code'),
                        'name': stock.get('name'),
                        'turnover_rate': turnover_rate,
                        'volume_ratio': volume_ratio,
                        'nine_turn_up': nine_turn_up
                    })
                    
        except (ValueError, TypeError):
            continue
    
    print("\n九转序列统计:")
    for key in sorted(nine_turn_stats.keys()):
        print(f"  九转{key}: {nine_turn_stats[key]}只")
    
    print("\n换手率统计:")
    for key, value in turnover_stats.items():
        print(f"  换手率{key}: {value}只")
    
    print("\n量比统计:")
    for key, value in volume_stats.items():
        print(f"  量比{key}: {value}只")
    
    print(f"\n符合红色筛选条件的股票: {len(red_candidates)}只")
    
    if red_candidates:
        print("\n前10只符合条件的股票:")
        for i, stock in enumerate(red_candidates[:10]):
            print(f"  {i+1}. {stock['name']}({stock['ts_code']}) - "
                  f"换手率:{stock['turnover_rate']:.2f}%, "
                  f"量比:{stock['volume_ratio']:.2f}, "
                  f"九转:{stock['nine_turn_up']}")

if __name__ == "__main__":
    debug_red_filter()