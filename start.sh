#!/bin/bash

# TD Stock Web Application 启动脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}启动 TD Stock Web Application...${NC}"

# 检查虚拟环境
if [[ ! -d "venv" ]]; then
    echo -e "${RED}错误: 虚拟环境不存在，请先运行部署脚本${NC}"
    exit 1
fi

# 检查.env文件
if [[ ! -f ".env" ]]; then
    echo -e "${YELLOW}警告: .env文件不存在，使用默认配置${NC}"
fi

# 激活虚拟环境
source venv/bin/activate

# 检查依赖
if ! python -c "import flask" 2>/dev/null; then
    echo -e "${RED}错误: Flask未安装，请先运行部署脚本安装依赖${NC}"
    exit 1
fi

# 创建必要的目录
mkdir -p logs cache data

# 设置环境变量
export FLASK_ENV=${FLASK_ENV:-production}
export FLASK_DEBUG=${FLASK_DEBUG:-False}
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8080}

echo -e "${GREEN}配置信息:${NC}"
echo "- 环境: $FLASK_ENV"
echo "- 调试模式: $FLASK_DEBUG"
echo "- 监听地址: $HOST:$PORT"
echo "- 工作目录: $SCRIPT_DIR"

# 启动应用
echo -e "${GREEN}启动Flask应用...${NC}"
python app.py