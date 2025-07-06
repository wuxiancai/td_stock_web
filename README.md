# 九转序列选股系统

基于九转序列技术指标的智能选股平台，集成Tushare数据源，提供股票筛选、K线图分析和技术指标展示功能。

## 功能特性

### 前端功能
- **股票搜索**: 支持6位股票代码快速搜索
- **市场分类**: 创业板、沪A、中小板、北交所股票列表
- **股票详情**: 完整的股票信息展示
- **K线图表**: 90天日K线图，集成九转序列标注
- **技术指标**: MACD指标图表
- **响应式设计**: 支持移动端和桌面端

### 后端功能
- **数据获取**: 集成Tushare Pro API
- **频率限制**: 智能API调用频率控制，每分钟最多199次请求
- **九转序列**: 自动计算九转序列买卖信号
- **MACD指标**: 计算MACD、信号线和柱状图
- **端口自适应**: 自动检测可用端口(8080-8089)
- **RESTful API**: 标准化API接口

## 技术栈

- **后端**: Python Flask
- **前端**: HTML5 + CSS3 + JavaScript
- **图表**: ECharts 5.4.3
- **数据源**: Tushare Pro
- **样式**: 渐变色彩设计，现代化UI

## 安装和运行

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置Tushare Token
项目已配置Token: `68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019`

### 3. 启动服务
```bash
python app.py
```

服务器将自动检测可用端口并启动，默认尝试8080端口。

### 4. 访问应用
打开浏览器访问: `http://localhost:端口号`

## API接口

### 股票详情
```
GET /api/stock/{stock_code}
```
返回股票的详细信息、K线数据、九转序列和MACD指标。

### 市场股票列表
```
GET /api/stocks/{market}?page={page}
```
- market: cyb(创业板), hu(沪A), zxb(中小板), bj(北交所)
- page: 页码，每页50条记录

### 频率限制器状态
```
GET /api/rate_limiter/status
```
返回Tushare API调用频率限制器的当前状态，包括已使用请求数、剩余请求数等信息。

## 九转序列说明

九转序列是一种技术分析工具，用于识别股价的转折点：

- **上涨九转**: 连续上涨天数标注(红色数字)
- **下跌九转**: 连续下跌天数标注(绿色数字)
- **信号意义**: 当出现9时，通常预示着趋势可能反转

## 项目结构

```
td_stock/
├── app.py                 # Flask主应用
├── requirements.txt       # Python依赖
├── README.md             # 项目说明
└── templates/            # HTML模板
    ├── index.html        # 首页
    └── stock_detail.html # 股票详情页
```

## 注意事项

1. **频率限制**: 系统已集成智能频率控制，自动限制Tushare API每分钟最多199次请求，确保不超过官方限制
2. **网络要求**: 需要稳定的网络连接获取实时数据
3. **浏览器兼容**: 推荐使用Chrome、Firefox等现代浏览器
4. **数据延迟**: 股票数据可能有15-20分钟延迟
5. **API监控**: 可通过 `/api/rate_limiter/status` 实时查看API使用情况

## 开发说明

- 九转序列算法基于连续涨跌天数计算
- MACD使用标准参数(12,26,9)
- K线图支持缩放和数据筛选
- 响应式设计适配不同屏幕尺寸
- 频率限制器使用滑动窗口算法，线程安全，自动处理API调用间隔
- 所有Tushare API调用都通过 `safe_tushare_call()` 函数进行频率控制

## 测试工具

项目包含频率限制器测试脚本：
```bash
# 测试API端点（需要服务器运行）
python test_rate_limiter.py

# 测试本地频率限制器类
python test_rate_limiter.py --local
```