#!/bin/bash
# 在本地开发机运行的脚本，通过 SSH 一键将树莓派(10.0.0.2)上的 frp_manager 升级到最新 GitHub MVC 版本
set -e

PI_IP="10.0.0.2"
PI_USER="jiang"
PI_PASS="1314520jh"
PI_DIR="/home/jiang/frp_manager"

echo "=================================================="
echo "🍓 正在连接树莓派 ${PI_IP} 执行一键无痛升级与自愈..."
echo "=================================================="

# 1. 验证树莓派 SSH 连通性并拉取 GitHub 最新代码进行覆盖更新
echo "📡 正在通过 SSH 登录树莓派并拉取 GitHub 上的最新重构代码..."
sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_IP} "
    if [ ! -d '$PI_DIR' ]; then
        echo '📂 未找到目录，正在执行全新的 Git clone...'
        git clone https://github.com/nian-chong/frp_manager.git '$PI_DIR'
    else
        echo '📂 正在进入目录执行 Git 拉取...'
        cd '$PI_DIR'
        git reset --hard HEAD
        git pull https://github.com/nian-chong/frp_manager.git main
    fi
"

# 2. 远程关闭密码认证并保障 Python Flask 依赖
echo "🔓 正在远程关闭用户密码认证，并保障 Python Flask 依赖..."
sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_IP} "
    echo '{\"username\": \"admin\", \"password\": \"\", \"auth_enabled\": false}' > '$PI_DIR/auth.json'
    sudo apt-get update -y && sudo apt-get install -y python3-flask
"

# 3. 远程生成并注册 Systemd 服务单元
echo "⚙️ 正在挂载 Systemd 托管服务并重启..."
sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_IP} "
    sudo bash -c \"cat << 'EOF' > /etc/systemd/system/frp-web-manager.service
[Unit]
Description=FRP Web Manager
After=network.target

[Service]
Type=simple
User=jiang
WorkingDirectory=$PI_DIR
ExecStart=/usr/bin/python3 $PI_DIR/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF\"
    sudo systemctl daemon-reload
    sudo systemctl enable frp-web-manager
    sudo systemctl restart frp-web-manager
"

echo "=================================================="
echo "🎉 树莓派升级已全部顺利完成！"
echo "🔓 密码认证已关闭（已启用免密直接登录）。"
echo "🌐 请在局域网内直接访问：http://${PI_IP}:8081"
echo "=================================================="
