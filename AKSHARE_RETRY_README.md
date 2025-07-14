# AkShare 定时重试机制

## 功能概述

本系统实现了针对 AkShare 数据接口的智能重试机制，当网络异常或数据源不可用时，系统会自动记录失败请求并在指定时间后重试，确保数据获取的稳定性和可靠性。

## 核心特性

### 🔄 自动重试机制
- **智能失败检测**: 自动识别网络错误、超时、数据源异常等问题
- **定时重试**: 失败后等待 5 分钟自动重试，避免频繁请求
- **多次重试**: 支持多次重试，直到成功或达到最大重试次数
- **错误分类**: 区分网络错误和其他异常，采用不同的处理策略

### 📊 状态监控
- **实时状态查询**: 通过 API 接口查看当前重试状态
- **详细错误信息**: 记录失败原因、时间、重试次数等详细信息
- **倒计时显示**: 显示距离下次重试的剩余时间

### 🧹 自动清理
- **定时清理**: 每天凌晨 2 点自动清理超过 24 小时的失败记录
- **内存优化**: 防止长期运行导致的内存泄漏

## 技术实现

### AkShareRetryManager 类

```python
class AkShareRetryManager:
    def __init__(self, retry_interval_minutes=5):
        self.retry_interval_minutes = retry_interval_minutes
        self.failed_requests = {}  # 存储失败的请求信息
        self.lock = threading.Lock()  # 线程安全
```

**主要方法:**
- `should_retry(request_key)`: 判断是否应该重试
- `record_failure(request_key, error_message)`: 记录失败信息
- `record_success(request_key)`: 记录成功，清除失败记录
- `get_retry_status()`: 获取当前重试状态
- `cleanup_old_failures()`: 清理过期记录

### safe_akshare_call 函数

```python
def safe_akshare_call(func, request_key, *args, **kwargs):
    """安全的 AkShare API 调用，包含重试机制"""
```

**功能特点:**
- 检查 AkShare 库可用性
- 判断是否需要跳过重试
- 处理空数据返回
- 区分错误类型并记录
- 返回统一的错误响应

## API 接口

### 查看重试状态

```http
GET /api/akshare/retry_status
```

**响应示例:**
```json
{
  "success": true,
  "data": {
    "total_failed_requests": 3,
    "retry_interval_minutes": 5,
    "failed_requests": [
      {
        "request_key": "spot_data_000001",
        "failure_count": 2,
        "first_failure_time": "2025-07-14 11:18:53",
        "last_attempt_time": "2025-07-14 11:23:53",
        "last_error": "HTTPSConnectionPool timeout",
        "next_retry_in_seconds": 180,
        "can_retry_now": false
      }
    ]
  }
}
```

## 使用方法

### 1. 启动应用

```bash
python3 app.py
```

启动时会显示重试机制状态:
```
AkShare重试机制已启用: 失败后300秒重试间隔
可通过 /api/akshare/retry_status 查看重试状态
```

### 2. 测试重试机制

```bash
# 运行测试脚本
python3 test_retry_mechanism.py

# 运行监控工具
python3 monitor_retry.py
```

### 3. 监控重试状态

**方法一: 使用监控脚本**
```bash
python3 monitor_retry.py
# 选择 "1. 监控重试状态"
```

**方法二: 直接调用 API**
```bash
curl http://localhost:8080/api/akshare/retry_status
```

**方法三: 在浏览器中查看**
```
http://localhost:8080/api/akshare/retry_status
```

## 集成的数据接口

重试机制已集成到以下 AkShare 数据接口:

1. **实时行情数据** (`ak.stock_zh_a_spot_em`)
   - 股票价格、涨跌幅、换手率、量比等
   - 请求标识: `spot_data_{stock_code}`

2. **分时图数据** (`ak.stock_zh_a_minute`)
   - 1分钟级别的价格和成交量数据
   - 请求标识: `minute_data_{stock_code}`

3. **K线数据** (`ak.stock_zh_a_hist`)
   - 日K线历史数据
   - 请求标识: `kline_data_{stock_code}_{period}_{adjust}`

4. **资金流向数据** (`ak.stock_individual_fund_flow`)
   - 个股资金流入流出数据
   - 请求标识: `fund_flow_{stock_code}`

## 配置参数

### 重试间隔
```python
# 默认 5 分钟，可在初始化时修改
akshare_retry_manager = AkShareRetryManager(retry_interval_minutes=5)
```

### 清理周期
```python
# 每天凌晨 2 点清理过期记录
scheduler.add_job(
    cleanup_akshare_failures,
    'cron',
    hour=2,
    minute=0,
    id='cleanup_akshare_failures'
)
```

## 错误处理

### 网络错误
- `requests.exceptions.RequestException`
- `urllib3.exceptions.*`
- `socket.timeout`
- `ConnectionError`

### 数据异常
- 空数据返回
- JSON 解析错误
- 数据格式异常

### 系统异常
- AkShare 库导入失败
- 内存不足
- 其他未知错误

## 日志记录

系统会记录详细的重试日志:

```
2025-07-14 11:18:53 - AkShare重试 - WARNING - spot_data_000001 请求失败: HTTPSConnectionPool timeout
2025-07-14 11:23:53 - AkShare重试 - INFO - spot_data_000001 开始第2次重试
2025-07-14 11:23:55 - AkShare重试 - INFO - spot_data_000001 重试成功
```

## 性能优化

### 内存管理
- 使用线程锁确保并发安全
- 定时清理过期记录
- 限制失败记录数量

### 网络优化
- 避免频繁重试
- 智能退避策略
- 连接池复用

## 故障排查

### 常见问题

1. **重试不生效**
   - 检查 AkShare 库是否正确安装
   - 确认网络连接状态
   - 查看错误日志

2. **重试过于频繁**
   - 调整重试间隔参数
   - 检查错误分类逻辑

3. **内存占用过高**
   - 检查清理任务是否正常运行
   - 调整清理周期

### 调试命令

```bash
# 查看当前重试状态
curl http://localhost:8080/api/akshare/retry_status

# 测试单个接口
curl http://localhost:8080/api/stock/000001/realtime

# 查看应用日志
tail -f app.log
```

## 扩展开发

### 添加新的重试接口

```python
# 在需要重试的地方使用 safe_akshare_call
result = safe_akshare_call(
    ak.your_new_function,
    f"your_request_key_{param}",
    param1=value1,
    param2=value2
)
```

### 自定义重试策略

```python
# 继承 AkShareRetryManager 类
class CustomRetryManager(AkShareRetryManager):
    def should_retry(self, request_key):
        # 自定义重试逻辑
        return super().should_retry(request_key)
```

## 总结

AkShare 定时重试机制为股票数据获取提供了强大的容错能力，通过智能重试、状态监控和自动清理等功能，确保了系统在网络不稳定环境下的可靠运行。该机制已无缝集成到现有的数据接口中，无需额外配置即可使用。