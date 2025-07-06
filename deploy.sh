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

# 安装必要的系统依赖
install_dependencies() {
    log_info "安装系统依赖..."
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        git \
        curl \
        wget \
        unzip \
        supervisor \
        nginx
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
    
    # 检查Python版本
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    log_info "检测到Python版本: $PYTHON_VERSION"
    
    if [[ "$PYTHON_VERSION" < "3.8" ]]; then
        log_error "Python版本过低，需要3.8或更高版本"
        exit 1
    fi
    
    # 创建虚拟环境
    python3 -m venv venv
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装项目依赖
    if [[ -f "requirements.txt" ]]; then
        log_info "安装项目依赖..."
        pip install -r requirements.txt
    else
        log_warning "未找到requirements.txt，手动安装依赖"
        pip install flask tushare pandas numpy
    fi
    
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
    
    # 创建环境配置文件
    cat > .env << EOF
# 九转序列选股系统环境配置

# Flask配置
FLASK_ENV=production
FLASK_DEBUG=False

# 服务器配置
HOST=0.0.0.0
PORT=8080

# Tushare配置
TUSHARE_TOKEN=$TUSHARE_TOKEN

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/var/log/td_stock/app.log
EOF
    
    if [[ "$TUSHARE_TOKEN" != "your_tushare_token_here" ]]; then
        log_success "环境配置文件创建完成，已自动配置Tushare Token"
    else
        log_warning "请编辑 $PROJECT_DIR/.env 文件，填入您的Tushare Token"
    fi
}

# 创建日志目录
setup_logs() {
    log_info "创建日志目录..."
    sudo mkdir -p /var/log/td_stock
    sudo chown $USER:$USER /var/log/td_stock
    log_success "日志目录创建完成"
}

# 创建systemd服务
setup_systemd() {
    log_info "创建systemd服务..."
    
    # 创建服务文件
    sudo tee /etc/systemd/system/td-stock.service > /dev/null << EOF
[Unit]
Description=九转序列选股系统
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python app.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10

# 日志配置
StandardOutput=append:/var/log/td_stock/app.log
StandardError=append:/var/log/td_stock/error.log

# 安全配置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/log/td_stock $PROJECT_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载systemd配置
    sudo systemctl daemon-reload
    
    # 启用服务
    sudo systemctl enable td-stock.service
    
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
        sudo ufw --force enable
        sudo ufw allow ssh
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        
        # 如果没有配置Nginx，开放8080端口
        if [[ ! -f /etc/nginx/sites-enabled/td-stock ]]; then
            sudo ufw allow 8080/tcp
        fi
        
        log_success "防火墙配置完成"
    else
        log_warning "未检测到ufw防火墙，请手动配置防火墙规则"
    fi
}

# 启动服务
start_service() {
    log_info "启动服务..."
    
    # 启动应用服务
    sudo systemctl start td-stock.service
    
    # 检查服务状态
    sleep 3
    if sudo systemctl is-active --quiet td-stock.service; then
        log_success "应用服务启动成功"
    else
        log_error "应用服务启动失败"
        log_info "查看日志: sudo journalctl -u td-stock.service -f"
        exit 1
    fi
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
}

# 主函数
main() {
    echo "=== 九转序列选股系统一键部署脚本 ==="
    echo "适用于 Ubuntu Server 22.04"
    echo
    
    check_root
    check_system
    
    log_info "开始部署..."
    
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
    
    log_success "部署完成！请按照上述信息配置和使用系统。"
}

# 执行主函数
main "$@"