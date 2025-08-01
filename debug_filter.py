#!/usr/bin/env python3
"""
调试筛选功能的脚本
"""
import json
import os

def debug_filter():
    """调试筛选功能"""
    
    # 检查缓存数据
    cache_dir = 'cache'
    markets = ['cyb', 'hu', 'zxb', 'kcb', 'bj']
    
    all_stocks = []
    nine_turn_stocks = []
    red_candidates = []
    
    for market in markets:
        cache_file = os.path.join(cache_dir, f'{market}_stocks_cache.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    market_data = json.load(f)
                
                if 'stocks' in market_data:
                    stocks = market_data['stocks']
                    all_stocks.extend(stocks)
                    
                    # 查找有九转序列数据的股票
                    for stock in stocks:
                        nine_turn_up = stock.get('nine_turn_up', 0)
                        nine_turn_down = stock.get('nine_turn_down', 0)
                        
                        if nine_turn_up > 0 or nine_turn_down > 0:
                            nine_turn_stocks.append({
                                'ts_code': stock.get('ts_code'),
                                'name': stock.get('name'),
                                'nine_turn_up': nine_turn_up,
                                'nine_turn_down': nine_turn_down,
                                'turnover_rate': stock.get('turnover_rate', 0),
                                'volume_ratio': stock.get('volume_ratio', 0)
                            })
                        
                        # 查找九转序列3-6的股票（不考虑其他条件）
                        if 3 <= nine_turn_up <= 6:
                            red_candidates.append({
                                'ts_code': stock.get('ts_code'),
                                'name': stock.get('name'),
                                'nine_turn_up': nine_turn_up,
                                'turnover_rate': stock.get('turnover_rate', 0),
                                'volume_ratio': stock.get('volume_ratio', 0)
                            })
                            
            except Exception as e:
                print(f"读取{market}缓存失败: {e}")
    
    print(f"总股票数: {len(all_stocks)}")
    print(f"有九转序列数据的股票数: {len(nine_turn_stocks)}")
    print(f"九转序列3-6的股票数（不考虑其他条件）: {len(red_candidates)}")
    
    # 显示前10个有九转序列数据的股票
    print("\n前10个有九转序列数据的股票:")
    for i, stock in enumerate(nine_turn_stocks[:10]):
        print(f"{i+1}. {stock['ts_code']} {stock['name']} - 上:{stock['nine_turn_up']} 下:{stock['nine_turn_down']} 换手率:{stock['turnover_rate']} 量比:{stock['volume_ratio']}")
    
    # 显示所有九转序列3-6的股票
    print(f"\n所有九转序列3-6的股票 (共{len(red_candidates)}只):")
    for i, stock in enumerate(red_candidates):
        meets_criteria = stock['turnover_rate'] > 2 and stock['volume_ratio'] > 1
        status = "✓符合条件" if meets_criteria else "✗不符合条件"
        print(f"{i+1}. {stock['ts_code']} {stock['name']} - 九转:{stock['nine_turn_up']} 换手率:{stock['turnover_rate']} 量比:{stock['volume_ratio']} {status}")

if __name__ == "__main__":
    debug_filter()