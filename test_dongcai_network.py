#!/usr/bin/env python3
"""
东财接口网络诊断脚本
测试不同的网络配置和连接方式，诊断东财接口连接问题
"""

import os
import sys
import time
import requests
import socket
import urllib3
from urllib.parse import urlparse

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_network_connectivity():
    """测试基础网络连接"""
    print("=== 基础网络连接测试 ===")
    
    # 测试DNS解析
    test_hosts = [
        'quote.eastmoney.com',
        '82.push2.eastmoney.com',
        'push2.eastmoney.com',
        'datacenter-web.eastmoney.com',
        'www.baidu.com'  # 对照组
    ]
    
    for host in test_hosts:
        try:
            ip = socket.gethostbyname(host)
            print(f"✓ DNS解析 {host} -> {ip}")
        except socket.gaierror as e:
            print(f"✗ DNS解析失败 {host}: {e}")
    
    print()

def test_http_connectivity():
    """测试HTTP连接"""
    print("=== HTTP连接测试 ===")
    
    test_urls = [
        'http://quote.eastmoney.com',
        'https://quote.eastmoney.com',
        'http://82.push2.eastmoney.com',
        'https://82.push2.eastmoney.com',
        'http://push2.eastmoney.com',
        'https://push2.eastmoney.com',
        'https://datacenter-web.eastmoney.com',
        'https://www.baidu.com'  # 对照组
    ]
    
    for url in test_urls:
        try:
            response = requests.get(url, timeout=10, verify=False)
            print(f"✓ HTTP连接 {url} -> {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            print(f"✗ HTTP连接失败 {url}: {e}")
        except requests.exceptions.Timeout as e:
            print(f"✗ HTTP超时 {url}: {e}")
        except Exception as e:
            print(f"✗ HTTP错误 {url}: {e}")
    
    print()

def test_proxy_settings():
    """测试代理设置"""
    print("=== 代理设置测试 ===")
    
    # 显示当前代理设置
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy']
    for var in proxy_vars:
        value = os.environ.get(var, '未设置')
        print(f"  {var}: {value}")
    
    print()

def test_akshare_dongcai():
    """测试AkShare东财接口"""
    print("=== AkShare东财接口测试 ===")
    
    try:
        import akshare as ak
        print("✓ AkShare库导入成功")
    except ImportError:
        print("✗ AkShare库导入失败")
        return
    
    # 保存原始环境变量
    original_env = {}
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy']
    for var in proxy_vars:
        original_env[var] = os.environ.get(var)
    
    # 测试不同的网络配置
    test_configs = [
        {
            'name': '默认配置',
            'env_changes': {}
        },
        {
            'name': '清除所有代理',
            'env_changes': {
                'HTTP_PROXY': None,
                'HTTPS_PROXY': None,
                'http_proxy': None,
                'https_proxy': None,
                'NO_PROXY': '*'
            }
        },
        {
            'name': '仅清除HTTPS代理',
            'env_changes': {
                'HTTPS_PROXY': None,
                'https_proxy': None,
            }
        }
    ]
    
    for config in test_configs:
        print(f"\n--- 测试配置: {config['name']} ---")
        
        # 应用环境变量更改
        for var, value in config['env_changes'].items():
            if value is None:
                if var in os.environ:
                    del os.environ[var]
            else:
                os.environ[var] = value
        
        try:
            print("尝试调用 ak.stock_zh_a_spot_em()...")
            start_time = time.time()
            df = ak.stock_zh_a_spot_em()
            end_time = time.time()
            
            if df is not None and not df.empty:
                print(f"✓ 成功获取数据，耗时: {end_time - start_time:.2f}秒")
                print(f"  数据条数: {len(df)}")
                print(f"  列名: {list(df.columns)}")
                
                # 检查关键字段
                key_fields = ['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '量比', '换手率', '市盈率-动态', '市净率']
                available_fields = [field for field in key_fields if field in df.columns]
                missing_fields = [field for field in key_fields if field not in df.columns]
                
                print(f"  可用字段: {available_fields}")
                if missing_fields:
                    print(f"  缺失字段: {missing_fields}")
                
                # 检查数据质量
                sample_data = df.head(3)
                print("  样本数据:")
                for idx, row in sample_data.iterrows():
                    print(f"    {row.get('代码', 'N/A')} {row.get('名称', 'N/A')} {row.get('最新价', 'N/A')}")
                
                break  # 成功后退出测试
            else:
                print("✗ 返回数据为空")
                
        except requests.exceptions.ProxyError as e:
            print(f"✗ 代理错误: {e}")
        except requests.exceptions.ConnectionError as e:
            print(f"✗ 连接错误: {e}")
        except requests.exceptions.Timeout as e:
            print(f"✗ 超时错误: {e}")
        except Exception as e:
            print(f"✗ 其他错误: {e}")
    
    # 恢复原始环境变量
    for var, value in original_env.items():
        if value is None:
            if var in os.environ:
                del os.environ[var]
        else:
            os.environ[var] = value
    
    print()

def test_alternative_dongcai_apis():
    """测试其他东财API接口"""
    print("=== 其他东财API接口测试 ===")
    
    try:
        import akshare as ak
    except ImportError:
        print("✗ AkShare库导入失败")
        return
    
    # 清除代理设置
    os.environ['NO_PROXY'] = '*'
    for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if var in os.environ:
            del os.environ[var]
    
    # 测试其他东财相关接口
    test_functions = [
        ('ak.stock_zh_a_hist', '历史数据', lambda: ak.stock_zh_a_hist("000001", period="daily", start_date="20250101", end_date="20250806")),
        ('ak.stock_individual_info_em', '个股信息', lambda: ak.stock_individual_info_em(symbol="000001")),
        ('ak.stock_zh_index_spot_em', '指数实时', lambda: ak.stock_zh_index_spot_em()),
    ]
    
    for func_name, desc, func_call in test_functions:
        try:
            print(f"测试 {func_name} ({desc})...")
            start_time = time.time()
            result = func_call()
            end_time = time.time()
            
            if result is not None:
                if hasattr(result, '__len__'):
                    print(f"✓ {func_name} 成功，耗时: {end_time - start_time:.2f}秒，数据量: {len(result)}")
                else:
                    print(f"✓ {func_name} 成功，耗时: {end_time - start_time:.2f}秒")
            else:
                print(f"✗ {func_name} 返回空数据")
                
        except Exception as e:
            print(f"✗ {func_name} 失败: {e}")
    
    print()

def main():
    """主函数"""
    print("东财接口网络诊断工具")
    print("=" * 50)
    
    test_network_connectivity()
    test_http_connectivity()
    test_proxy_settings()
    test_akshare_dongcai()
    test_alternative_dongcai_apis()
    
    print("=== 诊断建议 ===")
    print("1. 如果DNS解析失败，请检查网络连接和DNS设置")
    print("2. 如果HTTP连接失败，可能是防火墙或网络策略问题")
    print("3. 如果代理设置有问题，尝试清除代理或配置正确的代理")
    print("4. 如果AkShare调用失败，可能需要更新AkShare版本或使用其他数据源")
    print("5. 建议使用新浪财经API作为备用数据源")

if __name__ == "__main__":
    main()