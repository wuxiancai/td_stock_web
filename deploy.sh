#!/bin/bash

# 九转序列选股系统一键部署脚本
# 适用于 Ubuntu Server 22.04
# 作者: 自动生成
# 日期: $(date +%Y-%m-%d)

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "请不要使用root用户运行此脚本！"
        log_info "建议创建普通用户: sudo adduser stock && sudo usermod -aG sudo stock"
        exit 1
    fi
}

# 检查系统版本
check_system() {
    log_info "检查系统版本..."
    if [[ ! -f /etc/os-release ]]; then
        log_error "无法检测系统版本"
        exit 1
    fi
    
    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]] || [[ "$VERSION_ID" != "22.04" ]]; then
        log_warning "检测到系统版本: $PRETTY_NAME"
        log_warning "此脚本专为 Ubuntu 22.04 设计，其他版本可能存在兼容性问题"
        read -p "是否继续？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    log_success "系统检查通过"
}

# 更新系统包
update_system() {
    log_info "更新系统包..."
    sudo apt update
    sudo apt upgrade -y
    log_success "系统包更新完成"
}

# 检查端口占用
check_ports() {
    log_info "检查端口占用..."
    
    # 检查8080端口
    if netstat -tuln | grep -q ":8080 "; then
        log_error "端口8080已被占用，请先停止占用该端口的服务"
        log_info "查看占用进程: sudo lsof -i :8080"
        exit 1
    fi
    
    # 检查80端口（如果要配置Nginx）
    if netstat -tuln | grep -q ":80 "; then
        log_warning "端口80已被占用，Nginx配置可能会失败"
    fi
    
    log_success "端口检查完成"
}

# 安装必要的系统依赖
install_dependencies() {
    log_info "安装系统依赖..."
    
    # 更新包索引
    sudo apt update
    
    # 安装基础依赖，添加错误处理
    local packages=(
        "python3"
        "python3-pip"
        "python3-venv"
        "python3-dev"
        "build-essential"
        "git"
        "curl"
        "wget"
        "unzip"
        "nginx"
        "net-tools"
        "lsof"
    )
    
    for package in "${packages[@]}"; do
        log_info "安装 $package..."
        if ! sudo apt install -y "$package"; then
            log_error "安装 $package 失败"
            exit 1
        fi
    done
    
    # 验证Python安装
    if ! command -v python3 >/dev/null 2>&1; then
        log_error "Python3安装失败"
        exit 1
    fi
    
    # 验证pip安装
    if ! command -v pip3 >/dev/null 2>&1; then
        log_error "pip3安装失败"
        exit 1
    fi
    
    log_success "系统依赖安装完成"
}

# 设置项目目录
setup_project() {
    log_info "设置项目目录..."
    
    # 项目部署路径
    PROJECT_DIR="/home/$USER/td_stock"
    
    # 如果项目目录已存在，询问是否覆盖
    if [[ -d "$PROJECT_DIR" ]]; then
        log_warning "项目目录 $PROJECT_DIR 已存在"
        read -p "是否删除并重新部署？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$PROJECT_DIR"
            log_info "已删除旧的项目目录"
        else
            log_error "部署取消"
            exit 1
        fi
    fi
    
    # 复制项目文件
    cp -r "$(pwd)" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    
    log_success "项目目录设置完成: $PROJECT_DIR"
}

# 创建Python虚拟环境
setup_venv() {
    log_info "创建Python虚拟环境..."
    
    # 显示Python版本信息
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    log_info "检测到Python版本: $PYTHON_VERSION"
    log_info "使用系统Python版本创建虚拟环境"
    
    # 删除旧的虚拟环境（如果存在）
    if [[ -d "venv" ]]; then
        log_info "删除旧的虚拟环境..."
        rm -rf venv
    fi
    
    # 创建虚拟环境
    if ! python3 -m venv venv; then
        log_error "创建虚拟环境失败"
        exit 1
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip，添加超时和重试
    log_info "升级pip..."
    if ! pip install --upgrade pip --timeout 60; then
        log_warning "pip升级失败，尝试使用国内镜像源..."
        pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/ --timeout 60
    fi
    
    # 安装项目依赖
    if [[ -f "requirements.txt" ]]; then
        log_info "安装项目依赖..."
        # 首先尝试默认源
        if ! pip install -r requirements.txt --timeout 120; then
            log_warning "默认源安装失败，尝试使用国内镜像源..."
            if ! pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ --timeout 120; then
                log_error "依赖安装失败，请检查网络连接和requirements.txt文件"
                exit 1
            fi
        fi
    else
        log_warning "未找到requirements.txt，手动安装核心依赖"
        local core_packages=("flask" "tushare" "pandas" "numpy")
        for package in "${core_packages[@]}"; do
            log_info "安装 $package..."
            if ! pip install "$package" --timeout 60; then
                log_warning "默认源安装 $package 失败，尝试国内镜像源..."
                if ! pip install "$package" -i https://pypi.tuna.tsinghua.edu.cn/simple/ --timeout 60; then
                    log_error "安装 $package 失败"
                    exit 1
                fi
            fi
        done
    fi
    
    # 验证关键包是否安装成功
    log_info "验证依赖安装..."
    python3 -c "import flask, tushare, pandas, numpy" 2>/dev/null || {
        log_error "关键依赖验证失败"
        exit 1
    }
    
    log_success "Python虚拟环境创建完成"
}

# 配置环境变量
setup_env() {
    log_info "配置环境变量..."
    
    # 从app.py中提取Tushare Token
    TUSHARE_TOKEN=""
    if [[ -f "app.py" ]]; then
        TUSHARE_TOKEN=$(grep -o "ts.set_token('[^']*')" app.py | sed "s/ts.set_token('\([^']*'\))/\1/" | tr -d "'")
        if [[ -n "$TUSHARE_TOKEN" ]]; then
            log_success "从app.py中提取到Tushare Token: ${TUSHARE_TOKEN:0:10}..."
        else
            log_warning "未能从app.py中提取到Tushare Token"
            TUSHARE_TOKEN="your_tushare_token_here"
        fi
    else
        log_warning "未找到app.py文件"
        TUSHARE_TOKEN="your_tushare_token_here"
    fi
    
    # 生成随机密钥
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    
    # 创建环境配置文件
    cat > .env << EOF
# 九转序列选股系统环境配置
# 生成时间: $(date)

# Flask配置
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=$SECRET_KEY

# 服务器配置
HOST=0.0.0.0
PORT=8080

# Tushare配置
TUSHARE_TOKEN=$TUSHARE_TOKEN

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/var/log/td_stock/app.log

# 安全配置
SESSION_COOKIE_SECURE=False
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
EOF
    
    # 设置环境文件权限
    chmod 600 .env
    
    if [[ "$TUSHARE_TOKEN" != "your_tushare_token_here" ]]; then
        log_success "环境配置文件创建完成，已自动配置Tushare Token"
    else
        log_warning "请编辑 $PROJECT_DIR/.env 文件，填入您的Tushare Token"
    fi
}

# 创建日志目录和配置日志轮转
setup_logs() {
    log_info "创建日志目录..."
    sudo mkdir -p /var/log/td_stock
    sudo chown $USER:$USER /var/log/td_stock
    sudo chmod 755 /var/log/td_stock
    
    # 创建日志轮转配置
    log_info "配置日志轮转..."
    sudo tee /etc/logrotate.d/td-stock > /dev/null << EOF
/var/log/td_stock/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload td-stock.service > /dev/null 2>&1 || true
    endscript
}
EOF
    
    # 测试日志轮转配置
    if sudo logrotate -d /etc/logrotate.d/td-stock >/dev/null 2>&1; then
        log_success "日志轮转配置完成"
    else
        log_warning "日志轮转配置可能有问题，但不影响部署"
    fi
    
    log_success "日志目录创建完成"
}

# 创建systemd服务
setup_systemd() {
    log_info "创建systemd服务..."
    
    # 确保日志目录存在且权限正确
    sudo mkdir -p /var/log/td_stock
    sudo chown $USER:$USER /var/log/td_stock
    sudo chmod 755 /var/log/td_stock
    
    # 创建服务文件
    sudo tee /etc/systemd/system/td-stock.service > /dev/null << EOF
[Unit]
Description=九转序列选股系统
Documentation=https://github.com/your-repo/td_stock
After=network.target network-online.target
Wants=network-online.target
Requires=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$PROJECT_DIR/.env
# 启动前检查
ExecStartPre=/bin/test -f $PROJECT_DIR/app.py
ExecStartPre=/bin/test -f $PROJECT_DIR/.env
ExecStartPre=$PROJECT_DIR/venv/bin/python -c "import flask, tushare, pandas, numpy, schedule"
ExecStart=$PROJECT_DIR/venv/bin/python app.py
ExecReload=/bin/kill -HUP \$MAINPID
ExecStop=/bin/kill -TERM \$MAINPID
TimeoutStartSec=120
TimeoutStopSec=30
Restart=always
RestartSec=15
StartLimitInterval=300
StartLimitBurst=3

# 日志配置
StandardOutput=append:/var/log/td_stock/app.log
StandardError=append:/var/log/td_stock/error.log
SyslogIdentifier=td-stock

# 安全配置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/td_stock $PROJECT_DIR
ReadOnlyPaths=/etc

# 资源限制
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF
    
    # 验证服务文件语法
    if ! sudo systemd-analyze verify /etc/systemd/system/td-stock.service; then
        log_error "systemd服务文件语法错误"
        exit 1
    fi
    
    # 重新加载systemd配置
    sudo systemctl daemon-reload
    
    # 启用服务
    if ! sudo systemctl enable td-stock.service; then
        log_error "启用systemd服务失败"
        exit 1
    fi
    
    log_success "systemd服务创建完成"
}

# 配置Nginx反向代理（可选）
setup_nginx() {
    log_info "是否配置Nginx反向代理？"
    read -p "配置Nginx可以提供更好的性能和安全性 (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "配置Nginx..."
        
        # 创建Nginx配置
        sudo tee /etc/nginx/sites-available/td-stock << EOF
server {
    listen 80;
    server_name _;
    
    # 安全头
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # 静态文件缓存
    location /static {
        alias $PROJECT_DIR/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # 反向代理到Flask应用
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 日志
    access_log /var/log/nginx/td-stock.access.log;
    error_log /var/log/nginx/td-stock.error.log;
}
EOF
        
        # 启用站点
        sudo ln -sf /etc/nginx/sites-available/td-stock /etc/nginx/sites-enabled/
        
        # 删除默认站点
        sudo rm -f /etc/nginx/sites-enabled/default
        
        # 测试Nginx配置
        sudo nginx -t
        
        # 重启Nginx
        sudo systemctl restart nginx
        sudo systemctl enable nginx
        
        log_success "Nginx配置完成"
    else
        log_info "跳过Nginx配置"
    fi
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."
    
    # 检查ufw是否安装
    if command -v ufw >/dev/null 2>&1; then
        # 检查ufw状态
        local ufw_status=$(sudo ufw status | head -1)
        
        if [[ "$ufw_status" == *"inactive"* ]]; then
            log_info "启用ufw防火墙..."
            sudo ufw --force enable
        fi
        
        # 允许SSH（防止锁定）
        sudo ufw allow ssh
        sudo ufw allow 22/tcp
        
        # 允许HTTP和HTTPS
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        
        # 如果没有配置Nginx，开放8080端口
        if [[ ! -f /etc/nginx/sites-enabled/td-stock ]]; then
            sudo ufw allow 8080/tcp
            log_info "已开放8080端口用于直接访问应用"
        fi
        
        # 显示防火墙状态
        sudo ufw status numbered
        
        log_success "防火墙配置完成"
    else
        log_warning "未检测到ufw防火墙"
        log_info "建议安装ufw: sudo apt install ufw"
        log_info "手动配置防火墙规则以保护服务器安全"
    fi
}

# 验证配置文件
validate_config() {
    log_info "验证配置文件..."
    
    # 检查app.py是否存在
    if [[ ! -f "app.py" ]]; then
        log_error "未找到app.py文件"
        exit 1
    fi
    
    # 检查.env文件
    if [[ ! -f ".env" ]]; then
        log_error "未找到.env配置文件"
        exit 1
    fi
    
    # 测试Python应用是否可以正常导入
    log_info "测试应用导入..."
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # 创建测试脚本
    cat > test_import.py << 'EOF'
import sys
try:
    import app
    print("应用导入成功")
    sys.exit(0)
except Exception as e:
    print(f"应用导入失败: {e}")
    sys.exit(1)
EOF
    
    if python3 test_import.py; then
        log_success "应用配置验证通过"
    else
        log_error "应用配置验证失败"
        rm -f test_import.py
        exit 1
    fi
    
    rm -f test_import.py
}

# 启动服务
start_service() {
    log_info "启动服务..."
    
    # 验证配置
    validate_config
    
    # 启动应用服务
    if ! sudo systemctl start td-stock.service; then
        log_error "服务启动命令执行失败"
        exit 1
    fi
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 5
    
    # 检查服务状态
    local retry_count=0
    local max_retries=10
    
    while [[ $retry_count -lt $max_retries ]]; do
        if sudo systemctl is-active --quiet td-stock.service; then
            log_success "应用服务启动成功"
            
            # 测试HTTP连接
            log_info "测试HTTP连接..."
            sleep 2
            if curl -f http://localhost:8080 >/dev/null 2>&1; then
                log_success "HTTP服务响应正常"
            else
                log_warning "HTTP服务暂时无响应，可能仍在初始化中"
            fi
            return 0
        fi
        
        log_info "服务启动中... ($((retry_count + 1))/$max_retries)"
        sleep 2
        ((retry_count++))
    done
    
    log_error "应用服务启动失败"
    log_info "查看服务状态: sudo systemctl status td-stock.service"
    log_info "查看详细日志: sudo journalctl -u td-stock.service -f"
    log_info "查看应用日志: tail -f /var/log/td_stock/app.log"
    exit 1
}

# 显示部署信息
show_info() {
    log_success "部署完成！"
    echo
    echo "=== 部署信息 ==="
    echo "项目目录: $PROJECT_DIR"
    echo "虚拟环境: $PROJECT_DIR/venv"
    echo "配置文件: $PROJECT_DIR/.env"
    echo "日志目录: /var/log/td_stock/"
    echo
    echo "=== 服务管理 ==="
    echo "启动服务: sudo systemctl start td-stock"
    echo "停止服务: sudo systemctl stop td-stock"
    echo "重启服务: sudo systemctl restart td-stock"
    echo "查看状态: sudo systemctl status td-stock"
    echo "查看日志: sudo journalctl -u td-stock -f"
    echo
    echo "=== 访问地址 ==="
    if [[ -f /etc/nginx/sites-enabled/td-stock ]]; then
        echo "HTTP: http://$(hostname -I | awk '{print $1}')"
    else
        echo "HTTP: http://$(hostname -I | awk '{print $1}'):8080"
    fi
    echo
    echo "=== 重要提醒 ==="
    if [[ "$TUSHARE_TOKEN" == "your_tushare_token_here" ]]; then
        log_warning "请务必编辑 $PROJECT_DIR/.env 文件，填入您的Tushare Token！"
        log_warning "修改配置后需要重启服务: sudo systemctl restart td-stock"
    else
        log_success "Tushare Token已自动配置完成！"
        log_info "如需修改配置，请编辑 $PROJECT_DIR/.env 文件"
        log_info "修改配置后需要重启服务: sudo systemctl restart td-stock"
    fi
    
    echo
    echo "=== 故障排除 ==="
    echo "如果遇到问题，请按以下步骤排查："
    echo "1. 检查服务状态: sudo systemctl status td-stock"
    echo "2. 查看服务日志: sudo journalctl -u td-stock -f"
    echo "3. 查看应用日志: tail -f /var/log/td_stock/app.log"
    echo "4. 查看错误日志: tail -f /var/log/td_stock/error.log"
    echo "5. 测试端口连通: curl -I http://localhost:8080"
    echo "6. 检查防火墙: sudo ufw status"
    echo "7. 重启服务: sudo systemctl restart td-stock"
    echo
    echo "=== 性能优化建议 ==="
    echo "1. 定期清理日志: sudo logrotate -f /etc/logrotate.d/td-stock"
    echo "2. 监控系统资源: htop 或 top"
    echo "3. 备份配置文件: cp $PROJECT_DIR/.env $PROJECT_DIR/.env.backup"
    echo "4. 更新依赖包: cd $PROJECT_DIR && source venv/bin/activate && pip list --outdated"
}

# 清理函数（在出错时调用）
cleanup_on_error() {
    log_error "部署过程中出现错误，正在清理..."
    
    # 停止服务（如果已启动）
    if sudo systemctl is-active --quiet td-stock.service 2>/dev/null; then
        sudo systemctl stop td-stock.service
    fi
    
    # 禁用服务（如果已启用）
    if sudo systemctl is-enabled --quiet td-stock.service 2>/dev/null; then
        sudo systemctl disable td-stock.service
    fi
    
    # 删除systemd服务文件
    if [[ -f /etc/systemd/system/td-stock.service ]]; then
        sudo rm -f /etc/systemd/system/td-stock.service
        sudo systemctl daemon-reload
    fi
    
    log_info "清理完成，您可以重新运行部署脚本"
}

# 设置错误处理
trap cleanup_on_error ERR

# 主函数
main() {
    echo "=== 九转序列选股系统一键部署脚本 ==="
    echo "适用于 Ubuntu Server 22.04"
    echo "版本: 2.0"
    echo "更新时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo
    
    # 预检查
    check_root
    check_system
    check_ports
    
    log_info "开始部署..."
    
    # 部署步骤
    update_system
    install_dependencies
    setup_project
    setup_venv
    setup_env
    setup_logs
    setup_systemd
    setup_nginx
    setup_firewall
    start_service
    show_info
    
    # 取消错误处理陷阱
    trap - ERR
    
    log_success "部署完成！请按照上述信息配置和使用系统。"
    log_info "建议重启系统以确保所有配置生效: sudo reboot"
}

# 执行主函数
main "$@"