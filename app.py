from flask import Flask, request, redirect, jsonify, session, render_template
import subprocess, re, json, os, secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CFG = "/usr/local/frp/frpc.toml"

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.json")

def get_auth_credentials():
    if not os.path.exists(AUTH_FILE):
        default_username = "admin"
        default_password = secrets.token_hex(4)  # 8位随机强密码
        creds = {"username": default_username, "password": default_password, "auth_enabled": True}
        with open(AUTH_FILE, "w") as f:
            json.dump(creds, f)
        print(f"==================================================")
        print(f"🔑 FRP Manager Initialized Credentials:")
        print(f"👤 Username: {default_username}")
        print(f"🔒 Password: {default_password}")
        print(f"📝 Credentials saved to: {AUTH_FILE}")
        print(f"==================================================")
        return creds
    try:
        with open(AUTH_FILE) as f:
            data = json.load(f)
            if "auth_enabled" not in data:
                data["auth_enabled"] = True
            return data
    except:
        return {"username": "admin", "password": "admin_password", "auth_enabled": True}

# 确保启动时自动初始化或读取凭证并在后台打印
get_auth_credentials()



@app.before_request
def check_auth():
    if request.endpoint in ['login', 'static'] or request.path.startswith('/static'):
        return
    creds = get_auth_credentials()
    if not creds.get("auth_enabled", True):
        return
    if not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return redirect('/login')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("u")
        password = request.form.get("p")
        creds = get_auth_credentials()
        if username == creds["username"] and password == creds["password"]:
            session["logged_in"] = True
            return redirect("/")
        else:
            return render_template("login.html", error_msg="❌ 账号或密码错误")
    
    if session.get("logged_in"):
        return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/login")

@app.route("/api/auth/update", methods=["POST"])
def api_update_auth():
    try:
        data = request.json
        new_user = data.get("username", "").strip()
        new_pass = data.get("password", "").strip()
        auth_enabled = data.get("auth_enabled", True)
        
        if auth_enabled and (not new_user or not new_pass):
            return jsonify({"success": False, "error": "启用密码认证时，用户名或密码不能为空"}), 400
        
        creds = get_auth_credentials()
        updated_user = new_user if new_user else creds["username"]
        updated_pass = new_pass if new_pass else creds["password"]
        
        with open(AUTH_FILE, "w") as f:
            json.dump({"username": updated_user, "password": updated_pass, "auth_enabled": auth_enabled}, f)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/")
def index():
    r = subprocess.run(["sudo", "systemctl", "is-active", "frpc"], capture_output=True, text=True)
    running = r.stdout.strip() == "active"
    logs = subprocess.run(["journalctl", "-u", "frpc", "-n", "50", "--no-pager"], capture_output=True, text=True).stdout[:3000]
    cfg = read_config()
    proxies = read_proxies()
    
    sc = "running" if running else "stopped"
    st = "运行中" if running else "已停止"
    icon = "🟢" if running else "⚪️"
    btn = "<button type='submit' name='a' value='stop' class='btn btn-danger'>停止</button><button type='submit' name='a' value='restart' class='btn btn-secondary'>重启</button>" if running else "<button type='submit' name='a' value='start' class='btn btn-primary'>启动</button>"
    
    proxy_rows = ""
    for i, p in enumerate(proxies):
        proxy_rows += f"""<div class="proxy-item" id="proxy-{i}">
<div class="proxy-icon">📡</div>
<div class="proxy-info">
<span class="proxy-name">{p['name']}</span>
<span class="proxy-detail">{p['localIP']}:{p['localPort']}<span class="arrow">→</span>{p['remotePort']}</span>
</div>
<div class="proxy-type">{p['type'].upper()}</div>
<div class="proxy-actions">
<button class="btn-icon" onclick="editProxy({i})">✏️</button>
<button class="btn-icon btn-delete" onclick="deleteProxy({i})">🗑️</button>
</div></div>"""
    
    if not proxies:
        proxy_rows = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无转发配置</div></div>'
    
    proxies_json = json.dumps(proxies)
    auth_creds = get_auth_credentials()
    auth_config_json = json.dumps({"auth_enabled": auth_creds.get("auth_enabled", True)})
    
    return render_template("index.html", 
                           sc=sc, icon=icon, st=st, btn=btn, 
                           proxy_rows=proxy_rows, cfg=cfg, logs=logs, 
                           proxies_json=proxies_json, 
                           auth_config_json=auth_config_json)


@app.route("/api/status")
def api_status():
    r = subprocess.run(["sudo", "systemctl", "is-active", "frpc"], capture_output=True, text=True)
    running = r.stdout.strip() == "active"
    return jsonify({"running": running})

@app.route("/api/logs")
def api_logs():
    logs = subprocess.run(["journalctl", "-u", "frpc", "-n", "50", "--no-pager"], capture_output=True, text=True).stdout[:3000]
    return jsonify({"logs": logs})

@app.route("/api/proxies")
def api_proxies():
    proxies = read_proxies()
    return jsonify({"proxies": proxies})

@app.route("/api/tunnels")
def api_tunnels():
    import urllib.request
    import base64
    import json
    
    url = "http://127.0.0.1:7400/api/status"
    req = urllib.request.Request(url)
    auth_str = "admin:admin"
    auth_bytes = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    req.add_header("Authorization", f"Basic {auth_bytes}")
    
    try:
        with urllib.request.urlopen(req, timeout=1.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                tunnels = {}
                total_active_conns = 0
                for category in ["tcp", "udp", "http", "https"]:
                    if category in data:
                        for item in data[category]:
                            tunnels[item["name"]] = {
                                "status": item.get("status", "unknown"),
                                "err": item.get("err", ""),
                                "active_conns": item.get("active_conns", 0)
                            }
                            total_active_conns += item.get("active_conns", 0)
                return jsonify({
                    "success": True, 
                    "tunnels": tunnels, 
                    "total_active_conns": total_active_conns,
                    "raw_data": data
                })
    except Exception as e:
        pass
    return jsonify({"success": False, "error": "FRP 客户端未启动或管理控制台无法连接"})

def read_config():
    try:
        with open(CFG) as f: c = f.read()
        # 支持新旧两种格式
        tk = re.search(r'auth\.token = "([^"]+)"', c) or re.search(r'\[auth\][^\[]*token = "([^"]+)"', c, re.DOTALL)
        return {"sa": re.search(r'serverAddr = "([^"]+)"', c).group(1) or "your-server-ip",
                "sp": re.search(r"serverPort = (\d+)", c).group(1) or "5443",
                "tk": tk.group(1) if tk else "",
                "li": "10.0.0.2", "lp": "80", "rp": "8080"}
    except:
        return {"sa": "your-server-ip", "sp": "5443", "tk": "", "li": "10.0.0.2", "lp": "80", "rp": "8080"}

def read_proxies():
    proxies = []
    try:
        with open(CFG) as f: c = f.read()
        proxy_blocks = re.findall(r'\[\[proxies\]\]\n(.*?)(?=\[\[proxies\]\]|\Z)', c, re.DOTALL)
        for block in proxy_blocks:
            name = re.search(r'name = "([^"]+)"', block)
            ptype = re.search(r'type = "([^"]+)"', block)
            lip = re.search(r'localIP = "([^"]+)"', block)
            lport = re.search(r'localPort = (\d+)', block)
            rport = re.search(r'remotePort = (\d+)', block)
            custom_domain = re.search(r'customDomains = \["([^"]+)"\]', block)
            http_user = re.search(r'httpUser = "([^"]+)"', block)
            http_pass = re.search(r'httpPassword = "([^"]+)"', block)
            if name and ptype:
                proxies.append({
                    "name": name.group(1), "type": ptype.group(1),
                    "localIP": lip.group(1) if lip else "127.0.0.1",
                    "localPort": lport.group(1) if lport else "80",
                    "remotePort": rport.group(1) if rport else "",
                    "customDomain": custom_domain.group(1) if custom_domain else "",
                    "httpUser": http_user.group(1) if http_user else "",
                    "httpPassword": http_pass.group(1) if http_pass else ""
                })
    except Exception as e:
        print(f"Error: {e}")
    return proxies

def generate_config_content(proxies):
    c = ""
    if os.path.exists(CFG):
        try:
            with open(CFG) as f: c = f.read()
        except:
            pass
    sa_match = re.search(r'serverAddr = "([^"]+)"', c)
    sa = sa_match.group(1) if sa_match else "your-server-ip"
    sp_match = re.search(r"serverPort = (\d+)", c)
    sp = sp_match.group(1) if sp_match else "5443"
    tk = re.search(r'auth\.token = "([^"]+)"', c) or re.search(r'\[auth\][^\[]*token = "([^"]+)"', c, re.DOTALL)
    token = tk.group(1) if tk else ""
    cfg = f'serverAddr = "{sa}"\nserverPort = {sp}\n\n[auth]\ntoken = "{token}"\n\n[transport]\ntcpMux = true\n\n[log]\nlevel = "info"\nmaxDays = 3\n\n[webServer]\naddr = "127.0.0.1"\nport = 7400\nuser = "admin"\npassword = "admin"\n'
    for p in proxies:
        if p["type"] in ["http", "https"]:
            cfg += f'\n[[proxies]]\nname = "{p["name"]}"\ntype = "{p["type"]}"\nlocalIP = "{p["localIP"]}"\nlocalPort = {p["localPort"]}\n'
            if p.get("httpUser") and p.get("httpPassword"):
                cfg += f'httpUser = "{p["httpUser"]}"\nhttpPassword = "{p["httpPassword"]}"\n'
            cfg += f'customDomains = ["{p.get("customDomain", p["name"] + ".example.com")}"]\n'
        else:
            cfg += f'\n[[proxies]]\nname = "{p["name"]}"\ntype = "{p["type"]}"\nlocalIP = "{p["localIP"]}"\nlocalPort = {p["localPort"]}\nremotePort = {p["remotePort"]}\n'
    return cfg

def find_frpc_path():
    paths = ["/usr/local/frp/frpc", "/usr/local/bin/frpc", "/usr/bin/frpc"]
    for p in paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    try:
        r = subprocess.run(["which", "frpc"], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip()
    except:
        pass
    return None

def apply_config_and_restart(new_config_str):
    # 1. 静态语法 Dry Run 校验
    frpc_path = find_frpc_path()
    if frpc_path:
        temp_cfg = "/tmp/frpc_verify.toml"
        try:
            with open(temp_cfg, "w") as f:
                f.write(new_config_str)
            r = subprocess.run([frpc_path, "verify", "-c", temp_cfg], capture_output=True, text=True)
            if r.returncode != 0 and "unknown command" not in r.stderr:
                err = r.stderr.strip() or r.stdout.strip() or "静态配置语法格式错误"
                return False, f"⚠️ 配置格式校验失败，已阻断应用：{err}"
        except Exception as e:
            pass
        finally:
            if os.path.exists(temp_cfg):
                try: os.remove(temp_cfg)
                except: pass

    # 2. 备份当前配置
    old_config_str = ""
    if os.path.exists(CFG):
        try:
            with open(CFG) as f: old_config_str = f.read()
        except:
            pass

    # 3. 写入新配置
    try:
        os.makedirs(os.path.dirname(CFG), exist_ok=True)
        with open(CFG, "w") as f:
            f.write(new_config_str)
    except Exception as e:
        return False, f"无法写入配置文件：{e}"

    # 4. 重启服务
    try:
        subprocess.run(["sudo", "systemctl", "restart", "frpc"], check=True, capture_output=True)
    except Exception as e:
        return False, f"无法重启 frpc 服务：{e}"

    # 5. 动态跟踪检测 3 秒
    import time
    for _ in range(6):
        time.sleep(0.5)
        r = subprocess.run(["sudo", "systemctl", "is-active", "frpc"], capture_output=True, text=True)
        if r.stdout.strip() != "active":
            # 获取崩溃日志
            logs_r = subprocess.run(["journalctl", "-u", "frpc", "-n", "10", "--no-pager"], capture_output=True, text=True)
            crash_logs = logs_r.stdout.strip() or "服务启动后在 3 秒内发生意外退出了"
            # 自动回滚
            if old_config_str:
                try:
                    with open(CFG, "w") as f: f.write(old_config_str)
                    subprocess.run(["sudo", "systemctl", "restart", "frpc"])
                except Exception as rollback_err:
                    crash_logs += f"\n(且配置自动还原失败：{rollback_err})"
            return False, f"🚨 服务启动失败，已自动回滚配置！崩溃原因：\n{crash_logs}"

    return True, None

def write_proxies(proxies):
    content = generate_config_content(proxies)
    with open(CFG, "w") as f: f.write(content)

@app.route("/api/proxy/save", methods=["POST"])
def api_save_proxy():
    try:
        data = request.json
        proxies = read_proxies()
        idx = data.get('index', -1)
        new_proxy = {
            "name": data['name'],
            "type": data['type'],
            "localIP": data['localIP'],
            "localPort": data['localPort'],
            "remotePort": data['remotePort'],
            "httpUser": data.get('httpUser', ''),
            "httpPassword": data.get('httpPassword', '')
        }
        if idx >= 0 and idx < len(proxies): proxies[idx] = new_proxy
        else: proxies.append(new_proxy)
        
        new_cfg_content = generate_config_content(proxies)
        success, err_msg = apply_config_and_restart(new_cfg_content)
        if not success:
            return jsonify({"success": False, "error": err_msg}), 400
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/proxy/delete", methods=["POST"])
def api_delete_proxy():
    try:
        data = request.json
        proxies = read_proxies()
        idx = data.get('index', -1)
        if idx >= 0 and idx < len(proxies):
            proxies.pop(idx)
            new_cfg_content = generate_config_content(proxies)
            success, err_msg = apply_config_and_restart(new_cfg_content)
            if not success:
                return jsonify({"success": False, "error": err_msg}), 400
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Invalid index"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/save", methods=["POST"])
def save():
    sa = request.form.get("sa")
    sp = request.form.get("sp")
    tk = request.form.get("tk")
    proxies = read_proxies()
    cfg_content = f'serverAddr = "{sa}"\nserverPort = {sp}\n\n[auth]\ntoken = "{tk}"\n\n[transport]\ntcpMux = true\n\n[log]\nlevel = "info"\nmaxDays = 3\n\n[webServer]\naddr = "127.0.0.1"\nport = 7400\nuser = "admin"\npassword = "admin"\n'
    for p in proxies:
        if p["type"] in ["http", "https"]:
            cfg_content += f'\n[[proxies]]\nname = "{p["name"]}"\ntype = "{p["type"]}"\nlocalIP = "{p["localIP"]}"\nlocalPort = {p["localPort"]}\n'
            if p.get("httpUser") and p.get("httpPassword"):
                cfg_content += f'httpUser = "{p["httpUser"]}"\nhttpPassword = "{p["httpPassword"]}"\n'
            cfg_content += f'customDomains = ["{p.get("customDomain", p["name"] + ".example.com")}"]\n'
        else:
            cfg_content += f'\n[[proxies]]\nname = "{p["name"]}"\ntype = "{p["type"]}"\nlocalIP = "{p["localIP"]}"\nlocalPort = {p["localPort"]}\nremotePort = {p["remotePort"]}\n'
            
    success, err_msg = apply_config_and_restart(cfg_content)
    if not success:
        err_html = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>FRP Manager - Error</title>
<style>
body { font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif; background:#F2F2F7; padding:40px 20px; text-align:center; }
.card { background:#fff; max-width:500px; margin:0 auto; padding:30px; border-radius:14px; box-shadow:0 8px 30px rgba(0,0,0,0.08); text-align:left; }
h2 { color:#FF3B30; margin-bottom:12px; }
pre { background:#F2F2F7; padding:12px; border-radius:8px; font-family:monospace; font-size:12px; white-space:pre-wrap; }
.btn { display:inline-block; margin-top:20px; background:#007AFF; color:#fff; text-decoration:none; padding:10px 20px; border-radius:8px; font-weight:600; }
</style></head>
<body><div class="card">
<h2>🚨 配置更新失败，已自动恢复！</h2>
<p>应用主配置时，服务未能正常拉起。为了保障控制面板与代理服务的可用性，系统已自动回滚了配置文件。</p>
<hr style="margin:20px 0; border:0; border-top:1px solid rgba(60,60,67,0.12)">
<p><strong>详细排错日志：</strong></p>
<pre>ERROR_MSG_PLACEHOLDER</pre>
<a href="/" class="btn">返回主页面</a>
</div></body></html>"""
        return err_html.replace("ERROR_MSG_PLACEHOLDER", str(err_msg))
    return redirect("/")

@app.route("/ctrl", methods=["POST"])
def ctrl():
    subprocess.run(["sudo", "systemctl", request.form.get("a"), "frpc"])
    return redirect("/")
def is_safe_filename(filename):
    if not re.match(r'^[a-zA-Z0-9_\-\.]+\.toml$', filename):
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return True

@app.route("/api/configs")
def api_configs():
    configs = []
    cfg_dir = os.path.dirname(CFG)
    if not os.path.exists(cfg_dir):
        os.makedirs(cfg_dir, exist_ok=True)
        
    files = [f for f in os.listdir(cfg_dir) if f.endswith(".toml") and f != "frpc.toml"]
    # 额外过滤不安全的文件名，防止垃圾或恶意注入显现
    files = [f for f in files if is_safe_filename(f)]
    if not files:
        default_path = os.path.join(cfg_dir, "default.toml")
        if not os.path.exists(default_path):
            default_content = 'serverAddr = "your-server-ip"\nserverPort = 5443\n\n[auth]\ntoken = ""\n\n[transport]\ntcpMux = true\n\n[log]\nlevel = "info"\nmaxDays = 3\n'
            try:
                with open(default_path, "w") as f: f.write(default_content)
                files.append("default.toml")
            except: pass
        else:
            files.append("default.toml")
        
    if not os.path.exists(CFG) and not os.path.islink(CFG):
        try:
            os.symlink(os.path.join(cfg_dir, files[0]), CFG)
        except: pass
        
    active_file = "frpc.toml"
    if os.path.islink(CFG):
        try:
            active_file = os.path.basename(os.readlink(CFG))
        except: pass
        
    return jsonify({"configs": sorted(files), "active": active_file})

@app.route("/api/config/switch", methods=["POST"])
def api_config_switch():
    try:
        data = request.json
        target_file = data.get("file", "").strip()
        if not is_safe_filename(target_file):
            return jsonify({"success": False, "error": "非法的配置文件名称"}), 400
            
        cfg_dir = os.path.dirname(CFG)
        target_path = os.path.join(cfg_dir, target_file)
        
        if not target_file or not os.path.exists(target_path) or target_file == "frpc.toml":
            return jsonify({"success": False, "error": "目标配置文件无效"}), 400
            
        if os.path.exists(CFG) or os.path.islink(CFG):
            try: os.remove(CFG)
            except Exception as e: return jsonify({"success": False, "error": f"无法清理旧软链接: {e}"}), 500
            
        try:
            os.symlink(target_path, CFG)
        except Exception as e:
            return jsonify({"success": False, "error": f"创建软链接失败: {e}"}), 500
            
        with open(CFG) as f: content = f.read()
        success, err_msg = apply_config_and_restart(content)
        if not success:
            return jsonify({"success": False, "error": err_msg}), 400
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/config/create", methods=["POST"])
def api_config_create():
    try:
        data = request.json
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"success": False, "error": "配置文件名称不能为空"}), 400
        if not name.endswith(".toml"):
            name += ".toml"
        if name == "frpc.toml":
            return jsonify({"success": False, "error": "不能创建与系统软链接同名的配置文件"}), 400
        if not is_safe_filename(name):
            return jsonify({"success": False, "error": "非法的配置文件名称"}), 400
            
        cfg_dir = os.path.dirname(CFG)
        new_path = os.path.join(cfg_dir, name)
        if os.path.exists(new_path):
            return jsonify({"success": False, "error": "同名配置文件已存在"}), 400
            
        default_content = 'serverAddr = "your-server-ip"\nserverPort = 5443\n\n[auth]\ntoken = ""\n\n[transport]\ntcpMux = true\n\n[log]\nlevel = "info"\nmaxDays = 3\n'
        with open(new_path, "w") as f:
            f.write(default_content)
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False)
