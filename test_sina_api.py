#!/usr/bin/env python3
"""
测试新浪财经API实时数据获取功能
"""

import requests
import re
from datetime import datetime

def test_sina_realtime_api():
    """测试新浪财经实时数据API"""
    print("=== 测试新浪财经实时数据API ===")
    
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
    ]
    
    # 构建批量请求URL
    sina_codes = []
    for stock_code in hot_stocks:
        if stock_code.startswith('6'):
            sina_codes.append(f'sh{stock_code}')
        else:
            sina_codes.append(f'sz{stock_code}')
    
    url = f'http://hq.sinajs.cn/list={",".join(sina_codes)}'
    print(f"请求URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'http://finance.sina.com.cn/'
    }
    
    try:
        print("正在发送请求...")
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'gbk'
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容长度: {len(response.text)}")
        
        if response.status_code == 200:
            content = response.text
            lines = content.strip().split('\n')
            
            print(f"\n成功获取 {len(lines)} 行数据")
            print("\n解析结果:")
            print("-" * 80)
            
            valid_count = 0
            for idx, line in enumerate(lines):
                try:
                    # 提取股票代码
                    code_match = re.search(r'var hq_str_([^=]+)=', line)
                    if not code_match:
                        print(f"第{idx+1}行: 无法提取股票代码")
                        continue
                    
                    sina_code = code_match.group(1)
                    stock_code = sina_code[2:]  # 去掉sh/sz前缀
                    
                    # 提取数据
                    data_match = re.search(r'"([^"]*)"', line)
                    if not data_match:
                        print(f"第{idx+1}行: 无法提取数据内容")
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
                        
                        # 计算涨跌幅
                        if pre_close > 0:
                            change_amount = latest_price - pre_close
                            change_percent = (change_amount / pre_close) * 100
                        else:
                            change_amount = 0
                            change_percent = 0
                        
                        if latest_price > 0:
                            valid_count += 1
                            print(f"✓ {stock_code} {name}")
                            print(f"  最新价: {latest_price:.2f}")
                            print(f"  涨跌幅: {change_percent:.2f}%")
                            print(f"  涨跌额: {change_amount:.2f}")
                            print(f"  成交量: {volume:,.0f}")
                            print(f"  成交额: {amount:,.0f}")
                            print(f"  今开: {open_price:.2f}")
                            print(f"  最高: {high:.2f}")
                            print(f"  最低: {low:.2f}")
                            print(f"  昨收: {pre_close:.2f}")
                            print()
                        else:
                            print(f"✗ {stock_code} {name}: 最新价为0，可能停牌")
                    else:
                        print(f"第{idx+1}行: 数据字段不足 (只有{len(data_parts)}个字段)")
                        
                except Exception as e:
                    print(f"第{idx+1}行解析失败: {e}")
                    continue
            
            print("-" * 80)
            print(f"总计: {len(lines)} 行数据，{valid_count} 只股票有效")
            
            # 检查数据质量
            if valid_count > 0:
                print("✓ 新浪财经API工作正常")
                return True
            else:
                print("✗ 新浪财经API返回数据无效")
                return False
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
            if response.text:
                print(f"错误内容: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ 请求超时")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ 连接错误: {e}")
        return False
    except Exception as e:
        print(f"✗ 其他错误: {e}")
        return False

def test_single_stock():
    """测试单只股票的数据获取"""
    print("\n=== 测试单只股票数据获取 ===")
    
    stock_code = "000001"  # 平安银行
    url = f"http://hq.sinajs.cn/list=sz{stock_code}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'http://finance.sina.com.cn/'
    }
    
    try:
        print(f"测试股票: {stock_code}")
        print(f"请求URL: {url}")
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"单只股票测试失败: {e}")
        return False

def check_trading_time():
    """检查当前是否为交易时间"""
    print("=== 交易时间检查 ===")
    
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

if __name__ == "__main__":
    print("新浪财经API测试")
    print("=" * 50)
    
    # 检查交易时间
    is_trading_time = check_trading_time()
    
    # 测试单只股票
    single_success = test_single_stock()
    
    # 测试批量股票
    batch_success = test_sina_realtime_api()
    
    print("\n" + "=" * 50)
    print("测试结果总结:")
    print(f"交易时间: {'✓' if is_trading_time else '✗'}")
    print(f"单只股票API: {'✓' if single_success else '✗'}")
    print(f"批量股票API: {'✓' if batch_success else '✗'}")
    
    if not is_trading_time:
        print("\n注意: 当前不是交易时间，数据可能不是最新的")
    
    if single_success and batch_success:
        print("\n✓ 新浪财经API工作正常，应用可以使用备用数据源")
    elif single_success:
        print("\n⚠️  单只股票API正常，但批量API有问题")
    else:
        print("\n✗ 新浪财经API无法访问")