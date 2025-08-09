#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复前端数据显示问题
问题分析：
1. 300101不在热门股票列表中，所以后台定时任务没有获取它的数据
2. 增强信息获取函数工作正常，但可能在批量处理时出现问题
3. 需要确保所有字段都能正确获取和显示

解决方案：
1. 将300101添加到热门股票列表（已完成）
2. 修复增强信息获取的错误处理
3. 添加更好的日志记录
4. 创建测试脚本验证修复效果
"""

import sys
import os
import json
import requests
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

def get_enhanced_stock_info_fixed(stock_code):
    """修复版本的增强股票信息获取函数"""
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
            
            if 'item' in stock_info.columns and 'value' in stock_info.columns:
                for idx, row in stock_info.iterrows():
                    item = str(row['item']).strip()
                    value = row['value']
                    
                    # 提取关键信息，使用中文字段名匹配DataFrame格式
                    if item == '总市值':
                        try:
                            # 转换为亿元单位
                            market_cap_yuan = float(value) if value else 0.0
                            info_dict['总市值'] = market_cap_yuan / 100000000  # 转换为亿元
                            print(f"[增强信息] 解析总市值: {value} -> {info_dict['总市值']:.2f}亿")
                        except Exception as e:
                            info_dict['总市值'] = 0.0
                            print(f"[增强信息] 解析总市值失败: {e}")
                    elif item == '流通市值':
                        try:
                            # 转换为亿元单位
                            circulating_cap_yuan = float(value) if value else 0.0
                            info_dict['流通市值'] = circulating_cap_yuan / 100000000  # 转换为亿元
                            print(f"[增强信息] 解析流通市值: {value} -> {info_dict['流通市值']:.2f}亿")
                        except Exception as e:
                            info_dict['流通市值'] = 0.0
                            print(f"[增强信息] 解析流通市值失败: {e}")
                    elif item == '市盈率':
                        try:
                            info_dict['市盈率-动态'] = float(value) if value else 0.0
                            print(f"[增强信息] 解析市盈率: {value} -> {info_dict['市盈率-动态']}")
                        except Exception as e:
                            info_dict['市盈率-动态'] = 0.0
                            print(f"[增强信息] 解析市盈率失败: {e}")
                    elif item == '市净率':
                        try:
                            info_dict['市净率'] = float(value) if value else 0.0
                            print(f"[增强信息] 解析市净率: {value} -> {info_dict['市净率']}")
                        except Exception as e:
                            info_dict['市净率'] = 0.0
                            print(f"[增强信息] 解析市净率失败: {e}")
                    elif item == '换手率':
                        try:
                            # 移除百分号并转换为数值
                            turnover_str = str(value).replace('%', '') if value else '0'
                            info_dict['换手率'] = float(turnover_str) if turnover_str else 0.0
                            print(f"[增强信息] 解析换手率: {value} -> {info_dict['换手率']}")
                        except Exception as e:
                            info_dict['换手率'] = 0.0
                            print(f"[增强信息] 解析换手率失败: {e}")
            
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

def get_sina_realtime_data_fixed(stock_code):
    """修复版本的新浪财经实时数据获取"""
    try:
        import requests
        import re
        
        print(f"[新浪财经] 获取{stock_code}实时数据...")
        
        # 确定市场前缀
        if stock_code.startswith('6'):
            sina_code = f'sh{stock_code}'
        else:
            sina_code = f'sz{stock_code}'
        
        url = f'http://hq.sinajs.cn/list={sina_code}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        
        if response.status_code == 200:
            content = response.text
            print(f"[新浪财经] 响应内容: {content[:100]}...")
            
            # 解析数据
            data_match = re.search(r'"([^"]*)"', content)
            if data_match:
                data_str = data_match.group(1)
                data_parts = data_str.split(',')
                
                if len(data_parts) >= 32:
                    name = data_parts[0]
                    open_price = float(data_parts[1]) if data_parts[1] else 0.0
                    pre_close = float(data_parts[2]) if data_parts[2] else 0.0
                    latest_price = float(data_parts[3]) if data_parts[3] else 0.0
                    high = float(data_parts[4]) if data_parts[4] else 0.0
                    low = float(data_parts[5]) if data_parts[5] else 0.0
                    volume = float(data_parts[8]) if data_parts[8] else 0.0
                    amount = float(data_parts[9]) if data_parts[9] else 0.0
                    
                    # 计算涨跌幅和涨跌额
                    if pre_close > 0:
                        change_amount = latest_price - pre_close
                        change_percent = (change_amount / pre_close) * 100
                        amplitude = ((high - low) / pre_close) * 100 if high > low else 0.0
                    else:
                        change_amount = 0
                        change_percent = 0
                        amplitude = 0.0
                    
                    # 获取增强信息
                    enhanced_info = get_enhanced_stock_info_fixed(stock_code)
                    
                    stock_data = {
                        '代码': stock_code,
                        '名称': name,
                        '最新价': latest_price,
                        '涨跌幅': change_percent,
                        '涨跌额': change_amount,
                        '成交量': volume,
                        '成交额': amount,
                        '振幅': amplitude,
                        '最高': high,
                        '最低': low,
                        '今开': open_price,
                        '昨收': pre_close,
                        '量比': 0.0,  # 新浪API不提供
                        '换手率': enhanced_info.get('换手率', 0.0),
                        '市盈率-动态': enhanced_info.get('市盈率-动态', 0.0),
                        '市净率': enhanced_info.get('市净率', 0.0),
                        '总市值': enhanced_info.get('总市值', 0.0),
                        '流通市值': enhanced_info.get('流通市值', 0.0),
                        '涨速': 0.0,
                        '5分钟涨跌': 0.0,
                        '60日涨跌幅': 0.0,
                        '年初至今涨跌幅': 0.0,
                        '连涨天数': 0.0,
                        '量价齐升天数': 0.0
                    }
                    
                    print(f"[新浪财经] ✅ 成功获取{stock_code}数据:")
                    print(f"  最新价: {latest_price}")
                    print(f"  总市值: {enhanced_info.get('总市值', 0.0):.2f}亿")
                    print(f"  流通市值: {enhanced_info.get('流通市值', 0.0):.2f}亿")
                    print(f"  振幅: {amplitude:.2f}%")
                    
                    return stock_data
                else:
                    print(f"[新浪财经] 数据格式不正确，字段数: {len(data_parts)}")
            else:
                print(f"[新浪财经] 无法解析响应数据")
        else:
            print(f"[新浪财经] HTTP请求失败: {response.status_code}")
        
        return None
        
    except Exception as e:
        print(f"[新浪财经] 获取{stock_code}实时数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_api_response():
    """测试API响应"""
    try:
        print("\n=== 测试API响应 ===")
        response = requests.get('http://localhost:8080/api/stock/realtime_trading_data', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                print(f"✅ API响应成功，获取到{len(data['data'])}条数据")
                
                # 查找300101
                found_300101 = False
                for item in data['data']:
                    if item.get('代码') == '300101':
                        found_300101 = True
                        print(f"\n✅ 找到300101数据:")
                        print(f"  名称: {item.get('名称')}")
                        print(f"  最新价: {item.get('最新价')}")
                        print(f"  总市值: {item.get('总市值')}")
                        print(f"  流通市值: {item.get('流通市值')}")
                        print(f"  振幅: {item.get('振幅')}")
                        print(f"  市盈率-动态: {item.get('市盈率-动态')}")
                        break
                
                if not found_300101:
                    print("❌ 未找到300101数据")
                    print("可用股票代码:")
                    for item in data['data'][:10]:
                        print(f"  {item.get('代码')}: {item.get('名称')}")
            else:
                print(f"❌ API返回错误: {data.get('error')}")
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试API失败: {e}")

def create_manual_cache_data():
    """手动创建包含300101的缓存数据"""
    try:
        print("\n=== 手动创建缓存数据 ===")
        
        # 获取300101的实时数据
        stock_data = get_sina_realtime_data_fixed('300101')
        
        if stock_data:
            # 创建缓存数据结构
            cache_data = {
                'data': [stock_data],
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'cache_date': datetime.now().strftime('%Y-%m-%d'),
                'cache_time': datetime.now().strftime('%H:%M:%S'),
                'total_count': 1
            }
            
            # 保存到缓存文件
            cache_dir = 'cache'
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            cache_file = os.path.join(cache_dir, 'realtime_trading_data_cache.json')
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 成功创建缓存文件: {cache_file}")
            print(f"缓存数据: {stock_data}")
            
            return True
        else:
            print("❌ 无法获取300101数据")
            return False
            
    except Exception as e:
        print(f"❌ 创建缓存数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=== 前端数据显示问题修复脚本 ===")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 测试增强信息获取
    print("\n1. 测试增强信息获取...")
    enhanced_info = get_enhanced_stock_info_fixed('300101')
    print(f"增强信息结果: {enhanced_info}")
    
    # 2. 测试新浪财经数据获取
    print("\n2. 测试新浪财经数据获取...")
    sina_data = get_sina_realtime_data_fixed('300101')
    print(f"新浪财经数据: {sina_data}")
    
    # 3. 测试当前API响应
    print("\n3. 测试当前API响应...")
    test_api_response()
    
    # 4. 创建手动缓存数据
    print("\n4. 创建手动缓存数据...")
    if create_manual_cache_data():
        print("\n5. 重新测试API响应...")
        test_api_response()
    
    print("\n=== 修复脚本执行完成 ===")

if __name__ == "__main__":
    main()