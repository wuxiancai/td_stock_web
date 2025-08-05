"""
环境配置管理工具
支持多环境配置和动态配置更新
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import logging

@dataclass
class DatabaseConfig:
    """数据库配置"""
    path: str = "data/stock_data.db"
    max_connections: int = 10
    timeout: float = 30.0
    backup_enabled: bool = True
    backup_interval: int = 3600  # 秒

@dataclass
class ApiConfig:
    """API配置"""
    tushare_token: Optional[str] = None
    rate_limit_per_minute: int = 199
    timeout: float = 30.0
    retry_times: int = 3
    retry_delay: float = 1.0

@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    directory: str = "cache"
    default_ttl: int = 3600
    max_size_mb: int = 500
    cleanup_interval: int = 7200  # 秒

@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/app.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_output: bool = True

@dataclass
class SecurityConfig:
    """安全配置"""
    secret_key: str = field(default_factory=lambda: os.urandom(24).hex())
    session_timeout: int = 3600
    max_request_size: int = 16 * 1024 * 1024  # 16MB
    rate_limit_enabled: bool = True
    cors_enabled: bool = True
    allowed_origins: list = field(default_factory=lambda: ["*"])

@dataclass
class AppConfig:
    """应用配置"""
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.config: Optional[AppConfig] = None
        self.logger = logging.getLogger(__name__)
    
    def load_config(self, environment: str = None) -> AppConfig:
        """加载配置"""
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")
        
        # 配置文件优先级：
        # 1. 环境变量
        # 2. 环境特定配置文件 (config/{environment}.yaml)
        # 3. 默认配置文件 (config/default.yaml)
        # 4. 代码默认值
        
        config = AppConfig()
        config.environment = environment
        
        # 加载默认配置文件
        default_config_path = self.config_dir / "default.yaml"
        if default_config_path.exists():
            self._load_from_file(config, default_config_path)
        
        # 加载环境特定配置文件
        env_config_path = self.config_dir / f"{environment}.yaml"
        if env_config_path.exists():
            self._load_from_file(config, env_config_path)
        
        # 从环境变量覆盖配置
        self._load_from_env(config)
        
        # 验证配置
        self._validate_config(config)
        
        self.config = config
        return config
    
    def _load_from_file(self, config: AppConfig, file_path: Path):
        """从文件加载配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif file_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    self.logger.warning(f"不支持的配置文件格式: {file_path}")
                    return
            
            self._merge_config(config, data)
            self.logger.info(f"已加载配置文件: {file_path}")
            
        except Exception as e:
            self.logger.error(f"加载配置文件失败 {file_path}: {e}")
    
    def _load_from_env(self, config: AppConfig):
        """从环境变量加载配置"""
        env_mappings = {
            'DEBUG': ('debug', bool),
            'HOST': ('host', str),
            'PORT': ('port', int),
            'TUSHARE_TOKEN': ('api.tushare_token', str),
            'DATABASE_PATH': ('database.path', str),
            'CACHE_ENABLED': ('cache.enabled', bool),
            'LOG_LEVEL': ('logging.level', str),
            'SECRET_KEY': ('security.secret_key', str),
        }
        
        for env_key, (config_path, value_type) in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                try:
                    # 类型转换
                    if value_type == bool:
                        env_value = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif value_type == int:
                        env_value = int(env_value)
                    elif value_type == float:
                        env_value = float(env_value)
                    
                    # 设置配置值
                    self._set_nested_value(config, config_path, env_value)
                    self.logger.info(f"从环境变量加载配置: {env_key} -> {config_path}")
                    
                except (ValueError, TypeError) as e:
                    self.logger.error(f"环境变量类型转换失败 {env_key}: {e}")
    
    def _merge_config(self, config: AppConfig, data: Dict[str, Any]):
        """合并配置数据"""
        for key, value in data.items():
            if hasattr(config, key):
                current_value = getattr(config, key)
                if isinstance(current_value, (DatabaseConfig, ApiConfig, CacheConfig, 
                                            LoggingConfig, SecurityConfig)):
                    # 嵌套配置对象
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if hasattr(current_value, sub_key):
                                setattr(current_value, sub_key, sub_value)
                else:
                    # 简单属性
                    setattr(config, key, value)
    
    def _set_nested_value(self, obj: Any, path: str, value: Any):
        """设置嵌套属性值"""
        parts = path.split('.')
        current = obj
        
        for part in parts[:-1]:
            current = getattr(current, part)
        
        setattr(current, parts[-1], value)
    
    def _validate_config(self, config: AppConfig):
        """验证配置"""
        errors = []
        
        # 验证端口范围
        if not (1 <= config.port <= 65535):
            errors.append(f"端口号无效: {config.port}")
        
        # 验证数据库路径
        db_dir = Path(config.database.path).parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建数据库目录: {e}")
        
        # 验证缓存目录
        cache_dir = Path(config.cache.directory)
        if not cache_dir.exists():
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建缓存目录: {e}")
        
        # 验证日志目录
        log_dir = Path(config.logging.file_path).parent
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建日志目录: {e}")
        
        if errors:
            raise ValueError(f"配置验证失败: {'; '.join(errors)}")
    
    def save_config(self, config: AppConfig = None, file_name: str = None):
        """保存配置到文件"""
        if config is None:
            config = self.config
        
        if file_name is None:
            file_name = f"{config.environment}.yaml"
        
        config_path = self.config_dir / file_name
        
        try:
            config_dict = self._config_to_dict(config)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            
            self.logger.info(f"配置已保存到: {config_path}")
            
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            raise
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """将配置对象转换为字典"""
        def dataclass_to_dict(obj):
            if hasattr(obj, '__dataclass_fields__'):
                return {
                    field_name: dataclass_to_dict(getattr(obj, field_name))
                    for field_name in obj.__dataclass_fields__
                }
            elif isinstance(obj, list):
                return [dataclass_to_dict(item) for item in obj]
            else:
                return obj
        
        return dataclass_to_dict(config)
    
    def get_config(self) -> AppConfig:
        """获取当前配置"""
        if self.config is None:
            raise ValueError("配置未加载，请先调用 load_config()")
        return self.config
    
    def reload_config(self):
        """重新加载配置"""
        if self.config:
            environment = self.config.environment
            self.load_config(environment)
            self.logger.info("配置已重新加载")

# 全局配置管理器实例
config_manager = ConfigManager()

def get_config() -> AppConfig:
    """获取全局配置"""
    return config_manager.get_config()

def load_config(environment: str = None) -> AppConfig:
    """加载全局配置"""
    return config_manager.load_config(environment)