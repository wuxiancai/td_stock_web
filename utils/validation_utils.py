"""
数据验证和错误处理工具
提供股票数据的全面验证和错误处理机制
"""

from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

class ValidationLevel(Enum):
    """验证级别"""
    BASIC = "basic"      # 基础验证
    STANDARD = "standard"  # 标准验证
    STRICT = "strict"    # 严格验证

@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    data_quality_score: float  # 0-100分

class StockDataValidator:
    """股票数据验证器"""
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        self.validation_level = validation_level
        self.price_columns = ['open', 'close', 'high', 'low']
        self.required_columns = ['trade_date'] + self.price_columns
    
    def validate_kline_data(self, data: pd.DataFrame) -> ValidationResult:
        """验证K线数据"""
        errors = []
        warnings = []
        quality_score = 100.0
        
        # 基础验证
        basic_result = self._basic_validation(data)
        errors.extend(basic_result['errors'])
        warnings.extend(basic_result['warnings'])
        quality_score -= basic_result['penalty']
        
        # 标准验证
        if self.validation_level in [ValidationLevel.STANDARD, ValidationLevel.STRICT]:
            standard_result = self._standard_validation(data)
            errors.extend(standard_result['errors'])
            warnings.extend(standard_result['warnings'])
            quality_score -= standard_result['penalty']
        
        # 严格验证
        if self.validation_level == ValidationLevel.STRICT:
            strict_result = self._strict_validation(data)
            errors.extend(strict_result['errors'])
            warnings.extend(strict_result['warnings'])
            quality_score -= strict_result['penalty']
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data_quality_score=max(0, quality_score)
        )
    
    def _basic_validation(self, data: pd.DataFrame) -> Dict[str, Any]:
        """基础验证"""
        errors = []
        warnings = []
        penalty = 0
        
        # 检查数据是否为空
        if data.empty:
            errors.append("数据为空")
            penalty += 100
            return {'errors': errors, 'warnings': warnings, 'penalty': penalty}
        
        # 检查必需列
        missing_columns = [col for col in self.required_columns if col not in data.columns]
        if missing_columns:
            errors.append(f"缺少必需列: {missing_columns}")
            penalty += 50
        
        # 检查数据类型
        for col in self.price_columns:
            if col in data.columns:
                if not pd.api.types.is_numeric_dtype(data[col]):
                    errors.append(f"列 {col} 不是数值类型")
                    penalty += 10
        
        # 检查空值
        null_counts = data[self.price_columns].isnull().sum()
        for col, null_count in null_counts.items():
            if null_count > 0:
                warnings.append(f"列 {col} 有 {null_count} 个空值")
                penalty += null_count * 0.5
        
        return {'errors': errors, 'warnings': warnings, 'penalty': penalty}
    
    def _standard_validation(self, data: pd.DataFrame) -> Dict[str, Any]:
        """标准验证"""
        errors = []
        warnings = []
        penalty = 0
        
        # 价格逻辑验证
        for idx, row in data.iterrows():
            try:
                high = float(row['high'])
                low = float(row['low'])
                open_price = float(row['open'])
                close = float(row['close'])
                
                # 检查价格关系
                if high < max(open_price, close, low):
                    errors.append(f"第{idx}行: 最高价 {high} 小于其他价格")
                    penalty += 5
                
                if low > min(open_price, close, high):
                    errors.append(f"第{idx}行: 最低价 {low} 大于其他价格")
                    penalty += 5
                
                # 检查异常价格
                if any(price <= 0 for price in [high, low, open_price, close]):
                    errors.append(f"第{idx}行: 存在非正数价格")
                    penalty += 10
                
                # 检查价格波动异常
                price_range = high - low
                avg_price = (high + low) / 2
                if avg_price > 0 and price_range / avg_price > 0.2:  # 单日波动超过20%
                    warnings.append(f"第{idx}行: 价格波动异常大 ({price_range/avg_price:.1%})")
                    penalty += 1
                    
            except (ValueError, TypeError) as e:
                errors.append(f"第{idx}行: 价格数据格式错误 - {str(e)}")
                penalty += 5
        
        return {'errors': errors, 'warnings': warnings, 'penalty': penalty}
    
    def _strict_validation(self, data: pd.DataFrame) -> Dict[str, Any]:
        """严格验证"""
        errors = []
        warnings = []
        penalty = 0
        
        # 时间序列连续性检查
        if 'trade_date' in data.columns:
            dates = pd.to_datetime(data['trade_date'])
            date_gaps = dates.diff().dt.days
            
            # 检查是否有异常的日期间隔
            large_gaps = date_gaps[date_gaps > 7]  # 超过7天的间隔
            if len(large_gaps) > 0:
                warnings.append(f"发现 {len(large_gaps)} 个大于7天的日期间隔")
                penalty += len(large_gaps) * 2
        
        # 成交量验证（如果存在）
        if 'volume' in data.columns or 'vol' in data.columns:
            vol_col = 'volume' if 'volume' in data.columns else 'vol'
            zero_volume_count = (data[vol_col] == 0).sum()
            if zero_volume_count > 0:
                warnings.append(f"发现 {zero_volume_count} 个零成交量交易日")
                penalty += zero_volume_count * 0.5
        
        # 价格精度检查
        for col in self.price_columns:
            if col in data.columns:
                # 检查是否有过多的小数位
                decimal_places = data[col].astype(str).str.split('.').str[1].str.len()
                excessive_precision = (decimal_places > 4).sum()
                if excessive_precision > 0:
                    warnings.append(f"列 {col} 有 {excessive_precision} 个过高精度的值")
                    penalty += excessive_precision * 0.1
        
        return {'errors': errors, 'warnings': warnings, 'penalty': penalty}

class DataSanitizer:
    """数据清理器"""
    
    @staticmethod
    def clean_price_data(data: pd.DataFrame) -> pd.DataFrame:
        """清理价格数据"""
        cleaned_data = data.copy()
        
        price_columns = ['open', 'close', 'high', 'low']
        
        for col in price_columns:
            if col in cleaned_data.columns:
                # 移除非正数
                cleaned_data = cleaned_data[cleaned_data[col] > 0]
                
                # 处理异常值（使用IQR方法）
                Q1 = cleaned_data[col].quantile(0.25)
                Q3 = cleaned_data[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                # 标记异常值但不删除，而是记录警告
                outliers = cleaned_data[
                    (cleaned_data[col] < lower_bound) | 
                    (cleaned_data[col] > upper_bound)
                ]
                
                if len(outliers) > 0:
                    print(f"警告: 列 {col} 发现 {len(outliers)} 个可能的异常值")
        
        return cleaned_data
    
    @staticmethod
    def fill_missing_values(data: pd.DataFrame, method: str = 'forward') -> pd.DataFrame:
        """填充缺失值"""
        filled_data = data.copy()
        
        price_columns = ['open', 'close', 'high', 'low']
        
        for col in price_columns:
            if col in filled_data.columns:
                if method == 'forward':
                    filled_data[col] = filled_data[col].fillna(method='ffill')
                elif method == 'backward':
                    filled_data[col] = filled_data[col].fillna(method='bfill')
                elif method == 'interpolate':
                    filled_data[col] = filled_data[col].interpolate()
                elif method == 'mean':
                    filled_data[col] = filled_data[col].fillna(filled_data[col].mean())
        
        return filled_data

class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def handle_api_error(error: Exception, api_name: str, retry_count: int = 0) -> Dict[str, Any]:
        """处理API错误"""
        error_info = {
            'api_name': api_name,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'retry_count': retry_count,
            'timestamp': datetime.now().isoformat(),
            'should_retry': False,
            'wait_time': 0
        }
        
        error_msg = str(error).lower()
        
        # 频率限制错误
        if any(keyword in error_msg for keyword in ['rate', 'limit', 'frequency', '频率']):
            error_info['should_retry'] = True
            error_info['wait_time'] = min(60 * (2 ** retry_count), 300)  # 指数退避，最大5分钟
        
        # 网络错误
        elif any(keyword in error_msg for keyword in ['network', 'connection', 'timeout', '网络']):
            error_info['should_retry'] = True
            error_info['wait_time'] = min(10 * (retry_count + 1), 60)  # 线性增加，最大1分钟
        
        # 数据不存在错误
        elif any(keyword in error_msg for keyword in ['not found', 'no data', '无数据']):
            error_info['should_retry'] = False
            error_info['wait_time'] = 0
        
        return error_info

# 便捷函数
def validate_stock_data(data: pd.DataFrame, 
                       level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
    """验证股票数据的便捷函数"""
    validator = StockDataValidator(level)
    return validator.validate_kline_data(data)

def clean_and_validate_data(data: pd.DataFrame) -> Tuple[pd.DataFrame, ValidationResult]:
    """清理并验证数据"""
    # 先清理
    sanitizer = DataSanitizer()
    cleaned_data = sanitizer.clean_price_data(data)
    cleaned_data = sanitizer.fill_missing_values(cleaned_data)
    
    # 再验证
    validation_result = validate_stock_data(cleaned_data)
    
    return cleaned_data, validation_result