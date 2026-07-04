let refreshInterval = null;
let latestTunnels = {};

// 页面加载完成后开始自动刷新
document.addEventListener('DOMContentLoaded', function() {
    startAutoRefresh();
    refreshConfigs();
    refreshTunnels().then(() => {
        refreshProxies();
    });
});

function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        refreshStatus();
        refreshLogs();
        refreshTunnels();
    }, 5000);
}

function stopAutoRefresh() {
    if(refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

function refreshAll() {
    const btn = document.getElementById('refreshBtn');
    btn.classList.add('spinning');
    
    refreshStatus();
    refreshLogs();
    refreshConfigs();
    refreshTunnels().then(() => {
        refreshProxies();
    });
    
    setTimeout(() => {
        btn.classList.remove('spinning');
        showToast('已刷新');
    }, 1000);
}

function refreshStatus() {
    fetch('/api/status')
        .then(r => r.json())
        .then(d => {
            const badge = document.getElementById('statusBadge');
            const btnGroup = document.getElementById('btnGroup');
            
            if(d.running) {
                badge.className = 'status-badge running';
                badge.innerHTML = '<span>🟢</span><span>运行中</span>';
                btnGroup.innerHTML = '<form method="post" action="/ctrl" style="display:inline"><button type="submit" name="a" value="stop" class="btn btn-danger">停止</button><button type="submit" name="a" value="restart" class="btn btn-secondary">重启</button></form>';
            } else {
                badge.className = 'status-badge stopped';
                badge.innerHTML = '<span>⚪️</span><span>已停止</span>';
                btnGroup.innerHTML = '<form method="post" action="/ctrl" style="display:inline"><button type="submit" name="a" value="start" class="btn btn-primary">启动</button></form>';
            }
        })
        .catch(e => console.error('Refresh status error:', e));
}

function refreshLogs() {
    fetch('/api/logs')
        .then(r => r.json())
        .then(d => {
            document.getElementById('logsContent').textContent = d.logs;
        })
        .catch(e => console.error('Refresh logs error:', e));
}

function refreshTunnels() {
    return fetch('/api/tunnels')
        .then(r => r.json())
        .then(d => {
            const badge = document.getElementById('proxyMiniBadge');
            if(d.success) {
                latestTunnels = d.tunnels;
                
                let running = 0;
                let error = 0;
                for (let name in d.tunnels) {
                    if (d.tunnels[name].status === 'running') {
                        running++;
                    } else {
                        error++;
                    }
                }
                
                let tcp = (d.raw_data && d.raw_data.tcp || []).length;
                let udp = (d.raw_data && d.raw_data.udp || []).length;
                let http = (d.raw_data && d.raw_data.http || []).length;
                let https = (d.raw_data && d.raw_data.https || []).length;
                let typesStr = [];
                if (tcp > 0) typesStr.push(`TCP: ${tcp}`);
                if (udp > 0) typesStr.push(`UDP: ${udp}`);
                if (http > 0) typesStr.push(`HTTP: ${http}`);
                if (https > 0) typesStr.push(`HTTPS: ${https}`);
                const typesPart = typesStr.join(' | ') || '无映射';
                
                badge.innerHTML = `🟢 ${running} 运行中 &nbsp;|&nbsp; 🔴 ${error} 异常 &nbsp;|&nbsp; ${typesPart}`;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
                latestTunnels = {};
            }
        })
        .catch(e => {
            console.error('Refresh tunnels error:', e);
            const badge = document.getElementById('proxyMiniBadge');
            if (badge) badge.style.display = 'none';
            latestTunnels = {};
        });
}

function refreshProxies() {
    fetch('/api/proxies')
        .then(r => r.json())
        .then(d => {
            const list = document.getElementById('proxyList');
            if(d.proxies.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无转发配置</div></div>';
            } else {
                list.innerHTML = d.proxies.map(function(p, i) {
                    let statusHtml = '<span style="font-size:12px;color:var(--apple-text-secondary);margin-left:8px">⚪ 离线</span>';
                    if (latestTunnels && latestTunnels[p.name]) {
                        const t = latestTunnels[p.name];
                        if (t.status === 'running') {
                            statusHtml = `<span style="font-size:12px;color:var(--apple-green);margin-left:8px;font-weight:600">🟢 运行中</span>`;
                        } else {
                            statusHtml = `<span style="font-size:12px;color:var(--apple-red);margin-left:8px;font-weight:600" title="${t.err}">🔴 异常</span>`;
                        }
                    }
                    return '<div class="proxy-item" id="proxy-' + i + '">' +
                        '<div class="proxy-icon">📡</div>' +
                        '<div class="proxy-info">' +
                        '<div style="display:flex;align-items:center">' +
                        '<span class="proxy-name">' + p.name + '</span>' +
                        statusHtml +
                        '</div>' +
                        '<span class="proxy-detail">' + p.localIP + ':' + p.localPort + '<span class="arrow">→</span>' + p.remotePort + '</span>' +
                        '</div>' +
                        '<div class="proxy-type">' + p.type.toUpperCase() + '</div>' +
                        '<div class="proxy-actions">' +
                        '<button class="btn-icon" onclick="editProxy(' + i + ')">✏️</button>' +
                        '<button class="btn-icon btn-delete" onclick="deleteProxy(' + i + ')">🗑️</button>' +
                        '</div></div>';
                }).join('');
            }
        })
        .catch(e => console.error('Refresh proxies error:', e));
}

function editProxy(idx) {
    const p = proxies[idx];
    document.getElementById('proxyIndex').value = idx;
    document.getElementById('pName').value = p.name;
    document.getElementById('pType').value = p.type;
    document.getElementById('pLocalIP').value = p.localIP;
    document.getElementById('pLocalPort').value = p.localPort;
    document.getElementById('pRemotePort').value = p.remotePort || '';
    document.getElementById('pCustomDomain').value = p.customDomain || '';
    document.getElementById('pHttpUser').value = p.httpUser || '';
    document.getElementById('pHttpPassword').value = p.httpPassword || '';
    toggleAuthFields();
    document.getElementById('modalTitle').textContent = '编辑代理';
    document.getElementById('proxyModal').classList.add('active');
}

function addProxy() {
    document.getElementById('proxyIndex').value = -1;
    document.getElementById('pName').value = '';
    document.getElementById('pType').value = 'tcp';
    document.getElementById('pLocalIP').value = '127.0.0.1';
    document.getElementById('pLocalPort').value = '';
    document.getElementById('pRemotePort').value = '';
    document.getElementById('pCustomDomain').value = '';
    document.getElementById('pHttpUser').value = '';
    document.getElementById('pHttpPassword').value = '';
    toggleAuthFields();
    document.getElementById('modalTitle').textContent = '添加代理';
    document.getElementById('proxyModal').classList.add('active');
}

function toggleAuthFields() {
    const type = document.getElementById('pType').value;
    const authDiv = document.getElementById('authFields');
    if(type === 'http' || type === 'https') {
        authDiv.style.display = 'block';
    } else {
        authDiv.style.display = 'none';
    }
}

function deleteProxy(idx) {
    if(confirm('确定要删除这个代理配置吗？')) {
        fetch('/api/proxy/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({index: idx})
        }).then(r => r.json()).then(d => {
            if(d.success) { showToast('已删除'); setTimeout(() => location.reload(), 1000); }
            else { showToast(d.error, 'error'); }
        });
    }
}

function saveProxy(e) {
    e.preventDefault();
    const data = {
        index: parseInt(document.getElementById('proxyIndex').value),
        name: document.getElementById('pName').value,
        type: document.getElementById('pType').value,
        localIP: document.getElementById('pLocalIP').value,
        localPort: parseInt(document.getElementById('pLocalPort').value),
        remotePort: parseInt(document.getElementById('pRemotePort').value),
        customDomain: document.getElementById('pCustomDomain').value,
        httpUser: document.getElementById('pHttpUser').value,
        httpPassword: document.getElementById('pHttpPassword').value
    };
    fetch('/api/proxy/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()).then(d => {
        if(d.success) { 
            showToast('保存成功！'); 
            closeModal();
            setTimeout(() => location.reload(), 1000); 
        }
        else { showToast(d.error, 'error'); }
    });
}

function closeModal() { document.getElementById('proxyModal').classList.remove('active'); }

function showToast(msg, type) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show' + (type ? ' ' + type : '');
    setTimeout(() => { t.classList.remove('show'); }, 2500);
}

document.getElementById('proxyModal').addEventListener('click', function(e) {
    if(e.target === this) closeModal();
});

function openAuthModal() {
    document.getElementById('aUser').value = '';
    document.getElementById('aPass').value = '';
    document.getElementById('aEnabled').checked = authConfig.auth_enabled;
    toggleAuthInputs();
    document.getElementById('authModal').classList.add('active');
}

function closeAuthModal() {
    document.getElementById('authModal').classList.remove('active');
}

function toggleAuthInputs() {
    const enabled = document.getElementById('aEnabled').checked;
    const uInput = document.getElementById('aUser');
    const pInput = document.getElementById('aPass');
    uInput.required = enabled;
    pInput.required = enabled;
    uInput.disabled = !enabled;
    pInput.disabled = !enabled;
    if(!enabled) {
        uInput.value = '';
        pInput.value = '';
    }
}

function saveAuth(e) {
    e.preventDefault();
    const data = {
        username: document.getElementById('aUser').value,
        password: document.getElementById('aPass').value,
        auth_enabled: document.getElementById('aEnabled').checked
    };
    fetch('/api/auth/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()).then(d => {
        if(d.success) {
            showToast('设置更新成功！正在重新载入');
            closeAuthModal();
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast(d.error, 'error');
        }
    });
}

document.getElementById('authModal').addEventListener('click', function(e) {
    if(e.target === this) closeAuthModal();
});

function refreshConfigs() {
    fetch('/api/configs')
        .then(r => r.json())
        .then(d => {
            const list = document.getElementById('configList');
            list.innerHTML = d.configs.map(f => {
                const isActive = f === d.active;
                const activeBadge = isActive ? '<span class="status-badge running btn-sm" style="padding:4px 8px;font-size:12px">● 激活中</span>' : '';
                const switchBtn = isActive ? '' : `<button class="btn btn-secondary btn-sm" onclick="switchConfig('${f}')">切换</button>`;
                const activeBgClass = isActive ? 'style="background:rgba(0,122,255,0.05)"' : '';
                return '<div class="proxy-item" ' + activeBgClass + '>' +
                    '<div class="proxy-icon">📄</div>' +
                    '<div class="proxy-info">' +
                    '<span class="proxy-name" style="font-family:monospace">' + f + '</span>' +
                    '</div>' +
                    '<div style="display:flex;align-items:center;gap:10px">' +
                    activeBadge +
                    switchBtn +
                    '</div></div>';
            }).join('');
        })
        .catch(e => console.error('Refresh configs error:', e));
}

function switchConfig(filename) {
    if (confirm(`确定要切换并激活配置文件 [${filename}] 吗？\n（系统将立即重新加载该配置下的所有转发规则）`)) {
        fetch('/api/config/switch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({file: filename})
        }).then(r => r.json()).then(d => {
            if(d.success) {
                showToast('配置切换成功！服务已重新加载');
                setTimeout(() => location.reload(), 1500);
            } else {
                showToast(d.error, 'error');
            }
        });
    }
}

function addConfig() {
    document.getElementById('cName').value = '';
    document.getElementById('configModal').classList.add('active');
}

function closeConfigModal() {
    document.getElementById('configModal').classList.remove('active');
}

// 确保该函数成功注册并绑定
function saveConfig(e) {
    e.preventDefault();
    const data = {
        name: document.getElementById('cName').value
    };
    fetch('/api/config/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()).then(d => {
        if(d.success) {
            showToast('配置文件创建成功！');
            closeConfigModal();
            refreshConfigs();
        } else {
            showToast(d.error, 'error');
        }
    });
}

document.getElementById('configModal').addEventListener('click', function(e) {
    if(e.target === this) closeConfigModal();
});
