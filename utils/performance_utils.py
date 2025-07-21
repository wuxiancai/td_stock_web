"""
性能监控和缓存优化工具
提供API调用监控、缓存管理和性能分析功能
"""

import time
import functools
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
import os

@dataclass
class PerformanceMetrics:
    """性能指标"""
    api_name: str
    call_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0
    success_rate: float = 100.0
    last_call_time: Optional[datetime] = None
    recent_calls: deque = field(default_factory=lambda: deque(maxlen=100))

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.lock = threading.Lock()
        self.start_time = datetime.now()
    
    def record_api_call(self, api_name: str, duration: float, success: bool = True):
        """记录API调用"""
        with self.lock:
            if api_name not in self.metrics:
                self.metrics[api_name] = PerformanceMetrics(api_name=api_name)
            
            metric = self.metrics[api_name]
            metric.call_count += 1
            metric.total_time += duration
            metric.avg_time = metric.total_time / metric.call_count
            metric.min_time = min(metric.min_time, duration)
            metric.max_time = max(metric.max_time, duration)
            metric.last_call_time = datetime.now()
            
            if not success:
                metric.error_count += 1
            
            metric.success_rate = ((metric.call_count - metric.error_count) / metric.call_count) * 100
            
            # 记录最近的调用
            metric.recent_calls.append({
                'timestamp': datetime.now().isoformat(),
                'duration': duration,
                'success': success
            })
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取性能指标摘要"""
        with self.lock:
            summary = {
                'monitor_start_time': self.start_time.isoformat(),
                'total_apis': len(self.metrics),
                'apis': {}
            }
            
            for api_name, metric in self.metrics.items():
                summary['apis'][api_name] = {
                    'call_count': metric.call_count,
                    'avg_time': round(metric.avg_time, 3),
                    'min_time': round(metric.min_time, 3),
                    'max_time': round(metric.max_time, 3),
                    'error_count': metric.error_count,
                    'success_rate': round(metric.success_rate, 2),
                    'last_call': metric.last_call_time.isoformat() if metric.last_call_time else None
                }
            
            return summary
    
    def get_slow_apis(self, threshold: float = 2.0) -> List[Dict[str, Any]]:
        """获取慢API列表"""
        slow_apis = []
        
        with self.lock:
            for api_name, metric in self.metrics.items():
                if metric.avg_time > threshold:
                    slow_apis.append({
                        'api_name': api_name,
                        'avg_time': round(metric.avg_time, 3),
                        'call_count': metric.call_count,
                        'max_time': round(metric.max_time, 3)
                    })
        
        return sorted(slow_apis, key=lambda x: x['avg_time'], reverse=True)

def performance_monitor(api_name: str):
    """性能监控装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                # 这里需要一个全局的监控器实例
                if hasattr(wrapper, '_monitor'):
                    wrapper._monitor.record_api_call(api_name, duration, success)
        
        return wrapper
    return decorator

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache", default_ttl: int = 3600):
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_file_path(self, key: str) -> str:
        """获取缓存文件路径"""
        safe_key = key.replace('/', '_').replace('\\', '_').replace(':', '_')
        return os.path.join(self.cache_dir, f"{safe_key}.json")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        ttl = ttl or self.default_ttl
        expire_time = datetime.now() + timedelta(seconds=ttl)
        
        cache_data = {
            'value': value,
            'expire_time': expire_time.isoformat(),
            'created_time': datetime.now().isoformat()
        }
        
        with self.lock:
            # 内存缓存
            self.memory_cache[key] = cache_data
            
            # 文件缓存
            try:
                cache_file = self._get_cache_file_path(key)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"警告: 无法写入缓存文件 {key}: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self.lock:
            # 先检查内存缓存
            if key in self.memory_cache:
                cache_data = self.memory_cache[key]
                expire_time = datetime.fromisoformat(cache_data['expire_time'])
                
                if datetime.now() < expire_time:
                    return cache_data['value']
                else:
                    # 过期，删除内存缓存
                    del self.memory_cache[key]
            
            # 检查文件缓存
            cache_file = self._get_cache_file_path(key)
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    expire_time = datetime.fromisoformat(cache_data['expire_time'])
                    
                    if datetime.now() < expire_time:
                        # 重新加载到内存缓存
                        self.memory_cache[key] = cache_data
                        return cache_data['value']
                    else:
                        # 过期，删除文件
                        os.remove(cache_file)
                except Exception as e:
                    print(f"警告: 无法读取缓存文件 {key}: {e}")
        
        return None
    
    def delete(self, key: str) -> None:
        """删除缓存"""
        with self.lock:
            # 删除内存缓存
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            # 删除文件缓存
            cache_file = self._get_cache_file_path(key)
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                except Exception as e:
                    print(f"警告: 无法删除缓存文件 {key}: {e}")
    
    def clear_expired(self) -> int:
        """清理过期缓存"""
        cleared_count = 0
        current_time = datetime.now()
        
        with self.lock:
            # 清理内存缓存
            expired_keys = []
            for key, cache_data in self.memory_cache.items():
                expire_time = datetime.fromisoformat(cache_data['expire_time'])
                if current_time >= expire_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.memory_cache[key]
                cleared_count += 1
            
            # 清理文件缓存
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    cache_file = os.path.join(self.cache_dir, filename)
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        expire_time = datetime.fromisoformat(cache_data['expire_time'])
                        if current_time >= expire_time:
                            os.remove(cache_file)
                            cleared_count += 1
                    except Exception:
                        # 如果文件损坏，也删除它
                        try:
                            os.remove(cache_file)
                            cleared_count += 1
                        except Exception:
                            pass
        
        return cleared_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            memory_count = len(self.memory_cache)
            file_count = len([f for f in os.listdir(self.cache_dir) if f.endswith('.json')])
            
            total_size = 0
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except Exception:
                        pass
            
            return {
                'memory_cache_count': memory_count,
                'file_cache_count': file_count,
                'total_cache_size_bytes': total_size,
                'total_cache_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_directory': self.cache_dir
            }

def cached(ttl: int = 3600, cache_manager: Optional[CacheManager] = None):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}_{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # 使用提供的缓存管理器或默认的
            cm = cache_manager or getattr(wrapper, '_cache_manager', None)
            if not cm:
                cm = CacheManager()
                wrapper._cache_manager = cm
            
            # 尝试从缓存获取
            cached_result = cm.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cm.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

class RateLimiter:
    """增强的频率限制器"""
    
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = deque()
        self.lock = threading.Lock()
    
    def can_call(self) -> bool:
        """检查是否可以调用"""
        with self.lock:
            now = time.time()
            
            # 移除一分钟前的调用记录
            while self.calls and self.calls[0] < now - 60:
                self.calls.popleft()
            
            return len(self.calls) < self.calls_per_minute
    
    def record_call(self) -> None:
        """记录调用"""
        with self.lock:
            self.calls.append(time.time())
    
    def wait_time(self) -> float:
        """获取需要等待的时间"""
        with self.lock:
            if len(self.calls) < self.calls_per_minute:
                return 0.0
            
            # 计算最早的调用何时过期
            oldest_call = self.calls[0]
            return max(0, 60 - (time.time() - oldest_call))

# 全局实例
global_performance_monitor = PerformanceMonitor()
global_cache_manager = CacheManager()

# 便捷函数
def get_performance_summary() -> Dict[str, Any]:
    """获取性能摘要"""
    return global_performance_monitor.get_metrics_summary()

def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计"""
    return global_cache_manager.get_cache_stats()

def clear_expired_cache() -> int:
    """清理过期缓存"""
    return global_cache_manager.clear_expired()