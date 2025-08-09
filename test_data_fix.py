#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试数据获取和显示修复
"""

import requests
import json
from datetime import datetime

def test_api_data():
    """测试API数据"""
    try:
        print("=== 测试API数据获取 ===")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 测试实时交易数据API
        url = 'http://localhost:8080/api/stock/realtime_trading_data'
        print(f"请求URL: {url}")
        
        response = requests.get(url, timeout=10)
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"API响应成功: {data.get('success', False)}")
            
            if data.get('success'):
                stocks = data.get('data', [])
                print(f"获取到股票数量: {len(stocks)}")
                
                # 查找300101
                found_300101 = False
                for stock in stocks:
                    if stock.get('代码') == '300101':
                        found_300101 = True
                        print(f"\n✅ 找到300101 (振芯科技):")
                        print(f"  名称: {stock.get('名称')}")
                        print(f"  最新价: {stock.get('最新价')}")
                        print(f"  涨跌幅: {stock.get('涨跌幅')}%")
                        print(f"  总市值: {stock.get('总市值')}亿")
                        print(f"  流通市值: {stock.get('流通市值')}亿")
                        print(f"  振幅: {stock.get('振幅')}%")
                        print(f"  市盈率-动态: {stock.get('市盈率-动态')}")
                        print(f"  市净率: {stock.get('市净率')}")
                        break
                
                if not found_300101:
                    print("\n❌ 未找到300101数据")
                    print("前10只股票:")
                    for i, stock in enumerate(stocks[:10]):
                        print(f"  {i+1}. {stock.get('代码')}: {stock.get('名称')} - 总市值: {stock.get('总市值')}亿")
                
                # 检查其他股票的数据质量
                print(f"\n=== 数据质量检查 ===")
                valid_market_cap_count = 0
                valid_amplitude_count = 0
                
                for stock in stocks:
                    if stock.get('总市值', 0) > 0:
                        valid_market_cap_count += 1
                    if stock.get('振幅', 0) > 0:
                        valid_amplitude_count += 1
                
                print(f"有效总市值数据: {valid_market_cap_count}/{len(stocks)} ({valid_market_cap_count/len(stocks)*100:.1f}%)")
                print(f"有效振幅数据: {valid_amplitude_count}/{len(stocks)} ({valid_amplitude_count/len(stocks)*100:.1f}%)")
                
            else:
                print(f"❌ API返回错误: {data.get('error')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"响应内容: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def check_cache_file():
    """检查缓存文件"""
    try:
        print(f"\n=== 检查缓存文件 ===")
        cache_file = 'cache/realtime_trading_data_cache.json'
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"✅ 缓存文件存在")
            print(f"缓存时间: {cache_data.get('fetch_time')}")
            print(f"数据条数: {cache_data.get('total_count')}")
            
            # 查找300101
            stocks = cache_data.get('data', [])
            found_300101 = False
            for stock in stocks:
                if stock.get('代码') == '300101':
                    found_300101 = True
                    print(f"\n✅ 缓存中找到300101:")
                    print(f"  总市值: {stock.get('总市值')}亿")
                    print(f"  流通市值: {stock.get('流通市值')}亿")
                    print(f"  振幅: {stock.get('振幅')}%")
                    break
            
            if not found_300101:
                print(f"\n❌ 缓存中未找到300101")
                
        except FileNotFoundError:
            print(f"❌ 缓存文件不存在: {cache_file}")
        except Exception as e:
            print(f"❌ 读取缓存文件失败: {e}")
            
    except Exception as e:
        print(f"❌ 检查缓存文件失败: {e}")

def main():
    """主函数"""
    print("=== 数据获取和显示修复测试 ===")
    
    # 1. 检查缓存文件
    check_cache_file()
    
    # 2. 测试API数据
    test_api_data()
    
    print(f"\n=== 测试完成 ===")

if __name__ == "__main__":
    main()