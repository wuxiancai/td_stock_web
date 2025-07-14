# 云服务器 AkShare 导入问题修复指南

## 问题描述
云服务器上使用 `systemctl start td-stock.service` 启动服务时出现 `name 'ak' is not defined` 错误。

## 问题原因
当前 `td-stock.service` 文件使用系统 Python (`/usr/bin/python3`)，但 AkShare 可能没有安装在系统 Python 环境中，而是安装在虚拟环境中。

## 解决方案

### 方案1：使用虚拟环境（推荐）

1. 在云服务器上创建虚拟环境：
```bash
cd /home/ubuntu/td_stock_web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. 修改 `td-stock.service` 文件：
```ini
[Unit]
Description=TD Stock Web Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/td_stock_web
ExecStart=/home/ubuntu/td_stock_web/venv/bin/python app.py
Environment=PATH=/home/ubuntu/td_stock_web/venv/bin
Restart=always

[Install]
WantedBy=multi-user.target
```

3. 重新加载并启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl restart td-stock.service
```

### 方案2：在系统 Python 中安装依赖

1. 在云服务器上安装依赖到系统 Python：
```bash
cd /home/ubuntu/td_stock_web
sudo pip3 install -r requirements.txt
```

2. 验证 AkShare 安装：
```bash
python3 -c "import akshare as ak; print('AkShare 安装成功')"
```

### 方案3：使用启动脚本

1. 创建启动脚本 `start.sh`：
```bash
#!/bin/bash
cd /home/ubuntu/td_stock_web
source venv/bin/activate
python app.py
```

2. 修改 `td-stock.service` 文件：
```ini
[Unit]
Description=TD Stock Web Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/td_stock_web
ExecStart=/bin/bash /home/ubuntu/td_stock_web/start.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

## 验证修复

1. 检查服务状态：
```bash
sudo systemctl status td-stock.service
```

2. 查看服务日志：
```bash
sudo journalctl -u td-stock.service -f
```

3. 测试 AkShare 导入：
```bash
# 在虚拟环境中测试
source /home/ubuntu/td_stock_web/venv/bin/activate
python3 -c "import akshare as ak; print('AkShare 导入成功')"
```

## 代码修复

已对以下文件进行了修复，添加了 AkShare 导入失败的处理：

1. `app.py` - 在所有直接使用 `ak.` 的地方添加了可用性检查
2. `app_indices_new.py` - 修复了指数数据获取中的 AkShare 调用
3. `test_akshare_spot.py` - 添加了导入失败处理

这些修复确保即使 AkShare 导入失败，程序也不会崩溃，而是优雅地处理错误。

## 注意事项

- 推荐使用方案1（虚拟环境），这样可以避免系统 Python 环境污染
- 确保云服务器上的 Python 版本与本地开发环境一致
- 定期更新依赖包版本以确保兼容性