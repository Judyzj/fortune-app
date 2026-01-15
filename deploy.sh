#!/bin/bash

# Fortune App 快速部署脚本
# 用于在虚拟机上快速部署后端服务

set -e

echo "🚀 开始部署 Fortune App..."

# 检查是否在正确的目录
if [ ! -f "main.py" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 1. 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "📦 安装 Python 3..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
fi

# 2. 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 3. 激活虚拟环境并安装依赖
echo "📦 安装依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，创建模板..."
    cat > .env << EOF
COMPASS_API_KEY=你的compass_api_key
ALLOWED_ORIGINS=https://你的域名.com
EOF
    echo "✅ 已创建 .env 文件，请编辑并填入正确的值"
    echo "   然后运行: source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000"
    exit 0
fi

# 5. 检查服务是否已在运行
if systemctl is-active --quiet fortune-app 2>/dev/null; then
    echo "🔄 重启服务..."
    sudo systemctl restart fortune-app
else
    # 6. 创建 systemd 服务
    echo "📝 创建 systemd 服务..."
    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)
    
    sudo tee /etc/systemd/system/fortune-app.service > /dev/null << EOF
[Unit]
Description=Fortune App Backend
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin"
ExecStart=$CURRENT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # 7. 启动服务
    echo "🚀 启动服务..."
    sudo systemctl daemon-reload
    sudo systemctl enable fortune-app
    sudo systemctl start fortune-app
fi

# 8. 检查状态
echo "📊 检查服务状态..."
sleep 2
sudo systemctl status fortune-app --no-pager

echo ""
echo "✅ 部署完成！"
echo "📍 服务地址: http://$(hostname -I | awk '{print $1}'):8000"
echo "🔍 健康检查: http://$(hostname -I | awk '{print $1}'):8000/health"
echo ""
echo "📝 管理命令:"
echo "   查看状态: sudo systemctl status fortune-app"
echo "   查看日志: sudo journalctl -u fortune-app -f"
echo "   重启服务: sudo systemctl restart fortune-app"
echo "   停止服务: sudo systemctl stop fortune-app"
