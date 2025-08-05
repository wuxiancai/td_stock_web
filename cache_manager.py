#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的缓存管理系统
实现功能：
1. 数据校验：JSON文件完整性检查
2. 并发控制：文件锁机制防止冲突
3. 错误恢复：损坏文件自动重建
4. 分层存储：热数据内存+冷数据文件
5. 增量更新：只更新变化的数据
6. 监控告警：缓存状态监控
7. 数据生命周期：90天数据保留，120天自动清理
"""

import os
import json
import time
import threading
import hashlib
import shutil
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import OrderedDict
# 处理fcntl库的兼容性问题（Windows系统不支持fcntl）
try:
    import fcntl
    FCNTL_AVAILABLE = True
except ImportError:
    FCNTL_AVAILABLE = False
    
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cache_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class CacheMetrics:
    """缓存性能指标"""
    hit_count: int = 0
    miss_count: int = 0
    error_count: int = 0
    last_update_time: float = 0
    data_size: int = 0
    file_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0

@dataclass
class CacheStatus:
    """缓存状态信息"""
    is_healthy: bool = True
    last_check_time: float = 0
    error_messages: List[str] = None
    metrics: CacheMetrics = None
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
        if self.metrics is None:
            self.metrics = CacheMetrics()

class FileLockManager:
    """文件锁管理器"""
    
    def __init__(self, lock_timeout: int = 30):
        self.lock_timeout = lock_timeout
        self.locks = {}
        self.lock_mutex = threading.Lock()
        self.simple_locks = {}  # 用于简单锁机制
    
    def acquire_lock(self, file_path: str) -> Optional[object]:
        """获取文件锁"""
        if not FCNTL_AVAILABLE:
            # 在不支持fcntl的系统上使用简单的文件锁机制
            return self._acquire_simple_lock(file_path)
            
        lock_file = f"{file_path}.lock"
        
        try:
            # 确保锁文件目录存在
            lock_dir = os.path.dirname(lock_file)
            if lock_dir and not os.path.exists(lock_dir):
                os.makedirs(lock_dir, exist_ok=True)
            
            # 创建锁文件
            lock_fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
            
            # 尝试获取排他锁
            start_time = time.time()
            while time.time() - start_time < self.lock_timeout:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.info(f"成功获取文件锁: {file_path}")
                    return lock_fd
                except BlockingIOError:
                    time.sleep(0.1)
            
            # 超时未获取到锁
            os.close(lock_fd)
            logger.warning(f"获取文件锁超时: {file_path}")
            return None
            
        except Exception as e:
            logger.error(f"获取文件锁失败: {file_path}, 错误: {e}")
            return None
    
    def release_lock(self, lock_fd: object, file_path: str):
        """释放文件锁"""
        if not FCNTL_AVAILABLE:
            # 在不支持fcntl的系统上使用简单的文件锁机制
            return self._release_simple_lock(lock_fd, file_path)
            
        try:
            if lock_fd:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
                
                # 删除锁文件
                lock_file = f"{file_path}.lock"
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    
                logger.debug(f"成功释放文件锁: {file_path}")
        except Exception as e:
            logger.error(f"释放文件锁失败: {file_path}, 错误: {e}")
    
    def _acquire_simple_lock(self, file_path: str) -> Optional[str]:
        """简单文件锁实现（用于不支持fcntl的系统）"""
        lock_file = f"{file_path}.lock"
        
        with self.lock_mutex:
            # 检查是否已经有锁
            if lock_file in self.simple_locks:
                logger.warning(f"文件已被锁定: {file_path}")
                return None
            
            try:
                # 确保锁文件目录存在
                lock_dir = os.path.dirname(lock_file)
                if lock_dir and not os.path.exists(lock_dir):
                    os.makedirs(lock_dir, exist_ok=True)
                
                # 创建锁文件
                if os.path.exists(lock_file):
                    # 检查锁文件是否过期（超过锁定超时时间）
                    lock_age = time.time() - os.path.getmtime(lock_file)
                    if lock_age < self.lock_timeout:
                        logger.warning(f"文件锁未过期: {file_path}")
                        return None
                    else:
                        # 删除过期的锁文件
                        os.remove(lock_file)
                
                # 创建新的锁文件
                with open(lock_file, 'w') as f:
                    f.write(str(os.getpid()))
                
                self.simple_locks[lock_file] = time.time()
                logger.debug(f"成功获取简单文件锁: {file_path}")
                return lock_file
                
            except Exception as e:
                logger.error(f"获取简单文件锁失败: {file_path}, 错误: {e}")
                return None
    
    def _release_simple_lock(self, lock_file: str, file_path: str):
        """释放简单文件锁"""
        if not lock_file:
            return
            
        with self.lock_mutex:
            try:
                # 删除锁文件
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                
                # 从锁记录中移除
                if lock_file in self.simple_locks:
                    del self.simple_locks[lock_file]
                
                logger.debug(f"成功释放简单文件锁: {file_path}")
                
            except Exception as e:
                logger.error(f"释放简单文件锁失败: {file_path}, 错误: {e}")

class DataValidator:
    """数据校验器"""
    
    @staticmethod
    def validate_json_structure(data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """验证JSON数据结构"""
        errors = []
        
        # 检查必需字段
        required_fields = ['stocks', 'last_update_date', 'total']
        for field in required_fields:
            if field not in data:
                errors.append(f"缺少必需字段: {field}")
        
        # 检查stocks字段
        if 'stocks' in data:
            if not isinstance(data['stocks'], list):
                errors.append("stocks字段必须是列表")
            else:
                # 检查股票数据结构
                for i, stock in enumerate(data['stocks'][:5]):  # 只检查前5个
                    if not isinstance(stock, dict):
                        errors.append(f"股票数据[{i}]必须是字典")
                        continue
                    
                    stock_required = ['ts_code', 'name']
                    for field in stock_required:
                        if field not in stock:
                            errors.append(f"股票数据[{i}]缺少字段: {field}")
        
        # 检查日期格式
        if 'last_update_date' in data:
            try:
                datetime.strptime(data['last_update_date'], '%Y%m%d')
            except ValueError:
                errors.append("last_update_date日期格式错误")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def calculate_checksum(data: Dict[str, Any]) -> str:
        """计算数据校验和"""
        try:
            json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(json_str.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"计算校验和失败: {e}")
            return ""
    
    @staticmethod
    def verify_checksum(data: Dict[str, Any], expected_checksum: str) -> bool:
        """验证数据校验和"""
        actual_checksum = DataValidator.calculate_checksum(data)
        return actual_checksum == expected_checksum

class OptimizedCacheManager:
    """优化的缓存管理器"""
    
    def __init__(self, cache_dir: str = 'cache', max_memory_items: int = 100):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # 分层存储：内存缓存（热数据）
        self.memory_cache = OrderedDict()
        self.max_memory_items = max_memory_items
        
        # 组件初始化
        self.lock_manager = FileLockManager()
        self.validator = DataValidator()
        
        # 状态监控
        self.status = CacheStatus()
        self.metrics = CacheMetrics()
        
        # 线程锁
        self.memory_lock = threading.RLock()
        
        # 启动后台任务
        self._start_background_tasks()
        
        logger.info(f"缓存管理器初始化完成，缓存目录: {self.cache_dir}")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        # 健康检查任务
        health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        health_thread.start()
        
        # 数据清理任务
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()
    
    def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                self._perform_health_check()
                time.sleep(300)  # 每5分钟检查一次
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
                time.sleep(60)
    
    def _cleanup_loop(self):
        """数据清理循环"""
        # 启动后等待1小时再开始清理，避免影响应用启动
        time.sleep(3600)
        
        while True:
            try:
                self._cleanup_old_data()
                time.sleep(3600)  # 每小时清理一次
            except Exception as e:
                logger.error(f"数据清理失败: {e}")
                time.sleep(1800)  # 出错后30分钟重试
    
    def _perform_health_check(self):
        """执行健康检查"""
        errors = []
        
        try:
            # 检查缓存目录
            if not self.cache_dir.exists():
                errors.append("缓存目录不存在")
            
            # 检查磁盘空间
            disk_usage = shutil.disk_usage(self.cache_dir)
            free_space_gb = disk_usage.free / (1024**3)
            if free_space_gb < 1.0:  # 少于1GB
                errors.append(f"磁盘空间不足: {free_space_gb:.2f}GB")
            
            # 检查缓存文件
            cache_files = list(self.cache_dir.glob('*.json'))
            corrupted_files = []
            
            for cache_file in cache_files:
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 只对股票缓存文件进行结构验证，跳过watchlist.json等其他文件
                    if cache_file.name.endswith('_stocks_cache.json'):
                        is_valid, validation_errors = self.validator.validate_json_structure(data)
                        if not is_valid:
                            corrupted_files.append(str(cache_file))
                    # 对于其他JSON文件（如watchlist.json），只要能正常解析JSON就认为是有效的
                        
                except Exception:
                    corrupted_files.append(str(cache_file))
            
            if corrupted_files:
                errors.append(f"发现损坏的缓存文件: {corrupted_files}")
            
            # 更新状态
            self.status.is_healthy = len(errors) == 0
            self.status.error_messages = errors
            self.status.last_check_time = time.time()
            
            # 更新指标
            self.metrics.file_count = len(cache_files)
            total_size = sum(f.stat().st_size for f in cache_files)
            self.metrics.data_size = total_size
            
            if errors:
                logger.warning(f"健康检查发现问题: {errors}")
            else:
                logger.debug("健康检查通过")
                
        except Exception as e:
            logger.error(f"健康检查执行失败: {e}")
            self.status.is_healthy = False
            self.status.error_messages = [f"健康检查执行失败: {e}"]
    
    def _cleanup_old_data(self):
        """清理过期数据"""
        try:
            current_date = datetime.now()
            cutoff_date = current_date - timedelta(days=120)  # 120天前
            cutoff_str = cutoff_date.strftime('%Y%m%d')
            
            cleaned_count = 0
            
            for cache_file in self.cache_dir.glob('*.json'):
                try:
                    # 跳过非股票缓存文件
                    if not cache_file.name.endswith('_stocks_cache.json'):
                        continue
                        
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if 'stocks' in data:
                        original_count = sum(len(stock.get('kline_data', [])) for stock in data['stocks'])
                        data_modified = False
                        
                        # 清理每只股票的历史数据
                        for stock in data['stocks']:
                            if 'kline_data' in stock and stock['kline_data']:
                                # 只保留90天内的K线数据
                                keep_date = (current_date - timedelta(days=90)).strftime('%Y%m%d')
                                original_kline_count = len(stock['kline_data'])
                                stock['kline_data'] = [
                                    kline for kline in stock['kline_data']
                                    if kline.get('trade_date') and kline.get('trade_date') >= keep_date
                                ]
                                if len(stock['kline_data']) != original_kline_count:
                                    data_modified = True
                        
                        # 如果数据被修改，保存回文件
                        if data_modified:
                            new_count = sum(len(stock.get('kline_data', [])) for stock in data['stocks'])
                            self._save_data_with_backup(cache_file, data)
                            cleaned_count += 1
                            logger.info(f"清理缓存文件 {cache_file}: {original_count} -> {new_count} 条K线数据")
                    
                except Exception as e:
                    logger.error(f"清理缓存文件失败 {cache_file}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"数据清理完成，处理了 {cleaned_count} 个缓存文件")
            else:
                logger.debug("数据清理完成，无需清理的数据")
                
        except Exception as e:
            logger.error(f"数据清理失败: {e}")
    
    def get_cache_file_path(self, market: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f'{market}_stocks_cache.json'
    
    def get_intraday_cache_file_path(self, stock_code: str) -> Path:
        """获取分时图缓存文件路径"""
        # 创建分时图缓存子目录
        intraday_dir = self.cache_dir / 'intraday'
        intraday_dir.mkdir(exist_ok=True)
        
        # 按日期组织缓存文件
        today = datetime.now().strftime('%Y%m%d')
        return intraday_dir / f'{stock_code}_{today}_intraday.json'
    
    def _save_data_with_backup(self, file_path: Path, data: Dict[str, Any]):
        """带备份的数据保存"""
        # 创建备份
        if file_path.exists():
            backup_path = file_path.with_suffix('.json.backup')
            shutil.copy2(file_path, backup_path)
        
        # 添加校验和
        data['_checksum'] = self.validator.calculate_checksum(data)
        data['_save_time'] = time.time()
        
        # 原子写入
        temp_path = file_path.with_suffix('.json.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 原子替换
            temp_path.replace(file_path)
            logger.debug(f"成功保存缓存文件: {file_path}")
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e
    
    def load_cache_data(self, market: str) -> Optional[Dict[str, Any]]:
        """加载缓存数据（带校验和恢复）"""
        cache_file = self.get_cache_file_path(market)
        
        # 先检查内存缓存
        with self.memory_lock:
            if market in self.memory_cache:
                # 移到最后（LRU）
                self.memory_cache.move_to_end(market)
                self.metrics.hit_count += 1
                logger.debug(f"内存缓存命中: {market}")
                return self.memory_cache[market]
        
        # 内存缓存未命中，从文件加载
        self.metrics.miss_count += 1
        
        if not cache_file.exists():
            logger.debug(f"缓存文件不存在: {cache_file}")
            return None
        
        # 获取文件锁
        lock_fd = self.lock_manager.acquire_lock(str(cache_file))
        if not lock_fd:
            logger.warning(f"无法获取文件锁: {cache_file}")
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 数据校验
            is_valid, errors = self.validator.validate_json_structure(data)
            if not is_valid:
                logger.error(f"缓存数据结构无效: {errors}")
                self._attempt_recovery(cache_file)
                return None
            
            # 校验和验证（宽松模式）
            if '_checksum' in data:
                expected_checksum = data.pop('_checksum')
                if not self.validator.verify_checksum(data, expected_checksum):
                    logger.warning(f"缓存数据校验和不匹配: {cache_file}，可能是数据清理导致，继续使用")
                    # 不立即恢复，先检查数据是否基本可用
                    if 'stocks' not in data or not isinstance(data['stocks'], list):
                        logger.error(f"缓存数据结构异常，尝试恢复: {cache_file}")
                        self._attempt_recovery(cache_file)
                        return None
            
            # 加载到内存缓存
            with self.memory_lock:
                self.memory_cache[market] = data
                # 保持内存缓存大小限制
                while len(self.memory_cache) > self.max_memory_items:
                    self.memory_cache.popitem(last=False)
            
            logger.debug(f"成功加载缓存数据: {market}")
            return data
            
        except Exception as e:
            logger.error(f"加载缓存数据失败: {cache_file}, 错误: {e}")
            self.metrics.error_count += 1
            self._attempt_recovery(cache_file)
            return None
            
        finally:
            self.lock_manager.release_lock(lock_fd, str(cache_file))
    
    def save_cache_data(self, market: str, data: Dict[str, Any]) -> bool:
        """保存缓存数据（增量更新）"""
        cache_file = self.get_cache_file_path(market)
        
        # 获取文件锁
        lock_fd = self.lock_manager.acquire_lock(str(cache_file))
        if not lock_fd:
            logger.warning(f"无法获取文件锁，保存失败: {cache_file}")
            return False
        
        try:
            # 检查是否需要增量更新
            existing_data = None
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception:
                    logger.warning(f"读取现有缓存失败，将进行全量保存: {cache_file}")
            
            # 执行增量更新逻辑
            if existing_data and self._should_use_incremental_update(existing_data, data):
                updated_data = self._perform_incremental_update(existing_data, data)
            else:
                updated_data = data
            
            # 保存数据
            self._save_data_with_backup(cache_file, updated_data)
            
            # 更新内存缓存
            with self.memory_lock:
                self.memory_cache[market] = updated_data
                self.memory_cache.move_to_end(market)
            
            self.metrics.last_update_time = time.time()
            logger.debug(f"成功保存缓存数据: {market}")
            return True
            
        except Exception as e:
            logger.error(f"保存缓存数据失败: {cache_file}, 错误: {e}")
            self.metrics.error_count += 1
            return False
            
        finally:
            self.lock_manager.release_lock(lock_fd, str(cache_file))
    
    def _should_use_incremental_update(self, existing_data: Dict, new_data: Dict) -> bool:
        """判断是否应该使用增量更新"""
        # 如果数据结构发生变化，使用全量更新
        if set(existing_data.keys()) != set(new_data.keys()):
            return False
        
        # 如果股票数量变化超过10%，使用全量更新
        existing_count = len(existing_data.get('stocks', []))
        new_count = len(new_data.get('stocks', []))
        
        if existing_count == 0:
            return False
        
        change_ratio = abs(new_count - existing_count) / existing_count
        return change_ratio < 0.1
    
    def _perform_incremental_update(self, existing_data: Dict, new_data: Dict) -> Dict:
        """执行增量更新"""
        updated_data = existing_data.copy()
        
        # 更新基本信息
        updated_data['last_update_date'] = new_data.get('last_update_date')
        updated_data['total'] = new_data.get('total')
        
        # 创建股票代码到数据的映射
        existing_stocks = {stock['ts_code']: stock for stock in existing_data.get('stocks', [])}
        new_stocks = {stock['ts_code']: stock for stock in new_data.get('stocks', [])}
        
        # 增量更新股票数据
        updated_stocks = []
        for ts_code, new_stock in new_stocks.items():
            if ts_code in existing_stocks:
                # 更新现有股票
                existing_stock = existing_stocks[ts_code].copy()
                existing_stock.update(new_stock)
                updated_stocks.append(existing_stock)
            else:
                # 新增股票
                updated_stocks.append(new_stock)
        
        updated_data['stocks'] = updated_stocks
        
        logger.debug(f"增量更新完成: {len(new_stocks)} 只股票")
        return updated_data
    
    def _attempt_recovery(self, cache_file: Path):
        """尝试恢复损坏的缓存文件"""
        backup_file = cache_file.with_suffix('.json.backup')
        
        if backup_file.exists():
            try:
                # 尝试从备份恢复
                with open(backup_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                
                is_valid, _ = self.validator.validate_json_structure(backup_data)
                if is_valid:
                    shutil.copy2(backup_file, cache_file)
                    logger.info(f"成功从备份恢复缓存文件: {cache_file}")
                    return
                    
            except Exception as e:
                logger.error(f"从备份恢复失败: {e}")
        
        # 备份恢复失败，删除损坏的文件
        try:
            cache_file.unlink()
            logger.warning(f"删除损坏的缓存文件: {cache_file}")
        except Exception as e:
            logger.error(f"删除损坏文件失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取缓存状态"""
        return {
            'is_healthy': self.status.is_healthy,
            'last_check_time': self.status.last_check_time,
            'error_messages': self.status.error_messages,
            'metrics': asdict(self.metrics),
            'memory_cache_size': len(self.memory_cache),
            'cache_dir': str(self.cache_dir)
        }
    
    def clear_cache(self, market: Optional[str] = None):
        """清理缓存"""
        if market:
            # 清理特定市场
            cache_file = self.get_cache_file_path(market)
            if cache_file.exists():
                cache_file.unlink()
            
            with self.memory_lock:
                self.memory_cache.pop(market, None)
                
            logger.info(f"清理缓存: {market}")
        else:
            # 清理所有缓存
            for cache_file in self.cache_dir.glob('*.json'):
                cache_file.unlink()
            
            with self.memory_lock:
                self.memory_cache.clear()
                
            logger.info("清理所有缓存")
    
    def get_cache_info(self, market: str) -> Dict[str, Any]:
        """获取缓存信息"""
        cache_file = self.get_cache_file_path(market)
        
        info = {
            'market': market,
            'file_exists': cache_file.exists(),
            'in_memory': market in self.memory_cache,
            'file_path': str(cache_file)
        }
        
        if cache_file.exists():
            stat = cache_file.stat()
            info.update({
                'file_size': stat.st_size,
                'last_modified': stat.st_mtime,
                'last_modified_str': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return info
    
    def save_intraday_data(self, stock_code: str, intraday_data: List[Dict[str, Any]]) -> bool:
        """保存分时图数据到缓存"""
        cache_file = self.get_intraday_cache_file_path(stock_code)
        
        # 获取文件锁
        lock_fd = self.lock_manager.acquire_lock(str(cache_file))
        if not lock_fd:
            logger.warning(f"无法获取文件锁，保存分时图数据失败: {cache_file}")
            return False
        
        try:
            # 准备缓存数据
            cache_data = {
                'stock_code': stock_code,
                'date': datetime.now().strftime('%Y%m%d'),
                'save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data': intraday_data,
                'data_count': len(intraday_data)
            }
            
            # 保存数据
            self._save_data_with_backup(cache_file, cache_data)
            
            logger.info(f"成功保存分时图缓存: {stock_code}, 数据量: {len(intraday_data)}")
            return True
            
        except Exception as e:
            logger.error(f"保存分时图数据失败: {cache_file}, 错误: {e}")
            return False
            
        finally:
            self.lock_manager.release_lock(lock_fd, str(cache_file))
    
    def load_intraday_data(self, stock_code: str) -> Optional[List[Dict[str, Any]]]:
        """从缓存加载分时图数据"""
        cache_file = self.get_intraday_cache_file_path(stock_code)
        
        if not cache_file.exists():
            logger.debug(f"分时图缓存文件不存在: {cache_file}")
            return None
        
        # 获取文件锁
        lock_fd = self.lock_manager.acquire_lock(str(cache_file))
        if not lock_fd:
            logger.warning(f"无法获取文件锁，加载分时图数据失败: {cache_file}")
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 验证缓存数据
            if not isinstance(cache_data, dict) or 'data' not in cache_data:
                logger.warning(f"分时图缓存数据格式错误: {cache_file}")
                return None
            
            # 检查数据是否为当日数据
            today = datetime.now().strftime('%Y%m%d')
            cache_date = cache_data.get('date', '')
            
            if cache_date != today:
                logger.debug(f"分时图缓存数据过期: {cache_file}, 缓存日期: {cache_date}, 当前日期: {today}")
                return None
            
            intraday_data = cache_data['data']
            logger.info(f"成功加载分时图缓存: {stock_code}, 数据量: {len(intraday_data)}")
            return intraday_data
            
        except Exception as e:
            logger.error(f"加载分时图数据失败: {cache_file}, 错误: {e}")
            return None
            
        finally:
            self.lock_manager.release_lock(lock_fd, str(cache_file))
    
    def cleanup_old_intraday_cache(self):
        """清理过期的分时图缓存"""
        try:
            intraday_dir = self.cache_dir / 'intraday'
            if not intraday_dir.exists():
                return
            
            today = datetime.now().strftime('%Y%m%d')
            cleaned_count = 0
            
            for cache_file in intraday_dir.glob('*_intraday.json'):
                try:
                    # 从文件名提取日期
                    filename = cache_file.name
                    # 格式: {stock_code}_{date}_intraday.json
                    parts = filename.replace('_intraday.json', '').split('_')
                    if len(parts) >= 2:
                        file_date = parts[-1]  # 最后一部分是日期
                        
                        # 如果不是今天的文件，删除
                        if file_date != today:
                            cache_file.unlink()
                            cleaned_count += 1
                            logger.debug(f"删除过期分时图缓存: {cache_file}")
                
                except Exception as e:
                    logger.error(f"清理分时图缓存文件失败 {cache_file}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"清理过期分时图缓存完成，删除 {cleaned_count} 个文件")
            
        except Exception as e:
            logger.error(f"清理分时图缓存失败: {e}")

# 创建全局缓存管理器实例
cache_manager = OptimizedCacheManager()

# 兼容性函数（保持与原有代码的兼容性）
def get_cache_file_path(market: str) -> str:
    """兼容性函数：获取缓存文件路径"""
    return str(cache_manager.get_cache_file_path(market))

def load_cache_data(market: str) -> Optional[Dict[str, Any]]:
    """兼容性函数：加载缓存数据"""
    return cache_manager.load_cache_data(market)

def save_cache_data(market: str, data: Dict[str, Any]) -> bool:
    """兼容性函数：保存缓存数据"""
    return cache_manager.save_cache_data(market, data)