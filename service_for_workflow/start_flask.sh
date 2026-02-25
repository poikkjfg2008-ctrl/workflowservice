#!/bin/bash
# Flask应用启动脚本

echo "======================================"
echo "  Flask智能对话系统 - 启动中..."
echo "======================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3"
    exit 1
fi

# 安装Flask依赖
echo "📦 安装Flask依赖..."
pip3 install Flask Werkzeug -q

# 启动应用
echo "🚀 启动Flask应用..."
python3 flask_app.py
