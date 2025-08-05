"""
配置管理和环境适配工具
提供统一的配置管理、环境检测和适配功能
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

class Environment(Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"

@dataclass
class APIConfig:
    """API配置"""
    name: str
    base_url: str = ""
    timeout: int = 30
    retry_count: int = 3
    rate_limit: int = 60  # 每分钟调用次数
    api_key: Optional[str] = None
    enabled: bool = True

@dataclass
class DatabaseConfig:
    """数据库配置"""
    host: str = "localhost"
    port: int = 5432
    database: str = "stock_data"
    username: str = ""
    password: str = ""
    pool_size: int = 10

@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    default_ttl: int = 3600  # 默认过期时间（秒）
    max_memory_items: int = 1000
    cache_dir: str = "cache"
    cleanup_interval: int = 3600  # 清理间隔（秒）

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
class StockConfig:
    """股票配置"""
    default_period: str = "1d"
    max_data_points: int = 1000
    price_precision: int = 2
    volume_unit: str = "手"
    amount_unit: str = "万元"

@dataclass
class AppConfig:
    """应用配置"""
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 5000
    secret_key: str = "dev-secret-key"
    
    # 子配置
    apis: Dict[str, APIConfig] = field(default_factory=dict)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    stock: StockConfig = field(default_factory=StockConfig)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self._config: Optional[AppConfig] = None
        self._environment = self._detect_environment()
    
    def _detect_environment(self) -> Environment:
        """检测运行环境"""
        env_var = os.getenv('FLASK_ENV', os.getenv('APP_ENV', 'development')).lower()
        
        if env_var in ['prod', 'production']:
            return Environment.PRODUCTION
        elif env_var in ['test', 'testing']:
            return Environment.TESTING
        else:
            return Environment.DEVELOPMENT
    
    def load_config(self, config_file: Optional[str] = None) -> AppConfig:
        """加载配置"""
        if config_file is None:
            config_file = f"{self._environment.value}.yaml"
        
        config_path = self.config_dir / config_file
        
        # 如果配置文件不存在，创建默认配置
        if not config_path.exists():
            self._create_default_config(config_path)
        
        # 加载配置文件
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    config_data = yaml.safe_load(f)
            
            self._config = self._parse_config(config_data)
            
        except Exception as e:
            print(f"警告: 无法加载配置文件 {config_path}: {e}")
            print("使用默认配置")
            self._config = self._create_default_app_config()
        
        # 应用环境变量覆盖
        self._apply_env_overrides()
        
        return self._config
    
    def _create_default_config(self, config_path: Path) -> None:
        """创建默认配置文件"""
        default_config = self._get_default_config_dict()
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(default_config, f, default_flow_style=False, 
                             allow_unicode=True, indent=2)
            
            print(f"已创建默认配置文件: {config_path}")
            
        except Exception as e:
            print(f"警告: 无法创建配置文件 {config_path}: {e}")
    
    def _get_default_config_dict(self) -> Dict[str, Any]:
        """获取默认配置字典"""
        return {
            'app': {
                'environment': self._environment.value,
                'debug': self._environment == Environment.DEVELOPMENT,
                'host': '127.0.0.1',
                'port': 5000,
                'secret_key': 'change-this-in-production'
            },
            'apis': {
                'tushare': {
                    'name': 'Tushare',
                    'base_url': 'http://api.tushare.pro',
                    'timeout': 30,
                    'retry_count': 3,
                    'rate_limit': 60,
                    'enabled': True
                },
                'akshare': {
                    'name': 'AkShare',
                    'timeout': 30,
                    'retry_count': 3,
                    'rate_limit': 120,
                    'enabled': True
                }
            },
            'database': {
                'host': 'localhost',
                'port': 5432,
                'database': 'stock_data',
                'username': '',
                'password': '',
                'pool_size': 10
            },
            'cache': {
                'enabled': True,
                'default_ttl': 3600,
                'max_memory_items': 1000,
                'cache_dir': 'cache',
                'cleanup_interval': 3600
            },
            'logging': {
                'level': 'DEBUG' if self._environment == Environment.DEVELOPMENT else 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file_path': f'logs/{self._environment.value}.log',
                'max_file_size': 10485760,  # 10MB
                'backup_count': 5,
                'console_output': True
            },
            'stock': {
                'default_period': '1d',
                'max_data_points': 1000,
                'price_precision': 2,
                'volume_unit': '手',
                'amount_unit': '万元'
            }
        }
    
    def _parse_config(self, config_data: Dict[str, Any]) -> AppConfig:
        """解析配置数据"""
        app_data = config_data.get('app', {})
        
        # 解析API配置
        apis = {}
        for api_name, api_data in config_data.get('apis', {}).items():
            apis[api_name] = APIConfig(
                name=api_data.get('name', api_name),
                base_url=api_data.get('base_url', ''),
                timeout=api_data.get('timeout', 30),
                retry_count=api_data.get('retry_count', 3),
                rate_limit=api_data.get('rate_limit', 60),
                api_key=api_data.get('api_key'),
                enabled=api_data.get('enabled', True)
            )
        
        # 解析其他配置
        database_data = config_data.get('database', {})
        cache_data = config_data.get('cache', {})
        logging_data = config_data.get('logging', {})
        stock_data = config_data.get('stock', {})
        
        return AppConfig(
            environment=Environment(app_data.get('environment', 'development')),
            debug=app_data.get('debug', True),
            host=app_data.get('host', '127.0.0.1'),
            port=app_data.get('port', 5000),
            secret_key=app_data.get('secret_key', 'dev-secret-key'),
            apis=apis,
            database=DatabaseConfig(**database_data),
            cache=CacheConfig(**cache_data),
            logging=LoggingConfig(**logging_data),
            stock=StockConfig(**stock_data)
        )
    
    def _create_default_app_config(self) -> AppConfig:
        """创建默认应用配置"""
        config_dict = self._get_default_config_dict()
        return self._parse_config(config_dict)
    
    def _apply_env_overrides(self) -> None:
        """应用环境变量覆盖"""
        if not self._config:
            return
        
        # 应用级别的环境变量
        if os.getenv('APP_HOST'):
            self._config.host = os.getenv('APP_HOST')
        
        if os.getenv('APP_PORT'):
            try:
                self._config.port = int(os.getenv('APP_PORT'))
            except ValueError:
                pass
        
        if os.getenv('APP_SECRET_KEY'):
            self._config.secret_key = os.getenv('APP_SECRET_KEY')
        
        # API密钥
        for api_name in self._config.apis:
            env_key = f'{api_name.upper()}_API_KEY'
            if os.getenv(env_key):
                self._config.apis[api_name].api_key = os.getenv(env_key)
        
        # 数据库配置
        if os.getenv('DB_HOST'):
            self._config.database.host = os.getenv('DB_HOST')
        
        if os.getenv('DB_PORT'):
            try:
                self._config.database.port = int(os.getenv('DB_PORT'))
            except ValueError:
                pass
        
        if os.getenv('DB_NAME'):
            self._config.database.database = os.getenv('DB_NAME')
        
        if os.getenv('DB_USER'):
            self._config.database.username = os.getenv('DB_USER')
        
        if os.getenv('DB_PASSWORD'):
            self._config.database.password = os.getenv('DB_PASSWORD')
    
    def get_config(self) -> AppConfig:
        """获取配置"""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def save_config(self, config: AppConfig, config_file: Optional[str] = None) -> None:
        """保存配置"""
        if config_file is None:
            config_file = f"{config.environment.value}.yaml"
        
        config_path = self.config_dir / config_file
        
        # 转换为字典
        config_dict = self._config_to_dict(config)
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, 
                             allow_unicode=True, indent=2)
            
            print(f"配置已保存到: {config_path}")
            
        except Exception as e:
            print(f"错误: 无法保存配置文件 {config_path}: {e}")
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """将配置对象转换为字典"""
        return {
            'app': {
                'environment': config.environment.value,
                'debug': config.debug,
                'host': config.host,
                'port': config.port,
                'secret_key': config.secret_key
            },
            'apis': {
                name: {
                    'name': api.name,
                    'base_url': api.base_url,
                    'timeout': api.timeout,
                    'retry_count': api.retry_count,
                    'rate_limit': api.rate_limit,
                    'api_key': api.api_key,
                    'enabled': api.enabled
                }
                for name, api in config.apis.items()
            },
            'database': {
                'host': config.database.host,
                'port': config.database.port,
                'database': config.database.database,
                'username': config.database.username,
                'password': config.database.password,
                'pool_size': config.database.pool_size
            },
            'cache': {
                'enabled': config.cache.enabled,
                'default_ttl': config.cache.default_ttl,
                'max_memory_items': config.cache.max_memory_items,
                'cache_dir': config.cache.cache_dir,
                'cleanup_interval': config.cache.cleanup_interval
            },
            'logging': {
                'level': config.logging.level,
                'format': config.logging.format,
                'file_path': config.logging.file_path,
                'max_file_size': config.logging.max_file_size,
                'backup_count': config.logging.backup_count,
                'console_output': config.logging.console_output
            },
            'stock': {
                'default_period': config.stock.default_period,
                'max_data_points': config.stock.max_data_points,
                'price_precision': config.stock.price_precision,
                'volume_unit': config.stock.volume_unit,
                'amount_unit': config.stock.amount_unit
            }
        }

# 全局配置管理器
config_manager = ConfigManager()

# 便捷函数
def get_config() -> AppConfig:
    """获取应用配置"""
    return config_manager.get_config()

def get_api_config(api_name: str) -> Optional[APIConfig]:
    """获取API配置"""
    config = get_config()
    return config.apis.get(api_name)

def is_development() -> bool:
    """是否为开发环境"""
    return get_config().environment == Environment.DEVELOPMENT

def is_production() -> bool:
    """是否为生产环境"""
    return get_config().environment == Environment.PRODUCTION