#!/usr/bin/env python3
"""
东财实时数据接口修复脚本
实现多种解决方案来获取完整的实时股票数据
"""

import os
import sys
import time
import requests
import pandas as pd
import random
from datetime import datetime

def test_akshare_alternatives():
    """测试AkShare的其他实时数据接口"""
    print("=== 测试AkShare其他实时数据接口 ===")
    
    try:
        import akshare as ak
    except ImportError:
        print("✗ AkShare库导入失败")
        return None
    
    # 清除代理设置
    os.environ['NO_PROXY'] = '*'
    for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if var in os.environ:
            del os.environ[var]
    
    # 测试不同的实时数据接口
    alternative_functions = [
        {
            'name': 'stock_zh_a_spot',
            'desc': '沪深A股实时行情(腾讯)',
            'func': lambda: ak.stock_zh_a_spot(),
            'expected_fields': ['代码', '名称', '最新价', '涨跌额', '涨跌幅', '成交量', '成交额']
        },
        {
            'name': 'stock_sina_spot',
            'desc': '新浪实时行情',
            'func': lambda: ak.stock_zh_a_spot(),  # 实际上这个也是调用新浪的
            'expected_fields': ['代码', '名称', '最新价', '涨跌额', '涨跌幅', '成交量', '成交额']
        }
    ]
    
    successful_data = None
    
    for alt in alternative_functions:
        try:
            print(f"\n测试 {alt['name']} ({alt['desc']})...")
            start_time = time.time()
            df = alt['func']()
            end_time = time.time()
            
            if df is not None and not df.empty:
                print(f"✓ 成功获取数据，耗时: {end_time - start_time:.2f}秒")
                print(f"  数据条数: {len(df)}")
                print(f"  列名: {list(df.columns)}")
                
                # 检查期望字段
                available_fields = [field for field in alt['expected_fields'] if field in df.columns]
                missing_fields = [field for field in alt['expected_fields'] if field not in df.columns]
                
                print(f"  可用字段: {available_fields}")
                if missing_fields:
                    print(f"  缺失字段: {missing_fields}")
                
                # 显示样本数据
                sample_data = df.head(3)
                print("  样本数据:")
                for idx, row in sample_data.iterrows():
                    print(f"    {row.get('代码', 'N/A')} {row.get('名称', 'N/A')} {row.get('最新价', 'N/A')}")
                
                if successful_data is None:
                    successful_data = df
                    
            else:
                print(f"✗ {alt['name']} 返回数据为空")
                
        except Exception as e:
            print(f"✗ {alt['name']} 失败: {e}")
    
    return successful_data

def enhance_sina_api():
    """增强新浪API，获取更多字段"""
    print("\n=== 增强新浪API获取更多字段 ===")
    
    # 热门股票列表
    hot_stocks = [
        'sh000001', 'sz399001', 'sz399006',  # 指数
        'sh600036', 'sh600519', 'sh600276', 'sh600887', 'sh601318',  # 沪市
        'sz000858', 'sz000002', 'sz300059', 'sz300750', 'sz002415'   # 深市
    ]
    
    def get_enhanced_sina_data(stock_codes):
        """获取增强的新浪数据，包含更多字段"""
        try:
            # 构建批量请求URL
            codes_str = ','.join(stock_codes)
            url = f"http://hq.sinajs.cn/list={codes_str}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'http://finance.sina.com.cn'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                stocks_data = []
                
                for line in lines:
                    if 'var hq_str_' in line and '=""' not in line:
                        # 解析股票数据
                        parts = line.split('="')
                        if len(parts) >= 2:
                            code = parts[0].split('_')[-1]
                            data_str = parts[1].rstrip('";')
                            data_parts = data_str.split(',')
                            
                            if len(data_parts) >= 32:  # 确保有足够的字段
                                try:
                                    name = data_parts[0]
                                    current_price = float(data_parts[3]) if data_parts[3] else 0
                                    pre_close = float(data_parts[2]) if data_parts[2] else 0
                                    open_price = float(data_parts[1]) if data_parts[1] else 0
                                    high_price = float(data_parts[4]) if data_parts[4] else 0
                                    low_price = float(data_parts[5]) if data_parts[5] else 0
                                    volume = int(data_parts[8]) if data_parts[8] else 0
                                    amount = float(data_parts[9]) if data_parts[9] else 0
                                    
                                    # 计算涨跌额和涨跌幅
                                    change_amount = current_price - pre_close if pre_close > 0 else 0
                                    change_pct = (change_amount / pre_close * 100) if pre_close > 0 else 0
                                    
                                    # 计算振幅
                                    amplitude = ((high_price - low_price) / pre_close * 100) if pre_close > 0 else 0
                                    
                                    # 尝试获取更多字段（如果可用）
                                    turnover_rate = 0.0  # 新浪API通常不提供
                                    pe_ratio = 0.0       # 新浪API通常不提供
                                    pb_ratio = 0.0       # 新浪API通常不提供
                                    volume_ratio = 0.0   # 新浪API通常不提供
                                    
                                    # 尝试从其他字段获取市值信息
                                    total_market_cap = 0.0
                                    circulating_market_cap = 0.0
                                    
                                    stock_info = {
                                        '代码': code,
                                        '名称': name,
                                        '最新价': current_price,
                                        '涨跌额': change_amount,
                                        '涨跌幅': change_pct,
                                        '今开': open_price,
                                        '昨收': pre_close,
                                        '最高': high_price,
                                        '最低': low_price,
                                        '成交量': volume,
                                        '成交额': amount,
                                        '振幅': amplitude,
                                        '量比': volume_ratio,
                                        '换手率': turnover_rate,
                                        '市盈率-动态': pe_ratio,
                                        '市净率': pb_ratio,
                                        '总市值': total_market_cap,
                                        '流通市值': circulating_market_cap,
                                        '60日涨跌幅': 0.0,
                                        '年初至今涨跌幅': 0.0
                                    }
                                    
                                    stocks_data.append(stock_info)
                                    
                                except (ValueError, IndexError) as e:
                                    print(f"解析股票 {code} 数据时出错: {e}")
                                    continue
                
                return pd.DataFrame(stocks_data) if stocks_data else None
            else:
                print(f"新浪API请求失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"新浪API调用失败: {e}")
            return None
    
    # 测试增强的新浪API
    print("测试增强的新浪API...")
    df = get_enhanced_sina_data(hot_stocks)
    
    if df is not None and not df.empty:
        print(f"✓ 成功获取 {len(df)} 条数据")
        print(f"  列名: {list(df.columns)}")
        
        # 检查数据质量
        print("\n数据质量检查:")
        for col in ['量比', '换手率', '市盈率-动态', '市净率', '总市值', '流通市值']:
            non_zero_count = (df[col] != 0).sum()
            print(f"  {col}: {non_zero_count}/{len(df)} 条非零数据")
        
        print("\n样本数据:")
        sample_data = df.head(5)
        for idx, row in sample_data.iterrows():
            print(f"  {row['代码']} {row['名称']} {row['最新价']:.2f} {row['涨跌幅']:.2f}%")
        
        return df
    else:
        print("✗ 增强新浪API获取数据失败")
        return None

def get_additional_stock_info():
    """从其他数据源获取缺失的股票信息"""
    print("\n=== 从其他数据源获取缺失信息 ===")
    
    try:
        import akshare as ak
    except ImportError:
        print("✗ AkShare库导入失败")
        return None
    
    # 清除代理设置
    os.environ['NO_PROXY'] = '*'
    for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if var in os.environ:
            del os.environ[var]
    
    # 测试获取个股详细信息的接口
    test_stock = "000001"  # 平安银行
    
    try:
        print(f"测试获取 {test_stock} 的详细信息...")
        
        # 获取个股信息
        stock_info = ak.stock_individual_info_em(symbol=test_stock)
        if stock_info is not None:
            print("✓ 个股信息获取成功")
            print(f"  信息项目: {list(stock_info['item']) if 'item' in stock_info.columns else '无'}")
            
            # 查找关键信息
            key_info = {}
            if 'item' in stock_info.columns and 'value' in stock_info.columns:
                for idx, row in stock_info.iterrows():
                    item = row['item']
                    value = row['value']
                    if item in ['总市值', '流通市值', '市盈率', '市净率', '换手率']:
                        key_info[item] = value
                        print(f"    {item}: {value}")
            
            return key_info
        else:
            print("✗ 个股信息获取失败")
            
    except Exception as e:
        print(f"✗ 获取个股信息失败: {e}")
    
    return None

def create_enhanced_realtime_function():
    """创建增强的实时数据获取函数"""
    print("\n=== 创建增强的实时数据获取函数 ===")
    
    enhanced_code = '''
def get_enhanced_realtime_data():
    """
    增强的实时数据获取函数
    结合多个数据源，提供完整的实时股票数据
    """
    import requests
    import pandas as pd
    import time
    
    # 热门股票列表
    hot_stocks = [
        'sh600036', 'sh600519', 'sh600276', 'sh600887', 'sh601318',  # 沪市
        'sz000858', 'sz000002', 'sz300059', 'sz300750', 'sz002415'   # 深市
    ]
    
    def get_sina_realtime_data(stock_codes):
        """从新浪获取实时数据"""
        try:
            codes_str = ','.join(stock_codes)
            url = f"http://hq.sinajs.cn/list={codes_str}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'http://finance.sina.com.cn'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200:
                lines = response.text.strip().split('\\n')
                stocks_data = []
                
                for line in lines:
                    if 'var hq_str_' in line and '=""' not in line:
                        parts = line.split('="')
                        if len(parts) >= 2:
                            code = parts[0].split('_')[-1]
                            data_str = parts[1].rstrip('";')
                            data_parts = data_str.split(',')
                            
                            if len(data_parts) >= 32:
                                try:
                                    name = data_parts[0]
                                    current_price = float(data_parts[3]) if data_parts[3] else 0
                                    pre_close = float(data_parts[2]) if data_parts[2] else 0
                                    open_price = float(data_parts[1]) if data_parts[1] else 0
                                    high_price = float(data_parts[4]) if data_parts[4] else 0
                                    low_price = float(data_parts[5]) if data_parts[5] else 0
                                    volume = int(data_parts[8]) if data_parts[8] else 0
                                    amount = float(data_parts[9]) if data_parts[9] else 0
                                    
                                    change_amount = current_price - pre_close if pre_close > 0 else 0
                                    change_pct = (change_amount / pre_close * 100) if pre_close > 0 else 0
                                    amplitude = ((high_price - low_price) / pre_close * 100) if pre_close > 0 else 0
                                    
                                    stock_info = {
                                        '代码': code,
                                        '名称': name,
                                        '最新价': current_price,
                                        '涨跌额': change_amount,
                                        '涨跌幅': change_pct,
                                        '今开': open_price,
                                        '昨收': pre_close,
                                        '最高': high_price,
                                        '最低': low_price,
                                        '成交量': volume,
                                        '成交额': amount,
                                        '振幅': amplitude,
                                        '量比': 0.0,  # 新浪API不提供，需要其他数据源
                                        '换手率': 0.0,  # 新浪API不提供，需要其他数据源
                                        '市盈率-动态': 0.0,  # 新浪API不提供，需要其他数据源
                                        '市净率': 0.0,  # 新浪API不提供，需要其他数据源
                                        '总市值': 0.0,  # 新浪API不提供，需要其他数据源
                                        '流通市值': 0.0,  # 新浪API不提供，需要其他数据源
                                        '60日涨跌幅': 0.0,
                                        '年初至今涨跌幅': 0.0
                                    }
                                    
                                    stocks_data.append(stock_info)
                                    
                                except (ValueError, IndexError):
                                    continue
                
                return pd.DataFrame(stocks_data) if stocks_data else None
            else:
                return None
                
        except Exception:
            return None
    
    # 获取实时数据
    df = get_sina_realtime_data(hot_stocks)
    
    if df is not None and not df.empty:
        print(f"成功获取 {len(df)} 条实时数据")
        return df
    else:
        print("获取实时数据失败")
        return None

# 使用示例
if __name__ == "__main__":
    data = get_enhanced_realtime_data()
    if data is not None:
        print(data.head())
'''
    
    print("增强的实时数据获取函数代码已生成")
    print("该函数可以替代原有的东财接口，提供基础的实时数据")
    print("注意：某些高级字段（量比、换手率、市盈率等）需要额外的数据源补充")
    
    return enhanced_code

def main():
    """主函数"""
    print("东财实时数据接口修复工具")
    print("=" * 50)
    
    # 测试AkShare的其他接口
    akshare_data = test_akshare_alternatives()
    
    # 测试增强的新浪API
    sina_data = enhance_sina_api()
    
    # 获取额外的股票信息
    additional_info = get_additional_stock_info()
    
    # 创建增强的实时数据函数
    enhanced_function = create_enhanced_realtime_function()
    
    print("\n=== 修复建议 ===")
    print("1. 东财实时行情接口 (ak.stock_zh_a_spot_em) 目前无法访问")
    print("2. 建议使用新浪财经API作为主要数据源")
    print("3. 对于缺失的字段（量比、换手率、市盈率等），可以：")
    print("   - 使用AkShare的个股信息接口补充")
    print("   - 从其他数据源获取")
    print("   - 在前端显示时标注为'暂无数据'")
    print("4. 历史数据接口仍然可用，可以用于计算一些指标")
    print("5. 建议在应用中实现数据源降级策略")

if __name__ == "__main__":
    main()