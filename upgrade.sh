#!/bin/bash
# 树莓派基于 GitHub 仓库的 MVC 一键无痛升级与去密码自愈脚本
set -e

echo "=================================================="
echo "🍓 正在为树莓派升级 FRP Manager 到最新 GitHub 版本..."
echo "=================================================="

# 1. 自动定位或创建安装目录
TARGET_DIR="/home/jiang/frp_manager"
if [ ! -d "$TARGET_DIR" ]; then
    echo "📂 未找到默认目录，正在执行全新的 Git clone..."
    git clone https://github.com/Level6me/frp_manager "$TARGET_DIR"
else
    echo "📂 正在本地目录执行 Git pull 拉取最新代码..."
    cd "$TARGET_DIR"
    git reset --hard HEAD
    git pull origin main
fi

# 2. 强制将认证设定为关闭状态，实现免密登录
echo "🔐 正在写入免密认证配置文件..."
echo '{"username": "admin", "password": "", "auth_enabled": false}' > "$TARGET_DIR/auth.json"

# 3. 安装系统依赖
echo "📦 正在保障系统 Python Flask 依赖..."
sudo apt-get update -y && sudo apt-get install -y python3-flask

# 4. 写入并注册 Systemd 系统服务守护进程
echo "⚙️ 正在挂载 Systemd 托管服务..."
sudo bash -c "cat << 'EOF' > /etc/systemd/system/frp-web-manager.service
[Unit]
Description=FRP Web Manager
After=network.target

[Service]
Type=simple
User=jiang
WorkingDirectory=$TARGET_DIR
ExecStart=/usr/bin/python3 $TARGET_DIR/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable frp-web-manager
sudo systemctl restart frp-web-manager

echo "=================================================="
echo "🎉 树莓派已成功通过 GitHub 升级并拉起服务！"
echo "🔓 用户密码认证已成功关闭（已开启免密直接进入）。"
echo "🌐 请在局域网中直接访问树莓派：http://10.0.0.2:8081"
echo "=================================================="
