#!/usr/bin/env python3
"""
测试实时数据获取功能
使用与应用相同的网络配置和错误处理逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import akshare as ak
    print("✓ AkShare库已导入")
except ImportError:
    print("✗ AkShare库未安装")
    sys.exit(1)

from datetime import datetime
import pandas as pd
import time
import requests
import random
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def safe_akshare_call_test(func, *args, max_retries=3, retry_delay=2, **kwargs):
    """测试版本的安全AkShare调用，与应用中的逻辑相同"""
    
    for attempt in range(max_retries):
        try:
            print(f"[测试] 尝试调用 {func.__name__} (第{attempt + 1}次)")
            
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
                
                print(f"[测试] 已清除代理设置，直接连接...")
                result = func(*args, **adjusted_kwargs)
                print(f"[测试] {func.__name__} 调用成功")
                return result
                
            finally:
                # 恢复原始代理设置
                if old_http_proxy:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy:
                    os.environ['HTTPS_PROXY'] = old_https_proxy
                os.environ['NO_PROXY'] = old_no_proxy
            
        except requests.exceptions.ProxyError as e:
            print(f"[测试] 代理连接错误 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[测试] {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[测试] 代理连接失败，已重试{max_retries}次")
                break
                
        except requests.exceptions.ConnectionError as e:
            print(f"[测试] 网络连接错误 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[测试] {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[测试] 网络连接失败，已重试{max_retries}次")
                break
                
        except requests.exceptions.Timeout as e:
            print(f"[测试] 请求超时 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[测试] {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[测试] 请求超时，已重试{max_retries}次")
                break
                
        except Exception as e:
            print(f"[测试] API调用失败 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                print(f"[测试] {delay:.1f}秒后重试...")
                time.sleep(delay)
                continue
            else:
                print(f"[测试] API调用失败，已重试{max_retries}次")
                break
    
    print("[测试] 所有重试都失败了")
    return None

def test_akshare_realtime():
    """测试AkShare实时数据获取"""
    print("\n=== 测试AkShare实时数据获取 ===")
    
    # 检查当前代理设置
    print("当前环境变量:")
    print(f"  HTTP_PROXY: {os.environ.get('HTTP_PROXY', '未设置')}")
    print(f"  HTTPS_PROXY: {os.environ.get('HTTPS_PROXY', '未设置')}")
    print(f"  NO_PROXY: {os.environ.get('NO_PROXY', '未设置')}")
    
    df = safe_akshare_call_test(ak.stock_zh_a_spot_em)
    
    if df is not None and not df.empty:
        print(f"✓ 成功获取 {len(df)} 条数据")
        print(f"✓ 数据列名: {list(df.columns)}")
        
        # 检查前几条数据
        print("\n前3条数据示例:")
        for i, (idx, row) in enumerate(df.head(3).iterrows()):
            print(f"\n股票 {i+1}:")
            print(f"  代码: {row.get('代码', 'N/A')}")
            print(f"  名称: {row.get('名称', 'N/A')}")
            print(f"  最新价: {row.get('最新价', 'N/A')}")
            print(f"  涨跌幅: {row.get('涨跌幅', 'N/A')}")
            print(f"  量比: {row.get('量比', 'N/A')}")
            print(f"  换手率: {row.get('换手率', 'N/A')}")
            print(f"  市盈率-动态: {row.get('市盈率-动态', 'N/A')}")
            print(f"  市净率: {row.get('市净率', 'N/A')}")
            print(f"  总市值: {row.get('总市值', 'N/A')}")
            print(f"  流通市值: {row.get('流通市值', 'N/A')}")
        
        # 检查数据质量
        print("\n=== 数据质量检查 ===")
        zero_fields = []
        for col in ['量比', '换手率', '市盈率-动态', '市净率', '总市值', '流通市值']:
            if col in df.columns:
                zero_count = (df[col] == 0).sum()
                total_count = len(df)
                zero_ratio = zero_count / total_count * 100
                print(f"{col}: {zero_count}/{total_count} ({zero_ratio:.1f}%) 为0")
                if zero_ratio > 50:
                    zero_fields.append(col)
            else:
                print(f"{col}: 字段不存在")
        
        if zero_fields:
            print(f"\n⚠️  警告: 以下字段超过50%的数据为0: {', '.join(zero_fields)}")
        else:
            print("\n✓ 数据质量良好")
            
        return True
    else:
        print("✗ 获取的数据为空")
        return False

def check_trading_time():
    """检查当前是否为交易时间"""
    print("\n=== 交易时间检查 ===")
    
    now = datetime.now()
    current_time = now.time()
    is_trading_day = now.weekday() < 5  # 周一到周五
    
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"是否工作日: {'是' if is_trading_day else '否'}")
    
    # 交易时间段
    morning_start = datetime.strptime('09:25', '%H:%M').time()
    morning_end = datetime.strptime('11:35', '%H:%M').time()
    afternoon_start = datetime.strptime('12:55', '%H:%M').time()
    afternoon_end = datetime.strptime('15:05', '%H:%M').time()
    
    is_morning_session = morning_start <= current_time <= morning_end
    is_afternoon_session = afternoon_start <= current_time <= afternoon_end
    is_trading_hours = is_morning_session or is_afternoon_session
    
    print(f"上午交易时间 (09:25-11:35): {'是' if is_morning_session else '否'}")
    print(f"下午交易时间 (12:55-15:05): {'是' if is_afternoon_session else '否'}")
    print(f"当前是否交易时间: {'是' if (is_trading_day and is_trading_hours) else '否'}")
    
    return is_trading_day and is_trading_hours

def test_sina_fallback():
    """测试新浪财经备用接口"""
    print("\n=== 测试新浪财经备用接口 ===")
    
    try:
        import requests
        
        # 新浪财经实时数据接口
        url = "http://hq.sinajs.cn/list=sh000001,sz399001,sh000300"
        
        print("正在测试新浪财经接口...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            content = response.text
            print(f"✓ 新浪财经接口响应成功")
            print(f"响应内容长度: {len(content)} 字符")
            
            # 解析部分数据
            lines = content.strip().split('\n')
            for line in lines[:3]:  # 只显示前3行
                if line.strip():
                    print(f"数据示例: {line[:100]}...")
            
            return True
        else:
            print(f"✗ 新浪财经接口响应失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ 新浪财经接口测试失败: {e}")
        return False

if __name__ == "__main__":
    print("实时数据获取功能测试")
    print("=" * 50)
    
    # 检查交易时间
    is_trading_time = check_trading_time()
    
    # 测试AkShare
    akshare_success = test_akshare_realtime()
    
    # 测试新浪财经备用接口
    sina_success = test_sina_fallback()
    
    print("\n" + "=" * 50)
    print("测试结果总结:")
    print(f"交易时间: {'✓' if is_trading_time else '✗'}")
    print(f"AkShare数据获取: {'✓' if akshare_success else '✗'}")
    print(f"新浪财经备用接口: {'✓' if sina_success else '✗'}")
    
    if not is_trading_time:
        print("\n注意: 当前不是交易时间，实时数据可能不会更新")
    
    if not akshare_success and not sina_success:
        print("\n建议: 检查网络连接，所有数据源都无法访问")
    elif not akshare_success:
        print("\n建议: AkShare无法访问，但新浪财经接口可用，应用会自动切换到备用数据源")