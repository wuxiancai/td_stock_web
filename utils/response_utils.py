"""
API响应标准化工具
提供统一的API响应格式和错误处理
"""

from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime

class ResponseCode(Enum):
    """响应状态码"""
    SUCCESS = 200
    BAD_REQUEST = 400
    NOT_FOUND = 404
    INTERNAL_ERROR = 500
    RATE_LIMITED = 429
    DATA_INVALID = 422

@dataclass
class ApiResponse:
    """标准API响应格式"""
    success: bool
    code: int
    message: str
    data: Optional[Any] = None
    timestamp: str = None
    request_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'success': self.success,
            'code': self.code,
            'message': self.message,
            'timestamp': self.timestamp
        }
        
        if self.data is not None:
            result['data'] = self.data
            
        if self.request_id:
            result['request_id'] = self.request_id
            
        return result
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

class ResponseBuilder:
    """响应构建器"""
    
    @staticmethod
    def success(data: Any = None, message: str = "操作成功", request_id: str = None) -> ApiResponse:
        """构建成功响应"""
        return ApiResponse(
            success=True,
            code=ResponseCode.SUCCESS.value,
            message=message,
            data=data,
            request_id=request_id
        )
    
    @staticmethod
    def error(code: ResponseCode, message: str, data: Any = None, request_id: str = None) -> ApiResponse:
        """构建错误响应"""
        return ApiResponse(
            success=False,
            code=code.value,
            message=message,
            data=data,
            request_id=request_id
        )
    
    @staticmethod
    def bad_request(message: str = "请求参数错误", data: Any = None) -> ApiResponse:
        """构建400错误响应"""
        return ResponseBuilder.error(ResponseCode.BAD_REQUEST, message, data)
    
    @staticmethod
    def not_found(message: str = "资源未找到", data: Any = None) -> ApiResponse:
        """构建404错误响应"""
        return ResponseBuilder.error(ResponseCode.NOT_FOUND, message, data)
    
    @staticmethod
    def internal_error(message: str = "服务器内部错误", data: Any = None) -> ApiResponse:
        """构建500错误响应"""
        return ResponseBuilder.error(ResponseCode.INTERNAL_ERROR, message, data)
    
    @staticmethod
    def rate_limited(message: str = "请求频率过高", data: Any = None) -> ApiResponse:
        """构建429错误响应"""
        return ResponseBuilder.error(ResponseCode.RATE_LIMITED, message, data)
    
    @staticmethod
    def data_invalid(message: str = "数据验证失败", data: Any = None) -> ApiResponse:
        """构建422错误响应"""
        return ResponseBuilder.error(ResponseCode.DATA_INVALID, message, data)

def api_response_wrapper(func):
    """API响应包装装饰器"""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            
            # 如果返回的已经是ApiResponse，直接返回
            if isinstance(result, ApiResponse):
                return result.to_dict()
            
            # 否则包装为成功响应
            return ResponseBuilder.success(data=result).to_dict()
            
        except ValueError as e:
            return ResponseBuilder.bad_request(str(e)).to_dict()
        except FileNotFoundError as e:
            return ResponseBuilder.not_found(str(e)).to_dict()
        except Exception as e:
            return ResponseBuilder.internal_error(f"处理请求时发生错误: {str(e)}").to_dict()
    
    return wrapper

class DataFormatter:
    """数据格式化工具"""
    
    @staticmethod
    def format_stock_data(stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化股票数据"""
        formatted = stock_data.copy()
        
        # 格式化价格字段（保留2位小数）
        price_fields = ['open', 'close', 'high', 'low', 'current_price']
        for field in price_fields:
            if field in formatted and formatted[field] is not None:
                formatted[field] = round(float(formatted[field]), 2)
        
        # 格式化百分比字段
        percentage_fields = ['pct_chg', 'change_rate']
        for field in percentage_fields:
            if field in formatted and formatted[field] is not None:
                formatted[field] = round(float(formatted[field]), 2)
        
        # 格式化成交量（转换为万手）
        if 'volume' in formatted and formatted['volume'] is not None:
            formatted['volume_wan'] = round(float(formatted['volume']) / 10000, 2)
        
        # 格式化成交额（转换为万元）
        if 'amount' in formatted and formatted['amount'] is not None:
            formatted['amount_wan'] = round(float(formatted['amount']) / 10000, 2)
        
        return formatted
    
    @staticmethod
    def format_kline_data(kline_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化K线数据"""
        return [DataFormatter.format_stock_data(item) for item in kline_data]