from flask import Flask, jsonify
from datetime import datetime, timedelta
import pandas as pd

# 尝试导入akshare
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
    print("AkShare导入成功")
except ImportError as e:
    print(f"AkShare导入失败: {e}")
    AKSHARE_AVAILABLE = False
    ak = None

# 尝试导入tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
    print("Tushare导入成功")
except ImportError as e:
    print(f"Tushare导入失败: {e}")
    TUSHARE_AVAILABLE = False
    ts = None

# 全局变量用于重试机制
last_retry_time = None
retry_interval = 30  # 30秒重试间隔

# 初始化tushare
pro = None
if TUSHARE_AVAILABLE and ts is not None:
    try:
        pro = ts.pro_api('your_tushare_token')  # 请替换为实际的token
        print("Tushare Pro API初始化成功")
    except Exception as e:
        print(f"Tushare Pro API初始化失败: {e}")
        pro = None

def get_indices_realtime():
    """获取主要指数实时数据 - 智能重试机制"""
    global last_retry_time
    
    try:
        # 定义要获取的指数代码和名称
        indices = {
            'sh000001': '上证指数',
            'sz399001': '深证成指', 
            'sz399006': '创业板指',
            'sh000688': '科创板'
        }
        
        # 检查是否需要等待重试间隔
        current_time = datetime.now()
        if last_retry_time and (current_time - last_retry_time).total_seconds() < retry_interval:
            remaining_time = retry_interval - (current_time - last_retry_time).total_seconds()
            print(f"距离下次重试还有 {remaining_time:.0f} 秒，使用缓存的模拟数据")
            return get_fallback_indices_data(indices)
        
        # 策略1: 优先使用AkShare获取实时数据
        akshare_success = False
        indices_data = None
        try:
            print("[策略1] 尝试使用AkShare获取指数实时数据...")
            indices_data = get_indices_from_akshare(indices)
            if indices_data:
                akshare_success = True
                print("[策略1] AkShare获取成功")
            else:
                print("[策略1] AkShare返回空数据")
        except Exception as e:
            print(f"[策略1] AkShare获取失败: {e}")
        
        # 策略2: AkShare失败时使用Tushare备用
        if not akshare_success:
            try:
                print("[策略2] AkShare失败，尝试使用Tushare获取数据...")
                indices_data = get_indices_from_tushare(indices)
                if indices_data:
                    print("[策略2] Tushare获取成功")
                else:
                    print("[策略2] Tushare也返回空数据")
                    raise Exception("Tushare返回空数据")
            except Exception as e:
                print(f"[策略2] Tushare也失败: {e}")
                # 两个接口都失败，记录重试时间
                last_retry_time = current_time
                print(f"[重试机制] 两个接口都失败，将在 {retry_interval} 秒后重试")
                return get_fallback_indices_data(indices)
        
        # 成功获取数据，重置重试时间
        last_retry_time = None
        
        return {
            'success': True,
            'data': indices_data,
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"获取指数数据异常: {e}")
        return {'success': False, 'error': str(e)}

def get_indices_from_akshare(indices):
    """使用AkShare获取指数数据"""
    if not AKSHARE_AVAILABLE or ak is None:
        print("AkShare不可用，跳过AkShare获取")
        return None
        
    indices_data = {}
    
    try:
        # 尝试多种AkShare接口
        sh_data = None
        
        # 方法1: 获取沪深重要指数
        try:
            if 'ak' not in globals() or ak is None:
                print("AkShare未正确导入，跳过沪深重要指数获取")
                sh_data = None
            else:
                sh_data = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
            if sh_data is not None and not sh_data.empty:
                print("AkShare方法1成功: 沪深重要指数")
        except Exception as e1:
            print(f"AkShare方法1失败: {e1}")
            
            # 方法2: 获取上证系列指数
            try:
                if 'ak' not in globals() or ak is None:
                    print("AkShare未正确导入，跳过上证系列指数获取")
                    sh_data = None
                else:
                    sh_data = ak.stock_zh_index_spot_em(symbol="上证系列指数")
                if sh_data is not None and not sh_data.empty:
                    print("AkShare方法2成功: 上证系列指数")
            except Exception as e2:
                print(f"AkShare方法2失败: {e2}")
                
                # 方法3: 分别获取各个指数
                try:
                    indices_list = []
                    current_date = datetime.now().strftime('%Y%m%d')
                    
                    for code, name in indices.items():
                        try:
                            if 'ak' not in globals() or ak is None:
                                print(f"AkShare未正确导入，跳过{name}数据获取")
                                data = None
                            elif name == '上证指数':
                                data = ak.index_zh_a_hist(symbol="000001", period="daily", start_date=current_date, end_date=current_date)
                            elif name == '深证成指':
                                data = ak.index_zh_a_hist(symbol="399001", period="daily", start_date=current_date, end_date=current_date)
                            elif name == '创业板指':
                                data = ak.index_zh_a_hist(symbol="399006", period="daily", start_date=current_date, end_date=current_date)
                            elif name == '科创板':
                                data = ak.index_zh_a_hist(symbol="000688", period="daily", start_date=current_date, end_date=current_date)
                            else:
                                data = None
                            
                            if data is not None and not data.empty:
                                latest = data.iloc[-1]
                                indices_list.append({
                                    '名称': name,
                                    '代码': code,
                                    '最新价': latest['收盘'],
                                    '涨跌额': latest['涨跌额'] if '涨跌额' in latest else latest['收盘'] - latest['开盘'],
                                    '涨跌幅': latest['涨跌幅'] if '涨跌幅' in latest else ((latest['收盘'] - latest['开盘']) / latest['开盘'] * 100),
                                    '成交额': latest['成交额'] if '成交额' in latest else 0
                                })
                        except Exception as e:
                            print(f"获取{name}数据失败: {e}")
                    
                    if indices_list:
                        sh_data = pd.DataFrame(indices_list)
                        print("AkShare方法3成功: 分别获取各指数")
                except Exception as e3:
                    print(f"AkShare方法3失败: {e3}")
                    return None
        
        if sh_data is not None and not sh_data.empty:
            # 处理获取到的数据
            for index, row in sh_data.iterrows():
                name = row['名称']
                code = row['代码']
                
                # 匹配指数名称
                matched_key = None
                for key, index_name in indices.items():
                    if index_name in name or name in index_name:
                        matched_key = key
                        break
                
                if matched_key:
                    indices_data[matched_key] = {
                        'name': indices[matched_key],
                        'code': code,
                        'price': float(row['最新价']),
                        'change': float(row['涨跌额']),
                        'change_percent': float(row['涨跌幅']),
                        'volume': float(row['成交额']) if '成交额' in row and pd.notna(row['成交额']) else 0
                    }
            
            print(f"AkShare获取到 {len(indices_data)} 个指数数据")
            return indices_data
        else:
            print("AkShare返回空数据")
            return None
            
    except Exception as e:
        print(f"AkShare获取异常: {e}")
        return None

def get_indices_from_tushare(indices):
    """使用Tushare获取指数数据"""
    if not TUSHARE_AVAILABLE or ts is None or pro is None:
        print("Tushare不可用，跳过Tushare获取")
        return None
        
    indices_data = {}
    
    try:
        current_date = datetime.now().strftime('%Y%m%d')
        
        # 获取上证指数
        try:
            df = pro.index_daily(ts_code='000001.SH', trade_date=current_date)
            if df is not None and not df.empty:
                latest = df.iloc[0]
                
                # 检查数据日期是否为当日
                data_date = pd.to_datetime(latest['trade_date']).strftime('%Y%m%d')
                if data_date != current_date:
                    print(f"Tushare数据日期不匹配: 期望 {current_date}, 实际 {data_date}")
                    raise Exception(f"数据日期不匹配: {data_date} != {current_date}")
                
                indices_data['sh000001'] = {
                    'name': '上证指数',
                    'code': '000001.SH',
                    'price': float(latest['close']),
                    'change': float(latest['change']),
                    'change_percent': float(latest['pct_chg']),
                    'volume': float(latest['amount']) if 'amount' in latest and pd.notna(latest['amount']) else 0
                }
                print(f"Tushare获取上证指数成功: 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
        except Exception as e:
            print(f"Tushare获取上证指数失败: {e}")
        
        # 获取深证成指
        try:
            df = pro.index_daily(ts_code='399001.SZ', trade_date=current_date)
            if df is not None and not df.empty:
                latest = df.iloc[0]
                
                # 检查数据日期是否为当日
                data_date = pd.to_datetime(latest['trade_date']).strftime('%Y%m%d')
                if data_date != current_date:
                    print(f"Tushare深证成指数据日期不匹配: 期望 {current_date}, 实际 {data_date}")
                    raise Exception(f"深证成指数据日期不匹配: {data_date} != {current_date}")
                
                indices_data['sz399001'] = {
                    'name': '深证成指',
                    'code': '399001.SZ',
                    'price': float(latest['close']),
                    'change': float(latest['change']),
                    'change_percent': float(latest['pct_chg']),
                    'volume': float(latest['amount']) if 'amount' in latest and pd.notna(latest['amount']) else 0
                }
                print(f"Tushare获取深证成指成功: 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
        except Exception as e:
            print(f"Tushare获取深证成指失败: {e}")
        
        # 获取创业板指
        try:
            df = pro.index_daily(ts_code='399006.SZ', trade_date=current_date)
            if df is not None and not df.empty:
                latest = df.iloc[0]
                
                # 检查数据日期是否为当日
                data_date = pd.to_datetime(latest['trade_date']).strftime('%Y%m%d')
                if data_date != current_date:
                    print(f"Tushare创业板指数据日期不匹配: 期望 {current_date}, 实际 {data_date}")
                    raise Exception(f"创业板指数据日期不匹配: {data_date} != {current_date}")
                
                indices_data['sz399006'] = {
                    'name': '创业板指',
                    'code': '399006.SZ',
                    'price': float(latest['close']),
                    'change': float(latest['change']),
                    'change_percent': float(latest['pct_chg']),
                    'volume': float(latest['amount']) if 'amount' in latest and pd.notna(latest['amount']) else 0
                }
                print(f"Tushare获取创业板指成功: 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
        except Exception as e:
            print(f"Tushare获取创业板指失败: {e}")
        
        # 获取科创板
        try:
            df = pro.index_daily(ts_code='000688.SH', trade_date=current_date)
            if df is not None and not df.empty:
                latest = df.iloc[0]
                
                # 检查数据日期是否为当日
                data_date = pd.to_datetime(latest['trade_date']).strftime('%Y%m%d')
                if data_date != current_date:
                    print(f"Tushare科创板数据日期不匹配: 期望 {current_date}, 实际 {data_date}")
                    raise Exception(f"科创板数据日期不匹配: {data_date} != {current_date}")
                
                indices_data['sh000688'] = {
                     'name': '科创板',
                     'code': '000688.SH',
                     'price': float(latest['close']),
                     'change': float(latest['change']),
                     'change_percent': float(latest['pct_chg']),
                     'volume': float(latest['amount']) if 'amount' in latest and pd.notna(latest['amount']) else 0
                 }
                print(f"Tushare获取科创板成功: 价格={latest['close']}, 涨跌幅={latest['pct_chg']}%")
        except Exception as e:
            print(f"Tushare获取科创板失败: {e}")
        
        if indices_data:
            print(f"Tushare获取到 {len(indices_data)} 个指数数据")
            return indices_data
        else:
            print("Tushare未获取到任何数据")
            return None
            
    except Exception as e:
        print(f"Tushare获取异常: {e}")
        return None

def get_fallback_indices_data(indices):
    """获取回退的模拟数据"""
    mock_data = {
        'sh000001': {'name': '上证指数', 'code': '000001.SH', 'price': 3525.0, 'change': 15.2, 'change_percent': 0.43, 'volume': 410354000000},
        'sz399001': {'name': '深证成指', 'code': '399001.SZ', 'price': 11250.5, 'change': 45.8, 'change_percent': 0.41, 'volume': 195000000000},
        'sz399006': {'name': '创业板指', 'code': '399006.SZ', 'price': 2180.3, 'change': 12.7, 'change_percent': 0.59, 'volume': 125000000000},
        'sh000688': {'name': '科创板', 'code': '000688.SH', 'price': 850.2, 'change': 8.5, 'change_percent': 1.01, 'volume': 85000000000}
    }
    
    print("使用回退模拟数据")
    return {
        'success': True,
        'data': mock_data,
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'fallback_mock_data'
    }

# 测试函数
if __name__ == "__main__":
    result = get_indices_realtime()
    print("测试结果:")
    print(result)