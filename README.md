# 股票数据展示系统

一个基于Flask的实时股票数据展示系统，支持K线图、分时图等多种数据可视化功能。

## 🌟 特性

- **实时数据**: 支持多个数据源（Tushare、AkShare等）
- **多种图表**: K线图、分时图、技术指标图表
- **响应式设计**: 适配桌面和移动设备
- **高性能**: 数据库连接池、缓存机制、异步处理
- **可扩展**: 模块化设计，易于扩展新功能

## 📊 系统架构

```
td_stock_web/
├── app.py                 # Flask主应用
├── config/               # 配置文件
│   ├── development.yaml
│   └── production.yaml
├── utils/                # 工具模块
│   ├── config_utils.py   # 配置管理
│   ├── database_utils.py # 数据库工具
│   ├── response_utils.py # API响应工具
│   ├── env_config.py     # 环境配置
│   └── ...
├── static/               # 静态资源
│   ├── css/
│   ├── js/
│   └── images/
├── templates/            # HTML模板
└── data/                # 数据文件
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- SQLite 3
- 现代浏览器

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境

1. 复制配置文件：
```bash
cp config/development.yaml.example config/development.yaml
```

2. 编辑配置文件，设置API密钥等参数

3. 设置环境变量：
```bash
export ENVIRONMENT=development
export TUSHARE_TOKEN=your_token_here
```

### 启动应用

```bash
# 开发环境
python3 app.py

# 生产环境部署
./deploy.sh production
```

访问 http://localhost:8080 查看应用

## 📈 功能模块

### 1. 股票数据获取

- **Tushare API**: 专业的金融数据接口
- **AkShare**: 开源金融数据库
- **实时数据**: 支持分时数据获取
- **历史数据**: K线数据、财务数据等

### 2. 数据可视化

- **K线图**: 基于ECharts的专业K线图表
- **分时图**: 实时价格走势图
- **技术指标**: MA、RSI、MACD等
- **成交量**: 成交量柱状图

### 3. 数据管理

- **缓存机制**: 内存+文件双重缓存
- **数据验证**: 多级数据验证机制
- **性能监控**: API调用性能统计
- **错误处理**: 完善的异常处理机制

## 🛠️ 开发指南

### 代码结构

```python
# API路由示例
@app.route('/api/stock/<stock_code>')
@api_response_wrapper
def get_stock_data(stock_code):
    """获取股票基本信息"""
    # 业务逻辑
    return stock_data

# 数据库操作示例
from utils.database_utils import get_database_pool

pool = get_database_pool()
with pool.get_connection() as conn:
    cursor = conn.execute("SELECT * FROM stocks WHERE code = ?", (stock_code,))
    return cursor.fetchall()
```

### 前端组件

```javascript
// 创建图表
const chartManager = new StockChartManager();
const chart = chartManager.createKlineChart('container', data);

// 数据处理
const processor = new DataProcessor();
const ma5 = processor.calculateMA(data, 5);
```

### 配置管理

```python
from utils.env_config import ConfigManager

config = ConfigManager()
db_config = config.get_database_config()
api_config = config.get_api_config()
```

## 🔧 配置说明

### 数据库配置

```yaml
database:
  type: sqlite
  path: data/stock_data.db
  pool_size: 10
  timeout: 30
```

### API配置

```yaml
api:
  tushare:
    token: ${TUSHARE_TOKEN}
    timeout: 30
  akshare:
    timeout: 15
```

### 缓存配置

```yaml
cache:
  memory:
    max_size: 1000
    ttl: 300
  file:
    enabled: true
    path: data/cache
```

## 📊 性能优化

### 数据库优化

- 连接池管理
- 索引优化
- 查询缓存
- WAL模式

### 前端优化

- 组件化设计
- 懒加载
- 代码分割
- 图片优化

### 缓存策略

- 多级缓存
- 智能过期
- 预加载机制
- 缓存预热

## 🔒 安全特性

- **输入验证**: 严格的参数验证
- **SQL注入防护**: 参数化查询
- **CSRF保护**: 跨站请求伪造防护
- **错误处理**: 安全的错误信息返回

## 📱 部署指南

### 开发环境

```bash
# 启动开发服务器
python3 app.py
```

### 生产环境

```bash
# 使用部署脚本
./deploy.sh production

# 或手动部署
gunicorn --bind 0.0.0.0:8080 --workers 4 app:app
```

### Docker部署

```bash
# 构建镜像
docker build -t stock-web .

# 运行容器
docker run -p 8080:8080 -e ENVIRONMENT=production stock-web
```

### Nginx配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static/ {
        alias /path/to/static/;
        expires 1y;
    }
}
```

## 📊 监控和日志

### 应用监控

- 性能指标收集
- 错误率统计
- API响应时间
- 系统资源使用

### 日志管理

- 结构化日志
- 日志轮转
- 错误告警
- 审计日志

## 🧪 测试

### 单元测试

```bash
pytest tests/unit/
```

### 集成测试

```bash
pytest tests/integration/
```

### 性能测试

```bash
locust -f tests/performance/locustfile.py
```

## 📚 API文档

### 股票基本信息

```
GET /api/stock/{stock_code}
```

响应示例：
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "code": "000001",
        "name": "平安银行",
        "price": 12.34,
        "change": 0.12,
        "change_pct": 0.98
    }
}
```

### K线数据

```
GET /api/kline/{stock_code}?period=1d&limit=100
```

### 分时数据

```
GET /api/realtime/{stock_code}
```

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

### 代码规范

- 使用 Black 进行代码格式化
- 遵循 PEP 8 编码规范
- 编写单元测试
- 更新文档

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [Tushare](https://tushare.pro/) - 专业的金融数据接口
- [AkShare](https://github.com/akfamily/akshare) - 开源财经数据接口库
- [ECharts](https://echarts.apache.org/) - 强大的数据可视化库
- [Flask](https://flask.palletsprojects.com/) - 轻量级Web框架

## 📞 支持

如有问题或建议，请：

- 创建 [Issue](https://github.com/your-repo/issues)
- 发送邮件至 support@example.com
- 查看 [Wiki](https://github.com/your-repo/wiki) 文档

---

**最后更新**: 2025年7月18日  
**版本**: v2.0.0