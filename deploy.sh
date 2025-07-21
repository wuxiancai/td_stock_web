#!/bin/bash

# 股票数据系统部署脚本
# 支持开发、测试、生产环境的自动化部署

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

# 默认配置
ENVIRONMENT="development"
PROJECT_DIR="/opt/td_stock_web"
SERVICE_NAME="td-stock"
PYTHON_VERSION="3.9"
BACKUP_DIR="/var/backups/td_stock"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--directory)
            PROJECT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  -e, --environment    部署环境 (development|testing|production)"
            echo "  -d, --directory      项目目录"
            echo "  -h, --help          显示帮助信息"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

log_info "开始部署股票数据系统..."
log_info "环境: $ENVIRONMENT"
log_info "项目目录: $PROJECT_DIR"

# 检查系统要求
check_requirements() {
    log_info "检查系统要求..."
    
    # 检查Python版本
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    PYTHON_VER=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [[ $(echo "$PYTHON_VER < 3.8" | bc -l) -eq 1 ]]; then
        log_error "Python版本过低，需要3.8+，当前版本: $PYTHON_VER"
        exit 1
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 未安装"
        exit 1
    fi
    
    # 检查systemd (生产环境)
    if [[ "$ENVIRONMENT" == "production" ]] && ! command -v systemctl &> /dev/null; then
        log_error "systemd 未安装，无法创建系统服务"
        exit 1
    fi
    
    log_success "系统要求检查通过"
}

# 创建项目目录结构
create_directories() {
    log_info "创建目录结构..."
    
    sudo mkdir -p "$PROJECT_DIR"
    sudo mkdir -p "$PROJECT_DIR/logs"
    sudo mkdir -p "$PROJECT_DIR/data"
    sudo mkdir -p "$PROJECT_DIR/cache"
    sudo mkdir -p "$PROJECT_DIR/config"
    sudo mkdir -p "$BACKUP_DIR"
    
    # 设置权限
    sudo chown -R $USER:$USER "$PROJECT_DIR"
    sudo chmod -R 755 "$PROJECT_DIR"
    
    log_success "目录结构创建完成"
}

# 安装Python依赖
install_dependencies() {
    log_info "安装Python依赖..."
    
    cd "$PROJECT_DIR"
    
    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log_success "虚拟环境创建完成"
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装依赖
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_success "依赖安装完成"
    else
        log_warning "requirements.txt 不存在，跳过依赖安装"
    fi
}

# 配置环境变量
setup_environment() {
    log_info "配置环境变量..."
    
    ENV_FILE="$PROJECT_DIR/.env"
    
    if [[ ! -f "$ENV_FILE" ]]; then
        cat > "$ENV_FILE" << EOF
# 环境配置
ENVIRONMENT=$ENVIRONMENT
DEBUG=$([ "$ENVIRONMENT" == "development" ] && echo "true" || echo "false")

# 数据库配置
DATABASE_PATH=$PROJECT_DIR/data/stock_data.db

# 缓存配置
CACHE_DIRECTORY=$PROJECT_DIR/cache

# 日志配置
LOG_FILE_PATH=$PROJECT_DIR/logs/app.log

# API配置 (请设置您的Tushare Token)
# TUSHARE_TOKEN=your_token_here

# 安全配置
SECRET_KEY=$(openssl rand -hex 32)
EOF
        log_success "环境变量文件创建完成"
    else
        log_info "环境变量文件已存在，跳过创建"
    fi
}

# 初始化数据库
init_database() {
    log_info "初始化数据库..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # 运行数据库初始化脚本
    if [[ -f "init_db.py" ]]; then
        python init_db.py
        log_success "数据库初始化完成"
    else
        log_warning "数据库初始化脚本不存在"
    fi
}

# 创建系统服务 (生产环境)
create_service() {
    if [[ "$ENVIRONMENT" != "production" ]]; then
        return
    fi
    
    log_info "创建系统服务..."
    
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=TD Stock Web Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python app.py
Restart=always
RestartSec=10

# 环境变量
EnvironmentFile=$PROJECT_DIR/.env

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# 安全设置
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$PROJECT_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载systemd配置
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    
    log_success "系统服务创建完成"
}

# 配置Nginx (生产环境)
setup_nginx() {
    if [[ "$ENVIRONMENT" != "production" ]]; then
        return
    fi
    
    log_info "配置Nginx..."
    
    if ! command -v nginx &> /dev/null; then
        log_warning "Nginx 未安装，跳过配置"
        return
    fi
    
    NGINX_CONFIG="/etc/nginx/sites-available/$SERVICE_NAME"
    
    sudo tee "$NGINX_CONFIG" > /dev/null << EOF
server {
    listen 80;
    server_name your-domain.com;  # 请修改为您的域名
    
    # 静态文件
    location /static/ {
        alias $PROJECT_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # 代理到Flask应用
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOF
    
    # 启用站点
    sudo ln -sf "$NGINX_CONFIG" "/etc/nginx/sites-enabled/"
    
    # 测试配置
    if sudo nginx -t; then
        sudo systemctl reload nginx
        log_success "Nginx配置完成"
    else
        log_error "Nginx配置测试失败"
    fi
}

# 创建备份脚本
create_backup_script() {
    log_info "创建备份脚本..."
    
    BACKUP_SCRIPT="$PROJECT_DIR/backup.sh"
    
    cat > "$BACKUP_SCRIPT" << 'EOF'
#!/bin/bash

# 股票数据系统备份脚本

BACKUP_DIR="/var/backups/td_stock"
PROJECT_DIR="/opt/td_stock_web"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.tar.gz"

# 创建备份
echo "开始备份..."
tar -czf "$BACKUP_FILE" \
    --exclude="$PROJECT_DIR/venv" \
    --exclude="$PROJECT_DIR/cache" \
    --exclude="$PROJECT_DIR/logs/*.log" \
    "$PROJECT_DIR"

echo "备份完成: $BACKUP_FILE"

# 清理旧备份 (保留7天)
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete
echo "旧备份清理完成"
EOF
    
    chmod +x "$BACKUP_SCRIPT"
    
    # 添加到crontab (生产环境)
    if [[ "$ENVIRONMENT" == "production" ]]; then
        (crontab -l 2>/dev/null; echo "0 2 * * * $BACKUP_SCRIPT") | crontab -
        log_success "备份脚本创建完成，已添加到定时任务"
    else
        log_success "备份脚本创建完成"
    fi
}

# 启动服务
start_service() {
    log_info "启动服务..."
    
    cd "$PROJECT_DIR"
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        sudo systemctl start "$SERVICE_NAME"
        sudo systemctl status "$SERVICE_NAME" --no-pager
        log_success "生产服务启动完成"
    else
        log_info "开发环境，请手动启动: cd $PROJECT_DIR && source venv/bin/activate && python app.py"
    fi
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 等待服务启动
    sleep 5
    
    # 检查端口
    if netstat -tuln | grep -q ":8080 "; then
        log_success "服务端口检查通过"
    else
        log_warning "服务端口8080未监听"
    fi
    
    # 检查HTTP响应
    if command -v curl &> /dev/null; then
        if curl -f -s http://localhost:8080/ > /dev/null; then
            log_success "HTTP响应检查通过"
        else
            log_warning "HTTP响应检查失败"
        fi
    fi
}

# 主部署流程
main() {
    log_info "========================================="
    log_info "股票数据系统自动化部署开始"
    log_info "========================================="
    
    check_requirements
    create_directories
    install_dependencies
    setup_environment
    init_database
    create_service
    setup_nginx
    create_backup_script
    start_service
    health_check
    
    log_success "========================================="
    log_success "部署完成！"
    log_success "========================================="
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log_info "生产环境部署完成，服务已启动"
        log_info "请确保："
        log_info "1. 设置Tushare Token: 编辑 $PROJECT_DIR/.env"
        log_info "2. 配置域名: 编辑 /etc/nginx/sites-available/$SERVICE_NAME"
        log_info "3. 设置SSL证书 (推荐使用Let's Encrypt)"
    else
        log_info "开发环境部署完成"
        log_info "启动命令: cd $PROJECT_DIR && source venv/bin/activate && python app.py"
    fi
}

# 执行主流程
main "$@"