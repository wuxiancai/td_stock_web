#!/usr/bin/env python3
"""
独立的资金流向数据处理模块
严格按照Tushare官方文档 moneyflow 接口实现
文档地址: https://tushare.pro/document/2?doc_id=170
"""

import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MoneyflowHandler:
    """
    资金流向数据处理器
    严格按照Tushare官方文档实现
    """
    
    def __init__(self, token: str):
        """
        初始化资金流向处理器
        
        Args:
            token: Tushare API token
        """
        self.pro = ts.pro_api(token)
        
    def get_moneyflow_data(self, 
                          ts_code: str, 
                          trade_date: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          days: int = 1) -> Dict:
        """
        获取股票资金流向数据
        严格按照Tushare官方文档 moneyflow 接口
        
        Args:
            ts_code: 股票代码，如 000001.SZ
            trade_date: 交易日期 YYYYMMDD
            start_date: 开始日期 YYYYMMDD  
            end_date: 结束日期 YYYYMMDD
            days: 获取天数，默认1天
            
        Returns:
            Dict: 包含资金流向数据的字典
            
        官方文档输出参数:
            - ts_code: TS代码
            - trade_date: 交易日期
            - buy_sm_vol: 小单买入量（手）
            - buy_sm_amount: 小单买入金额（万元）
            - sell_sm_vol: 小单卖出量（手）
            - sell_sm_amount: 小单卖出金额（万元）
            - buy_md_vol: 中单买入量（手）
            - buy_md_amount: 中单买入金额（万元）
            - sell_md_vol: 中单卖出量（手）
            - sell_md_amount: 中单卖出金额（万元）
            - buy_lg_vol: 大单买入量（手）
            - buy_lg_amount: 大单买入金额（万元）
            - sell_lg_vol: 大单卖出量（手）
            - sell_lg_amount: 大单卖出金额（万元）
            - buy_elg_vol: 特大单买入量（手）
            - buy_elg_amount: 特大单买入金额（万元）
            - sell_elg_vol: 特大单卖出量（手）
            - sell_elg_amount: 特大单卖出金额（万元）
            - net_mf_vol: 净流入量（手）
            - net_mf_amount: 净流入额（万元）
        """
        try:
            logger.info(f"获取{ts_code}的资金流向数据")
            
            # 验证股票代码
            if not self._validate_stock_code(ts_code):
                return {'success': False, 'error': '无效的股票代码'}
            
            # 构建查询参数
            params = {'ts_code': ts_code}
            
            if trade_date:
                params['trade_date'] = trade_date
            elif start_date and end_date:
                params['start_date'] = start_date
                params['end_date'] = end_date
            elif days > 1:
                # 计算日期范围
                if not trade_date:
                    trade_date = self._get_latest_trading_day()
                end_date = datetime.strptime(trade_date, '%Y%m%d')
                start_date = end_date - timedelta(days=days-1)
                params['start_date'] = start_date.strftime('%Y%m%d')
                params['end_date'] = trade_date
            else:
                if not trade_date:
                    trade_date = self._get_latest_trading_day()
                params['trade_date'] = trade_date
            
            # 调用Tushare API
            df = self.pro.moneyflow(**params)
            
            if df.empty:
                logger.warning(f"未获取到{ts_code}的资金流向数据")
                return {
                    'success': True,
                    'data': [],
                    'message': '暂无资金流向数据'
                }
            
            # 转换数据格式
            data_list = []
            for _, row in df.iterrows():
                data_list.append({
                    'ts_code': row['ts_code'],
                    'trade_date': row['trade_date'],
                    'buy_sm_vol': int(row['buy_sm_vol']) if pd.notna(row['buy_sm_vol']) else 0,
                    'buy_sm_amount': float(row['buy_sm_amount']) if pd.notna(row['buy_sm_amount']) else 0.0,
                    'sell_sm_vol': int(row['sell_sm_vol']) if pd.notna(row['sell_sm_vol']) else 0,
                    'sell_sm_amount': float(row['sell_sm_amount']) if pd.notna(row['sell_sm_amount']) else 0.0,
                    'buy_md_vol': int(row['buy_md_vol']) if pd.notna(row['buy_md_vol']) else 0,
                    'buy_md_amount': float(row['buy_md_amount']) if pd.notna(row['buy_md_amount']) else 0.0,
                    'sell_md_vol': int(row['sell_md_vol']) if pd.notna(row['sell_md_vol']) else 0,
                    'sell_md_amount': float(row['sell_md_amount']) if pd.notna(row['sell_md_amount']) else 0.0,
                    'buy_lg_vol': int(row['buy_lg_vol']) if pd.notna(row['buy_lg_vol']) else 0,
                    'buy_lg_amount': float(row['buy_lg_amount']) if pd.notna(row['buy_lg_amount']) else 0.0,
                    'sell_lg_vol': int(row['sell_lg_vol']) if pd.notna(row['sell_lg_vol']) else 0,
                    'sell_lg_amount': float(row['sell_lg_amount']) if pd.notna(row['sell_lg_amount']) else 0.0,
                    'buy_elg_vol': int(row['buy_elg_vol']) if pd.notna(row['buy_elg_vol']) else 0,
                    'buy_elg_amount': float(row['buy_elg_amount']) if pd.notna(row['buy_elg_amount']) else 0.0,
                    'sell_elg_vol': int(row['sell_elg_vol']) if pd.notna(row['sell_elg_vol']) else 0,
                    'sell_elg_amount': float(row['sell_elg_amount']) if pd.notna(row['sell_elg_amount']) else 0.0,
                    'net_mf_vol': int(row['net_mf_vol']) if pd.notna(row['net_mf_vol']) else 0,
                    'net_mf_amount': float(row['net_mf_amount']) if pd.notna(row['net_mf_amount']) else 0.0
                })
            
            logger.info(f"成功获取{ts_code}的{len(data_list)}条资金流向数据")
            
            return {
                'success': True,
                'data': data_list,
                'stock_info': {
                    'ts_code': ts_code,
                    'trade_date': params.get('trade_date', params.get('end_date'))
                },
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"获取{ts_code}资金流向数据失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def format_moneyflow_amount(self, amount: float, unit_type: str = 'auto') -> str:
        """
        格式化资金流向金额
        根据Tushare官方文档，所有金额字段单位都是万元
        
        Args:
            amount: 金额（万元）
            unit_type: 单位类型 ('auto', 'wan', 'yi')
            
        Returns:
            str: 格式化后的金额字符串
        """
        if amount is None or amount == 0:
            return '--'
        
        abs_amount = abs(amount)
        
        if unit_type == 'auto':
            # 自动选择单位
            if abs_amount >= 10000:  # 大于等于1亿万元，显示为亿元
                return f"{amount / 10000:.3f}亿元"
            else:  # 小于1亿万元，显示为万元
                return f"{amount:.0f}万元"
        elif unit_type == 'yi':
            return f"{amount / 10000:.3f}亿元"
        elif unit_type == 'wan':
            return f"{amount:.0f}万元"
        else:
            return f"{amount:.2f}"
    
    def format_moneyflow_volume(self, volume: int) -> str:
        """
        格式化资金流向成交量
        
        Args:
            volume: 成交量（手）
            
        Returns:
            str: 格式化后的成交量字符串
        """
        if volume is None or volume == 0:
            return '--'
        
        abs_volume = abs(volume)
        
        if abs_volume >= 100000000:  # 大于等于1亿手
            return f"{volume / 100000000:.2f}亿手"
        elif abs_volume >= 10000:  # 大于等于1万手
            return f"{volume / 10000:.2f}万手"
        else:
            return f"{volume}手"
    
    def calculate_net_inflow_summary(self, data: List[Dict]) -> Dict:
        """
        计算净流入汇总信息
        
        Args:
            data: 资金流向数据列表
            
        Returns:
            Dict: 汇总信息
        """
        if not data:
            return {
                'total_net_amount': 0.0,
                'total_net_volume': 0,
                'avg_net_amount': 0.0,
                'positive_days': 0,
                'negative_days': 0,
                'total_days': 0
            }
        
        total_net_amount = sum(item['net_mf_amount'] for item in data)
        total_net_volume = sum(item['net_mf_vol'] for item in data)
        positive_days = sum(1 for item in data if item['net_mf_amount'] > 0)
        negative_days = sum(1 for item in data if item['net_mf_amount'] < 0)
        total_days = len(data)
        avg_net_amount = total_net_amount / total_days if total_days > 0 else 0.0
        
        return {
            'total_net_amount': total_net_amount,
            'total_net_volume': total_net_volume,
            'avg_net_amount': avg_net_amount,
            'positive_days': positive_days,
            'negative_days': negative_days,
            'total_days': total_days
        }
    
    def get_moneyflow_categories(self, data: Dict) -> Dict:
        """
        获取各类别资金流向汇总
        
        Args:
            data: 单日资金流向数据
            
        Returns:
            Dict: 各类别汇总
        """
        if not data:
            return {}
        
        return {
            'small_order': {  # 小单：5万以下
                'buy_amount': data.get('buy_sm_amount', 0),
                'sell_amount': data.get('sell_sm_amount', 0),
                'net_amount': data.get('buy_sm_amount', 0) - data.get('sell_sm_amount', 0),
                'buy_volume': data.get('buy_sm_vol', 0),
                'sell_volume': data.get('sell_sm_vol', 0),
                'net_volume': data.get('buy_sm_vol', 0) - data.get('sell_sm_vol', 0)
            },
            'medium_order': {  # 中单：5万～20万
                'buy_amount': data.get('buy_md_amount', 0),
                'sell_amount': data.get('sell_md_amount', 0),
                'net_amount': data.get('buy_md_amount', 0) - data.get('sell_md_amount', 0),
                'buy_volume': data.get('buy_md_vol', 0),
                'sell_volume': data.get('sell_md_vol', 0),
                'net_volume': data.get('buy_md_vol', 0) - data.get('sell_md_vol', 0)
            },
            'large_order': {  # 大单：20万～100万
                'buy_amount': data.get('buy_lg_amount', 0),
                'sell_amount': data.get('sell_lg_amount', 0),
                'net_amount': data.get('buy_lg_amount', 0) - data.get('sell_lg_amount', 0),
                'buy_volume': data.get('buy_lg_vol', 0),
                'sell_volume': data.get('sell_lg_vol', 0),
                'net_volume': data.get('buy_lg_vol', 0) - data.get('sell_lg_vol', 0)
            },
            'extra_large_order': {  # 特大单：成交额>=100万
                'buy_amount': data.get('buy_elg_amount', 0),
                'sell_amount': data.get('sell_elg_amount', 0),
                'net_amount': data.get('buy_elg_amount', 0) - data.get('sell_elg_amount', 0),
                'buy_volume': data.get('buy_elg_vol', 0),
                'sell_volume': data.get('sell_elg_vol', 0),
                'net_volume': data.get('buy_elg_vol', 0) - data.get('sell_elg_vol', 0)
            }
        }
    
    def _validate_stock_code(self, ts_code: str) -> bool:
        """
        验证股票代码格式
        
        Args:
            ts_code: 股票代码
            
        Returns:
            bool: 是否有效
        """
        if not ts_code or '.' not in ts_code:
            return False
        
        code, market = ts_code.split('.')
        if len(code) != 6 or market not in ['SH', 'SZ', 'BJ']:
            return False
        
        return True
    
    def _get_latest_trading_day(self) -> str:
        """
        获取最近有数据的交易日
        
        Returns:
            str: 交易日期 YYYYMMDD
        """
        try:
            # 使用tushare获取交易日历
            today = datetime.now()
            
            # 先尝试使用tushare获取交易日历
            try:
                # 获取最近30天的交易日历
                start_date = (today - timedelta(days=30)).strftime('%Y%m%d')
                end_date = today.strftime('%Y%m%d')
                
                cal_df = self.pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
                
                if not cal_df.empty:
                    # 筛选出交易日，按日期倒序排列
                    trading_days = cal_df[cal_df['is_open'] == 1]['cal_date'].tolist()
                    trading_days.sort(reverse=True)  # 从最新日期开始
                    
                    # 验证每个交易日是否有数据（使用一个常见股票作为测试）
                    test_stock = '000001.SZ'  # 使用平安银行作为测试股票
                    for trading_day in trading_days:
                        try:
                            # 快速检查该日期是否有资金流向数据
                            df = self.pro.moneyflow(ts_code=test_stock, trade_date=trading_day)
                            if not df.empty:
                                logger.info(f"通过交易日历和数据验证获取到最新交易日: {trading_day}")
                                return trading_day
                        except Exception:
                            continue
                        
            except Exception as e:
                logger.warning(f"使用tushare获取交易日历失败: {e}")
            
            # 如果tushare失败，使用简单逻辑并验证数据
            test_stock = '000001.SZ'
            for i in range(10):  # 最多往前查10天
                check_date = today - timedelta(days=i)
                date_str = check_date.strftime('%Y%m%d')
                
                # 简单判断：周一到周五且不是节假日
                if check_date.weekday() < 5:  # 0-4表示周一到周五
                    try:
                        # 验证该日期是否有数据
                        df = self.pro.moneyflow(ts_code=test_stock, trade_date=date_str)
                        if not df.empty:
                            logger.info(f"使用简单逻辑和数据验证获取到交易日: {date_str}")
                            return date_str
                    except Exception:
                        continue
            
            # 如果都没有数据，返回昨天
            yesterday = (today - timedelta(days=1)).strftime('%Y%m%d')
            logger.warning(f"未找到有数据的交易日，返回昨天: {yesterday}")
            return yesterday
            
        except Exception as e:
            logger.error(f"获取最近交易日失败: {e}")
            return (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')


# 使用示例
if __name__ == "__main__":
    # 示例用法
    token = "your_tushare_token"  # 替换为实际的token
    handler = MoneyflowHandler(token)
    
    # 获取单只股票的资金流向数据
    result = handler.get_moneyflow_data('000001.SZ', trade_date='20231201')
    
    if result['success']:
        data = result['data'][0] if result['data'] else {}
        
        # 格式化显示
        print(f"股票代码: {data.get('ts_code')}")
        print(f"交易日期: {data.get('trade_date')}")
        print(f"净流入额: {handler.format_moneyflow_amount(data.get('net_mf_amount', 0))}")
        print(f"净流入量: {handler.format_moneyflow_volume(data.get('net_mf_vol', 0))}")
        
        # 获取各类别汇总
        categories = handler.get_moneyflow_categories(data)
        for category, info in categories.items():
            print(f"{category}: 净流入 {handler.format_moneyflow_amount(info['net_amount'])}")
    else:
        print(f"获取失败: {result['error']}")