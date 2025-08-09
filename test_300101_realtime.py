#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试300101股票的实时交易数据
查看返回的具体数据内容
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_sina_realtime_data, get_enhanced_stock_info, get_sina_batch_realtime_data
from datetime import datetime
import json

def test_300101_sina_realtime():
    """测试300101的新浪实时数据"""
    print("=" * 60)
    print("测试300101股票 - 新浪财经实时数据")
    print("=" * 60)
    
    stock_code = "300101"
    
    try:
        # 获取新浪实时数据
        sina_data = get_sina_realtime_data(stock_code)
        
        if sina_data:
            print("✅ 新浪财经API成功获取300101实时数据:")
            print("-" * 40)
            for key, value in sina_data.items():
                print(f"{key}: {value}")
            print("-" * 40)
            return sina_data
        else:
            print("❌ 新浪财经API未获取到300101数据")
            return None
            
    except Exception as e:
        print(f"❌ 新浪财经API测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_300101_enhanced_info():
    """测试300101的增强信息"""
    print("\n" + "=" * 60)
    print("测试300101股票 - 增强信息（市值、PE等）")
    print("=" * 60)
    
    stock_code = "300101"
    
    try:
        # 获取增强信息
        enhanced_info = get_enhanced_stock_info(stock_code)
        
        if enhanced_info:
            print("✅ 成功获取300101增强信息:")
            print("-" * 40)
            for key, value in enhanced_info.items():
                if isinstance(value, float):
                    print(f"{key}: {value:.4f}")
                else:
                    print(f"{key}: {value}")
            print("-" * 40)
            return enhanced_info
        else:
            print("❌ 未获取到300101增强信息")
            return None
            
    except Exception as e:
        print(f"❌ 增强信息获取失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_batch_realtime_with_300101():
    """测试批量实时数据中是否包含300101"""
    print("\n" + "=" * 60)
    print("测试批量实时数据 - 查找300101")
    print("=" * 60)
    
    try:
        # 获取批量实时数据
        batch_data = get_sina_batch_realtime_data()
        
        if batch_data is not None and not batch_data.empty:
            print(f"✅ 批量数据获取成功，共{len(batch_data)}只股票")
            
            # 查找300101
            stock_300101 = batch_data[batch_data['代码'] == '300101']
            
            if not stock_300101.empty:
                print("\n✅ 在批量数据中找到300101:")
                print("-" * 40)
                row = stock_300101.iloc[0]
                for col in batch_data.columns:
                    value = row[col]
                    if isinstance(value, float):
                        print(f"{col}: {value:.4f}")
                    else:
                        print(f"{col}: {value}")
                print("-" * 40)
                return row.to_dict()
            else:
                print("❌ 批量数据中未找到300101")
                print("\n当前批量数据包含的股票:")
                for idx, row in batch_data.iterrows():
                    print(f"  {row['代码']} - {row['名称']}")
                return None
        else:
            print("❌ 批量数据获取失败")
            return None
            
    except Exception as e:
        print(f"❌ 批量数据测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_combined_300101_data():
    """创建300101的完整实时数据（组合新浪+增强信息）"""
    print("\n" + "=" * 60)
    print("创建300101完整实时数据")
    print("=" * 60)
    
    # 获取新浪实时数据
    sina_data = test_300101_sina_realtime()
    
    # 获取增强信息
    enhanced_info = test_300101_enhanced_info()
    
    if sina_data:
        # 组合数据
        combined_data = {
            '代码': '300101',
            '名称': sina_data.get('name', ''),
            '最新价': sina_data.get('latest_price', 0.0),
            '涨跌幅': sina_data.get('change_percent', 0.0),
            '涨跌额': sina_data.get('change_amount', 0.0),
            '成交量': sina_data.get('volume', 0.0),
            '成交额': sina_data.get('amount', 0.0),
            '最高': sina_data.get('high', 0.0),
            '最低': sina_data.get('low', 0.0),
            '今开': sina_data.get('open', 0.0),
            '昨收': sina_data.get('pre_close', 0.0),
            '振幅': 0.0,  # 需要计算
            '量比': 0.0,  # 新浪API不提供
            '换手率': enhanced_info.get('换手率', 0.0) if enhanced_info else 0.0,
            '市盈率-动态': enhanced_info.get('市盈率-动态', 0.0) if enhanced_info else 0.0,
            '市净率': enhanced_info.get('市净率', 0.0) if enhanced_info else 0.0,
            '总市值': enhanced_info.get('总市值', 0.0) if enhanced_info else 0.0,
            '流通市值': enhanced_info.get('流通市值', 0.0) if enhanced_info else 0.0,
            '数据来源': 'sina+akshare_enhanced',
            '更新时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 计算振幅
        if sina_data.get('pre_close', 0) > 0:
            high = sina_data.get('high', 0)
            low = sina_data.get('low', 0)
            pre_close = sina_data.get('pre_close', 0)
            combined_data['振幅'] = ((high - low) / pre_close) * 100 if high > low else 0.0
        
        print("\n✅ 300101完整实时数据:")
        print("=" * 60)
        for key, value in combined_data.items():
            if isinstance(value, float) and key not in ['代码']:
                print(f"{key}: {value:.4f}")
            else:
                print(f"{key}: {value}")
        print("=" * 60)
        
        return combined_data
    else:
        print("❌ 无法创建完整数据，新浪API获取失败")
        return None

def main():
    """主测试函数"""
    print("300101股票实时交易数据测试")
    print("测试时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 80)
    
    # 测试各个数据源
    sina_result = test_300101_sina_realtime()
    enhanced_result = test_300101_enhanced_info()
    batch_result = test_batch_realtime_with_300101()
    combined_result = create_combined_300101_data()
    
    print("\n" + "=" * 80)
    print("测试结果总结:")
    print("=" * 80)
    print(f"新浪实时数据: {'✅ 成功' if sina_result else '❌ 失败'}")
    print(f"增强信息数据: {'✅ 成功' if enhanced_result else '❌ 失败'}")
    print(f"批量数据查找: {'✅ 找到' if batch_result else '❌ 未找到'}")
    print(f"完整数据组合: {'✅ 成功' if combined_result else '❌ 失败'}")
    
    if combined_result:
        print("\n推荐使用完整数据组合方案，包含所有必要字段。")
    else:
        print("\n建议检查网络连接或API可用性。")

if __name__ == "__main__":
    main()