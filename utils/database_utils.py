"""
数据库连接池管理工具
提供高效的数据库连接管理和查询优化
"""

import sqlite3
import threading
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager
from queue import Queue, Empty
import time
import logging
from dataclasses import dataclass

@dataclass
class ConnectionConfig:
    """连接配置"""
    database_path: str
    max_connections: int = 10
    timeout: float = 30.0
    check_same_thread: bool = False
    isolation_level: Optional[str] = None

class DatabaseConnectionPool:
    """数据库连接池"""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.pool = Queue(maxsize=config.max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # 预创建连接
        self._initialize_pool()
    
    def _initialize_pool(self):
        """初始化连接池"""
        for _ in range(self.config.max_connections):
            conn = self._create_connection()
            if conn:
                self.pool.put(conn)
    
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """创建新连接"""
        try:
            conn = sqlite3.connect(
                self.config.database_path,
                timeout=self.config.timeout,
                check_same_thread=self.config.check_same_thread,
                isolation_level=self.config.isolation_level
            )
            
            # 设置连接参数
            conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            conn.execute("PRAGMA journal_mode=WAL")  # 启用WAL模式
            conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全性
            conn.execute("PRAGMA cache_size=10000")  # 增加缓存大小
            conn.execute("PRAGMA temp_store=MEMORY")  # 临时表存储在内存中
            
            with self.lock:
                self.active_connections += 1
            
            return conn
            
        except Exception as e:
            self.logger.error(f"创建数据库连接失败: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """获取连接（上下文管理器）"""
        conn = None
        try:
            # 尝试从池中获取连接
            try:
                conn = self.pool.get(timeout=5.0)
            except Empty:
                # 池中没有可用连接，创建新连接
                conn = self._create_connection()
                if not conn:
                    raise Exception("无法创建数据库连接")
            
            yield conn
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                try:
                    # 将连接放回池中
                    self.pool.put_nowait(conn)
                except:
                    # 池已满，关闭连接
                    conn.close()
                    with self.lock:
                        self.active_connections -= 1
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """执行查询"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """执行更新操作"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """批量执行操作"""
        with self.get_connection() as conn:
            cursor = conn.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
    
    def close_all(self):
        """关闭所有连接"""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except Empty:
                break
        
        with self.lock:
            self.active_connections = 0

class QueryBuilder:
    """SQL查询构建器"""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.reset()
    
    def reset(self):
        """重置查询构建器"""
        self._select_fields = []
        self._where_conditions = []
        self._order_by = []
        self._limit_value = None
        self._offset_value = None
        self._params = []
        return self
    
    def select(self, *fields: str):
        """选择字段"""
        self._select_fields.extend(fields)
        return self
    
    def where(self, condition: str, *params):
        """添加WHERE条件"""
        self._where_conditions.append(condition)
        self._params.extend(params)
        return self
    
    def order_by(self, field: str, direction: str = "ASC"):
        """添加排序"""
        self._order_by.append(f"{field} {direction}")
        return self
    
    def limit(self, count: int):
        """设置限制数量"""
        self._limit_value = count
        return self
    
    def offset(self, count: int):
        """设置偏移量"""
        self._offset_value = count
        return self
    
    def build(self) -> tuple:
        """构建查询语句"""
        # SELECT部分
        if self._select_fields:
            select_clause = f"SELECT {', '.join(self._select_fields)}"
        else:
            select_clause = "SELECT *"
        
        # FROM部分
        query = f"{select_clause} FROM {self.table_name}"
        
        # WHERE部分
        if self._where_conditions:
            query += f" WHERE {' AND '.join(self._where_conditions)}"
        
        # ORDER BY部分
        if self._order_by:
            query += f" ORDER BY {', '.join(self._order_by)}"
        
        # LIMIT部分
        if self._limit_value is not None:
            query += f" LIMIT {self._limit_value}"
        
        # OFFSET部分
        if self._offset_value is not None:
            query += f" OFFSET {self._offset_value}"
        
        return query, tuple(self._params)

# 全局连接池实例
_connection_pool: Optional[DatabaseConnectionPool] = None

def initialize_database_pool(config: ConnectionConfig):
    """初始化数据库连接池"""
    global _connection_pool
    _connection_pool = DatabaseConnectionPool(config)

def get_database_pool() -> DatabaseConnectionPool:
    """获取数据库连接池"""
    if _connection_pool is None:
        raise Exception("数据库连接池未初始化，请先调用 initialize_database_pool()")
    return _connection_pool

def query_decorator(func: Callable) -> Callable:
    """数据库查询装饰器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # 记录慢查询
            if duration > 1.0:  # 超过1秒的查询
                logging.warning(f"慢查询检测: {func.__name__} 耗时 {duration:.2f}秒")
            
            return result
        except Exception as e:
            logging.error(f"数据库查询错误 {func.__name__}: {e}")
            raise
    
    return wrapper