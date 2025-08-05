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
PROJECT_DIR="$HOME/td_stock_web"
SERVICE_NAME="td-stock-web"
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
    PYTHON_MAJOR=$(echo $PYTHON_VER | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VER | cut -d'.' -f2)
    
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 8 ]]; then
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
    
    # 检查必要的系统工具
    if ! command -v openssl &> /dev/null; then
        log_error "openssl 未安装，无法生成安全密钥"
        exit 1
    fi
    
    if ! command -v netstat &> /dev/null && ! command -v ss &> /dev/null; then
        log_warning "netstat 和 ss 都未安装，健康检查功能可能受限"
    fi
    
    log_success "系统要求检查通过"
}

# 创建项目目录结构
create_directories() {
    log_info "创建目录结构..."
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        # 生产环境使用sudo创建目录
        sudo mkdir -p "$PROJECT_DIR"
        sudo mkdir -p "$PROJECT_DIR/logs"
        sudo mkdir -p "$PROJECT_DIR/data"
        sudo mkdir -p "$PROJECT_DIR/cache"
        sudo mkdir -p "$PROJECT_DIR/config"
        sudo mkdir -p "$BACKUP_DIR"
        
        # 设置权限
        sudo chown -R $USER:staff "$PROJECT_DIR"
        sudo chmod -R 755 "$PROJECT_DIR"
    else
        # 开发和测试环境直接创建目录
        mkdir -p "$PROJECT_DIR"
        mkdir -p "$PROJECT_DIR/logs"
        mkdir -p "$PROJECT_DIR/data"
        mkdir -p "$PROJECT_DIR/cache"
        mkdir -p "$PROJECT_DIR/config"
        mkdir -p "$BACKUP_DIR" 2>/dev/null || log_warning "无法创建备份目录 $BACKUP_DIR，跳过"
        
        # 设置权限
        chmod -R 755 "$PROJECT_DIR"
    fi
    
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
FLASK_ENV=$ENVIRONMENT
FLASK_DEBUG=$([ "$ENVIRONMENT" == "development" ] && echo "true" || echo "false")

# 服务器配置
HOST=0.0.0.0
PORT=8080

# 数据库配置
DATABASE_PATH=$PROJECT_DIR/data/stock_data.db

# 缓存配置
CACHE_DIRECTORY=$PROJECT_DIR/cache

# 日志配置
LOG_FILE_PATH=$PROJECT_DIR/logs/app.log
LOG_LEVEL=INFO

# API配置
TUSHARE_TOKEN=68a7f380e45182b216eb63a9666c277ee96e68e3754476976adc5019

# 安全配置
SECRET_KEY=$(openssl rand -hex 32)

# 性能配置
MAX_CONNECTIONS=1000
REQUEST_TIMEOUT=60
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
    server_name wuxiancai.win www.wuxiancai.win;
    
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
        # 停止可能正在运行的服务
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        
        # 启动服务
        sudo systemctl start "$SERVICE_NAME"
        
        # 检查服务状态
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            log_success "系统服务 $SERVICE_NAME 启动成功"
            sudo systemctl status "$SERVICE_NAME" --no-pager
        else
            log_error "系统服务 $SERVICE_NAME 启动失败"
            sudo systemctl status "$SERVICE_NAME" --no-pager
            exit 1
        fi
    else
        # 开发和测试环境也自动启动服务
        log_info "非生产环境，启动开发服务器..."
        
        # 检查是否有进程在使用8080端口
        if netstat -tuln 2>/dev/null | grep -q ":8080 " || ss -tuln 2>/dev/null | grep -q ":8080 "; then
            log_warning "端口8080已被占用，尝试停止现有进程..."
            pkill -f "python.*app.py" 2>/dev/null || true
            sleep 2
        fi
        
        # 激活虚拟环境并启动应用
        source venv/bin/activate
        nohup python app.py > logs/app.log 2>&1 &
        APP_PID=$!
        
        # 等待服务启动
        sleep 3
        
        # 检查进程是否还在运行
        if kill -0 $APP_PID 2>/dev/null; then
            log_success "开发服务器启动成功 (PID: $APP_PID)"
            echo $APP_PID > "$PROJECT_DIR/app.pid"
        else
            log_error "开发服务器启动失败"
            exit 1
        fi
    fi
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 等待服务启动
    sleep 5
    
    # 检查端口
    PORT_CHECK=false
    if command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":8080 "; then
            PORT_CHECK=true
        fi
    elif command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":8080 "; then
            PORT_CHECK=true
        fi
    fi
    
    if $PORT_CHECK; then
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
        log_info "生产环境部署完成，系统服务 $SERVICE_NAME 已启动"
        log_info "配置信息："
        log_info "1. ✅ Tushare Token: 已预设"
        log_info "2. ✅ 域名配置: wuxiancai.win"
        log_info "3. ✅ 系统服务: $SERVICE_NAME"
        log_info "4. 🔧 建议设置SSL证书 (推荐使用Let's Encrypt)"
        log_info ""
        log_info "服务管理命令："
        log_info "- 启动服务: sudo systemctl start $SERVICE_NAME"
        log_info "- 停止服务: sudo systemctl stop $SERVICE_NAME"
        log_info "- 重启服务: sudo systemctl restart $SERVICE_NAME"
        log_info "- 查看状态: sudo systemctl status $SERVICE_NAME"
        log_info "- 查看日志: sudo journalctl -u $SERVICE_NAME -f"
        log_info ""
        log_info "访问地址："
        log_info "- HTTP: http://wuxiancai.win"
        log_info "- 直接IP: http://$(curl -s ifconfig.me 2>/dev/null || echo 'localhost'):80"
        log_info "- 本地测试: http://localhost:8080"
        log_info ""
        log_info "SSL证书配置命令："
        log_info "sudo certbot --nginx -d wuxiancai.win -d www.wuxiancai.win"
    else
        log_info "$ENVIRONMENT 环境部署完成，开发服务器已启动"
        log_info "配置信息："
        log_info "1. ✅ Tushare Token: 已预设"
        log_info "2. ✅ 服务端口: 8080"
        log_info "3. ✅ 进程PID: $(cat $PROJECT_DIR/app.pid 2>/dev/null || echo '未知')"
        log_info ""
        log_info "访问地址："
        log_info "- 本地访问: http://localhost:8080"
        log_info "- 网络访问: http://$(curl -s ifconfig.me 2>/dev/null || echo 'localhost'):8080"
        log_info ""
        log_info "服务管理："
        log_info "- 停止服务: kill \$(cat $PROJECT_DIR/app.pid)"
        log_info "- 查看日志: tail -f $PROJECT_DIR/logs/app.log"
        log_info "- 手动启动: cd $PROJECT_DIR && source venv/bin/activate && python app.py"
    fi
}

# 执行主流程
main "$@"