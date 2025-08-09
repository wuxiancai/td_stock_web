#!/usr/bin/env python3
"""
模拟应用中的实时数据获取逻辑
测试AkShare和新浪财经的数据获取过程
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import requests
import random
import urllib3
import pandas as pd
from datetime import datetime

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
    print("✓ AkShare库已导入")
except ImportError:
    ak = None
    AKSHARE_AVAILABLE = False
    print("✗ AkShare库未安装")

def safe_akshare_call_app(func, cache_key, *args, max_retries=3, retry_delay=2, **kwargs):
    """模拟应用中的safe_akshare_call函数"""
    if not AKSHARE_AVAILABLE or ak is None:
        print("AkShare不可用")
        return None
    
    print(f"[AkShare] 尝试使用东财数据源...")
    
    for attempt in range(max_retries):
        try:
            print(f"[AkShare] 东财 - 尝试调用 {func.__name__} (第{attempt + 1}次)")
            
            # 过滤掉不支持的参数
            adjusted_kwargs = kwargs.copy()
            if func.__name__ == 'stock_zh_a_spot_em':
                adjusted_kwargs.pop('timeout', None)
            
            # 临时设置环境变量以优化网络连接
            old_no_proxy = os.environ.get('NO_PROXY', '')
            old_http_proxy = os.environ.get('HTTP_PROXY', '')
            old_https_proxy = os.environ.get('HTTPS_PROXY', '')
            
            try:
                # 清除代理设置，直接连接
                os.environ['NO_PROXY'] = '*'
                if 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                if 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
                
                result = func(*args, **adjusted_kwargs)
                print(f"[AkShare] 东财 - {func.__name__} 调用成功")
                return result
                
            finally:
                # 恢复原始代理设置
                if old_http_proxy:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy:
                    os.environ['HTTPS_PROXY'] = old_https_proxy
                os.environ['NO_PROXY'] = old_no_proxy
            
        except requests.exceptions.ProxyError as e:
            print(f"[AkShare] 东财 - 代理连接错误 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[AkShare] 东财 - {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[AkShare] 东财 - 代理连接失败，已重试{max_retries}次")
                break
                
        except requests.exceptions.ConnectionError as e:
            print(f"[AkShare] 东财 - 网络连接错误 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[AkShare] 东财 - {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[AkShare] 东财 - 网络连接失败，已重试{max_retries}次")
                break
                
        except requests.exceptions.Timeout as e:
            print(f"[AkShare] 东财 - 请求超时 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[AkShare] 东财 - {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[AkShare] 东财 - 请求超时，已重试{max_retries}次")
                break
                
        except Exception as e:
            print(f"[AkShare] 东财 - API调用失败 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[AkShare] 东财 - {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[AkShare] 东财 - API调用失败，已重试{max_retries}次")
                break
    
    print("[AkShare] 所有数据源都失败了")
    return None

def get_sina_batch_realtime_data_app():
    """模拟应用中的新浪财经批量数据获取"""
    try:
        import requests
        import re
        
        print("[新浪财经批量] 开始获取热门股票实时数据...")
        
        # 热门股票代码列表
        hot_stocks = [
            '000001',  # 平安银行
            '000002',  # 万科A
            '000858',  # 五粮液
            '002415',  # 海康威视
            '300059',  # 东方财富
            '300750',  # 宁德时代
            '600036',  # 招商银行
            '600519',  # 贵州茅台
            '600887',  # 伊利股份
            '002594',  # 比亚迪
            '600276',  # 恒瑞医药
            '000725',  # 京东方A
            '002230',  # 科大讯飞
        ]
        
        # 构建批量请求URL
        sina_codes = []
        for stock_code in hot_stocks:
            if stock_code.startswith('6'):
                sina_codes.append(f'sh{stock_code}')
            else:
                sina_codes.append(f'sz{stock_code}')
        
        url = f'http://hq.sinajs.cn/list={",".join(sina_codes)}'
        print(f"[新浪财经批量] 请求URL: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        
        print(f"[新浪财经批量] 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            print(f"[新浪财经批量] 响应内容长度: {len(content)}")
            
            # 解析每一行数据
            lines = content.strip().split('\n')
            processed_data = []
            
            for idx, line in enumerate(lines):
                try:
                    # 提取股票代码
                    code_match = re.search(r'var hq_str_([^=]+)=', line)
                    if not code_match:
                        continue
                    
                    sina_code = code_match.group(1)
                    stock_code = sina_code[2:]  # 去掉sh/sz前缀
                    
                    # 提取数据
                    data_match = re.search(r'"([^"]*)"', line)
                    if not data_match:
                        continue
                    
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
                        
                        # 只添加有效数据（最新价大于0）
                        if latest_price > 0:
                            stock_item = {
                                '序号': len(processed_data) + 1,
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
                                '换手率': 0.0,  # 新浪API不提供
                                '市盈率-动态': 0.0,  # 新浪API不提供
                                '市净率': 0.0,  # 新浪API不提供
                                '总市值': 0.0,  # 新浪API不提供
                                '流通市值': 0.0,  # 新浪API不提供
                                '涨速': 0.0,  # 新浪API不提供
                                '5分钟涨跌': 0.0,  # 新浪API不提供
                                '60日涨跌幅': 0.0,  # 新浪API不提供
                                '年初至今涨跌幅': 0.0,  # 新浪API不提供
                                '连涨天数': 0.0,  # 新浪API不提供
                                '量价齐升天数': 0.0  # 新浪API不提供
                            }
                            processed_data.append(stock_item)
                            print(f"[新浪财经批量] 成功解析股票: {stock_code} {name} 最新价:{latest_price}")
                        
                except Exception as e:
                    print(f"[新浪财经批量] 解析第{idx}行数据失败: {e}")
                    continue
            
            if processed_data:
                # 转换为DataFrame格式，与AkShare保持一致
                df = pd.DataFrame(processed_data)
                print(f"[新浪财经批量] ✅ 成功获取{len(processed_data)}只股票的实时数据")
                return df
            else:
                print("[新浪财经批量] ❌ 没有解析到有效数据")
                return None
        else:
            print(f"[新浪财经批量] ❌ HTTP请求失败: {response.status_code}")
            return None
        
    except Exception as e:
        print(f"[新浪财经批量] 获取批量实时数据失败: {e}")
        return None

def test_app_realtime_logic():
    """测试应用的实时数据获取逻辑"""
    print("=== 模拟应用实时数据获取逻辑 ===")
    
    # 第一步：尝试AkShare
    print("\n第一步：尝试AkShare获取实时数据")
    realtime_data = None
    
    if AKSHARE_AVAILABLE:
        realtime_data = safe_akshare_call_app(
            ak.stock_zh_a_spot_em,
            'realtime_trading_data'
        )
    
    # 第二步：如果AkShare失败，使用新浪财经
    if realtime_data is None or (hasattr(realtime_data, 'empty') and realtime_data.empty):
        print("\n第二步：AkShare失败，使用新浪财经API")
        realtime_data = get_sina_batch_realtime_data_app()
    
    # 第三步：分析数据质量
    if realtime_data is not None and not realtime_data.empty:
        print(f"\n✅ 成功获取实时数据: {len(realtime_data)} 条")
        print(f"数据列名: {list(realtime_data.columns)}")
        
        # 检查关键字段的数据质量
        print("\n=== 数据质量分析 ===")
        key_fields = ['量比', '换手率', '市盈率-动态', '市净率', '总市值', '流通市值']
        
        for field in key_fields:
            if field in realtime_data.columns:
                zero_count = (realtime_data[field] == 0).sum()
                total_count = len(realtime_data)
                zero_ratio = zero_count / total_count * 100
                print(f"{field}: {zero_count}/{total_count} ({zero_ratio:.1f}%) 为0")
        
        # 显示前3条数据示例
        print("\n前3条数据示例:")
        for i, (idx, row) in enumerate(realtime_data.head(3).iterrows()):
            print(f"\n股票 {i+1}: {row['代码']} {row['名称']}")
            print(f"  最新价: {row['最新价']}")
            print(f"  涨跌幅: {row['涨跌幅']:.2f}%")
            print(f"  量比: {row['量比']}")
            print(f"  换手率: {row['换手率']}")
            print(f"  市盈率: {row['市盈率-动态']}")
            print(f"  总市值: {row['总市值']}")
        
        return True
    else:
        print("\n❌ 所有数据源都失败了")
        return False

if __name__ == "__main__":
    print("应用实时数据获取逻辑测试")
    print("=" * 50)
    
    success = test_app_realtime_logic()
    
    print("\n" + "=" * 50)
    print("测试结果:")
    if success:
        print("✅ 实时数据获取成功")
        print("\n问题分析:")
        print("- AkShare可能由于网络问题无法访问东财接口")
        print("- 应用自动切换到新浪财经备用数据源")
        print("- 新浪财经API不提供量比、换手率、市盈率等字段")
        print("- 这就是为什么这些字段显示为0的原因")
        print("\n建议解决方案:")
        print("1. 检查网络连接，确保能访问东财接口")
        print("2. 考虑增加其他数据源（如腾讯财经）")
        print("3. 对于新浪财经数据，可以通过其他接口补充缺失字段")
    else:
        print("❌ 实时数据获取失败")
        print("建议检查网络连接和数据源可用性")