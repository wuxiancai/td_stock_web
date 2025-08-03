# 缓存部署说明

## 问题描述

在将项目推送到Git并远程部署时，发现"红3-6筛选"页面的净流入额数据显示为0，这是因为`cache`目录被`.gitignore`忽略，导致远程服务器缺少必要的缓存数据。

## 问题根源

1. **cache目录被完全忽略**：`.gitignore`文件中的`cache/`规则导致整个缓存目录不被推送到Git仓库
2. **净流入数据依赖缓存**：净流入数据通过Tushare API获取并缓存，远程部署时缺少这些缓存数据
3. **API调用限制**：Tushare API有调用频率限制，新部署的服务器可能无法立即获取所有数据

## 解决方案

### 1. 修改.gitignore策略

已将`.gitignore`中的缓存规则从：
```
# Cache
cache/
```

修改为：
```
# Cache - 保留目录结构，忽略数据文件
cache/*.json
cache/*.json.backup
cache/intraday/*.json
```

这样可以：
- ✅ 保留cache目录结构
- ✅ 忽略具体的缓存数据文件（避免推送大量临时数据）
- ✅ 确保远程部署时有正确的目录结构

### 2. 添加.gitkeep文件

创建了以下文件确保目录结构被保留：
- `cache/.gitkeep`
- `cache/intraday/.gitkeep`

### 3. 创建缓存初始化脚本

创建了`init_cache.py`脚本，用于：
- 自动创建必要的缓存目录
- 检查目录权限
- 确保缓存系统正常工作

### 4. 更新部署脚本

在`deploy.sh`中添加了`init_cache()`函数，确保部署时：
- 自动创建缓存目录结构
- 运行缓存初始化脚本
- 设置正确的目录权限

## 部署步骤

### 重新部署到远程服务器

1. **提交更改到Git**：
   ```bash
   git add .
   git commit -m "修复缓存目录部署问题"
   git push origin main
   ```

2. **在远程服务器拉取更新**：
   ```bash
   cd /path/to/your/project
   git pull origin main
   ```

3. **运行缓存初始化**：
   ```bash
   python3 init_cache.py
   ```

4. **重启服务**：
   ```bash
   # 如果使用systemd
   sudo systemctl restart td-stock
   
   # 或者手动重启
   python3 app.py
   ```

### 验证修复

1. **检查缓存目录**：
   ```bash
   ls -la cache/
   ls -la cache/intraday/
   ```

2. **访问红3-6筛选页面**：
   - 等待几分钟让系统获取数据
   - 检查净流入额是否正常显示

3. **查看日志**：
   ```bash
   tail -f logs/app.log
   ```

## 注意事项

1. **首次部署后的数据获取**：
   - 远程服务器首次运行时需要从Tushare API获取数据
   - 由于API调用限制，可能需要等待一段时间才能看到完整数据
   - 建议在低峰期进行部署

2. **API Token配置**：
   - 确保远程服务器的Tushare Token配置正确
   - 检查Token的权限和积分是否足够

3. **监控缓存状态**：
   - 定期检查缓存文件的更新时间
   - 监控API调用是否成功

## 故障排除

### 如果净流入额仍显示为0

1. **检查API调用**：
   ```bash
   curl "http://localhost:5000/api/stock/000858.SZ/moneyflow"
   ```

2. **检查缓存文件**：
   ```bash
   ls -la cache/
   cat cache/realtime_trading_data_cache.json
   ```

3. **手动触发数据更新**：
   - 访问管理页面的"更新资金流向"按钮
   - 或者重启服务让系统重新获取数据

### 权限问题

如果遇到权限问题：
```bash
sudo chown -R $USER:$USER cache/
sudo chmod -R 755 cache/
```

## 总结

通过以上修改，cache目录的部署问题已得到解决：
- ✅ 目录结构会被正确部署到远程服务器
- ✅ 缓存系统可以正常工作
- ✅ 净流入数据可以正常显示
- ✅ 避免了推送大量临时缓存文件到Git仓库

建议在每次部署后验证缓存功能是否正常工作。