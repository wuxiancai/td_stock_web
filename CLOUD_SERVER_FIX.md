# 云服务器指数数据显示问题解决方案

## 问题描述
在云服务器上访问 `http://127.0.0.1:8080` 时，指数数据显示不正确（显示固定的模拟数据），但在本地 macOS 上访问相同地址数据正确。

## 根本原因
问题出现在 `app.py` 文件的指数数据重试机制中：

1. **重试机制触发**：当 AkShare 或 Tushare API 获取数据失败时，系统会设置 `last_retry_time` 全局变量
2. **模拟数据返回**：在重试间隔期间（120秒），系统会返回硬编码的模拟数据而不是真实数据
3. **环境差异**：云服务器环境可能由于网络、防火墙或其他因素导致 API 调用更容易失败

## 关键代码位置

### 问题代码（app.py 第1015-1030行）
```python
# 检查是否需要等待重试间隔
current_time = datetime.now()
if last_retry_time and (current_time - last_retry_time).total_seconds() < retry_interval:
    remaining_time = retry_interval - (current_time - last_retry_time).total_seconds()
    print(f"距离下次重试还有 {remaining_time:.0f} 秒，使用缓存的模拟数据")
    return get_fallback_indices_data(indices)  # 返回硬编码的模拟数据
```

### 模拟数据定义（app.py 第1340-1380行）
```python
def get_fallback_indices_data(indices):
    """获取回退的模拟数据"""
    mock_data = {
        'sh000001': {
            'name': '上证指数',
            'current_price': 3525.0,  # 硬编码的固定值
            'change_pct': 0.43,
            'change_amount': 15.2,
            'volume': 410354000000,
            'update_time': datetime.now().strftime('%H:%M:%S')
        },
        # ... 其他指数的硬编码数据
    }
```

## 解决方案

### 1. 立即解决方法
添加了重置重试状态的 API 接口：

```bash
# 重置重试状态
curl http://127.0.0.1:8080/api/indices/reset_retry
```

### 2. 使用步骤

1. **检查当前状态**：
   ```bash
   curl http://127.0.0.1:8080/api/indices/realtime
   ```

2. **如果返回模拟数据，重置重试状态**：
   ```bash
   curl http://127.0.0.1:8080/api/indices/reset_retry
   ```

3. **再次获取数据**：
   ```bash
   curl http://127.0.0.1:8080/api/indices/realtime
   ```

### 3. 长期优化建议

1. **调整重试间隔**：将 `retry_interval` 从 120 秒减少到 30-60 秒
2. **改进错误处理**：区分网络错误和数据错误，只对网络错误启用重试机制
3. **添加监控**：实现重试状态的自动监控和告警
4. **环境配置**：检查云服务器的网络配置和防火墙设置

## 验证方法

### 检查是否使用模拟数据
模拟数据的特征：
- 上证指数固定为 3525.0
- 深证成指固定为 11250.5
- 创业板指固定为 2180.3
- 科创板固定为 850.2

### 检查真实数据
真实数据的特征：
- 数值会根据市场实时变化
- 包含准确的涨跌幅和成交量
- 更新时间反映实际获取时间

## 预防措施

1. **定期重置**：可以设置定时任务定期调用重置接口
2. **监控告警**：监控 API 调用失败率，及时发现问题
3. **备用方案**：考虑使用多个数据源作为备用
4. **环境优化**：优化云服务器的网络配置和 API 访问环境

## 总结

这个问题是由于云服务器环境下 API 调用失败触发重试机制，导致系统返回硬编码的模拟数据。通过添加重置接口和优化重试逻辑，可以有效解决这个问题。建议在部署到生产环境时进一步优化重试机制和错误处理逻辑。