#!/bin/bash
# BookAI — Universal setup (Ubuntu/Debian + CentOS/RHEL/AlmaLinux/Rocky)
# bash <(curl -fsSL https://raw.githubusercontent.com/bilonglo9x-code/bookai/initial-setup/fix_setup.sh)

set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

DEPLOY_DIR="/opt/bookai"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   BookAI — Universal Setup             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Detect OS / package manager ──────────────────────────────
detect_os() {
    if command -v apt-get &>/dev/null; then
        echo "debian"
    elif command -v dnf &>/dev/null; then
        echo "rhel_dnf"
    elif command -v yum &>/dev/null; then
        echo "rhel_yum"
    else
        echo "unknown"
    fi
}

OS_TYPE=$(detect_os)
info "Detected OS type: $OS_TYPE"

# ── Step 1: Install system packages ──────────────────────────
info "Installing system dependencies..."

if [ "$OS_TYPE" = "debian" ]; then
    apt-get update -qq
    apt-get install -y -qq \
        python3 python3-venv python3-pip python3-dev \
        ffmpeg tesseract-ocr tesseract-ocr-vie \
        git curl nginx build-essential libssl-dev 2>/dev/null || true
    # Try python3.11 specifically if available
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev 2>/dev/null || true

elif [ "$OS_TYPE" = "rhel_dnf" ]; then
    dnf install -y epel-release 2>/dev/null || true
    dnf install -y \
        python3 python3-pip python3-devel \
        git curl nginx \
        gcc openssl-devel 2>/dev/null || true
    # Try python3.11 from EPEL or SCL
    dnf install -y python3.11 python3.11-devel 2>/dev/null || \
    dnf install -y python311 2>/dev/null || true

elif [ "$OS_TYPE" = "rhel_yum" ]; then
    yum install -y epel-release 2>/dev/null || true
    yum install -y \
        python3 python3-pip python3-devel \
        git curl nginx \
        gcc openssl-devel 2>/dev/null || true

else
    warn "Unknown package manager — skipping system package install. Proceeding with available tools."
fi

# ── Step 2: Find best Python ─────────────────────────────────
PYTHON=""
for py in python3.11 python3.12 python3.10 python3.9 python3; do
    if command -v "$py" &>/dev/null; then
        VER=$($py -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
        info "Found: $py → $VER"
        PYTHON="$py"
        break
    fi
done
[ -z "$PYTHON" ] && err "No Python 3 found. Install python3 manually and retry."
log "Using Python: $PYTHON ($($PYTHON --version))"

# ── Step 3: Clone / update repo ──────────────────────────────
if [ ! -d "$DEPLOY_DIR/.git" ]; then
    info "Cloning repo..."
    git clone -b initial-setup https://github.com/bilonglo9x-code/bookai.git "$DEPLOY_DIR"
else
    info "Updating repo..."
    cd "$DEPLOY_DIR" && git fetch origin && git reset --hard origin/initial-setup
fi
log "Repo ready at $DEPLOY_DIR"

# ── Step 4: Create venv ──────────────────────────────────────
cd "$DEPLOY_DIR"
info "Creating Python venv with $PYTHON..."

# Remove broken venv if exists
[ -d venv ] && rm -rf venv

$PYTHON -m venv venv
log "Venv created"

source venv/bin/activate
pip install --upgrade pip setuptools wheel -q

# ── Step 5: Install Python packages ──────────────────────────
info "Installing Python packages (takes 2-5 min)..."
pip install -e . -q
pip install streamlit edge-tts fastapi "uvicorn[standard]" psutil httpx -q
log "Python packages installed"

# ── Step 6: Quick smoke test ─────────────────────────────────
info "Smoke test..."
python3 -c "import bookai; print('bookai import OK')"
python3 -m pytest tests/ -q --tb=line -x 2>&1 | tail -6 || warn "Some tests failed — check manually"

# ── Step 7: Admin token ───────────────────────────────────────
ADMIN_TOKEN="bookai_admin_$(openssl rand -hex 8 2>/dev/null || date +%s | sha256sum | head -c 16)"
cat > "$DEPLOY_DIR/.env" << ENVEOF
VPS_ADMIN_TOKEN=$ADMIN_TOKEN
DEPLOY_DIR=$DEPLOY_DIR
ENVEOF
echo "$ADMIN_TOKEN" > /root/bookai_admin_token.txt
log "Admin token saved"

# ── Step 8: Systemd — Streamlit ──────────────────────────────
cat > /etc/systemd/system/bookai.service << SVCEOF
[Unit]
Description=BookAI Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DEPLOY_DIR
EnvironmentFile=-$DEPLOY_DIR/.env
ExecStart=$DEPLOY_DIR/venv/bin/streamlit run src/bookai/app.py \
    --server.port 8501 --server.address 0.0.0.0 \
    --server.headless true --browser.gatherUsageStats false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

# ── Step 9: Systemd — Admin API ──────────────────────────────
cat > /etc/systemd/system/bookai-admin.service << SVCEOF
[Unit]
Description=BookAI Admin API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DEPLOY_DIR
EnvironmentFile=-$DEPLOY_DIR/.env
ExecStart=$DEPLOY_DIR/venv/bin/uvicorn admin_api:app \
    --host 127.0.0.1 --port 8502 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable bookai bookai-admin
systemctl restart bookai bookai-admin
sleep 3
log "Systemd services started"

# ── Step 10: Nginx ────────────────────────────────────────────
# Find nginx config dir (differs between distros)
if [ -d /etc/nginx/sites-available ]; then
    NGINX_CONF=/etc/nginx/sites-available/bookai
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/bookai
    rm -f /etc/nginx/sites-enabled/default
elif [ -d /etc/nginx/conf.d ]; then
    NGINX_CONF=/etc/nginx/conf.d/bookai.conf
    # Remove default on RHEL
    rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
fi

cat > "$NGINX_CONF" << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 200M;

    location /admin/ {
        proxy_pass http://127.0.0.1:8502/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 180;
    }

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}
NGINXEOF

# On RHEL, nginx may need SELinux permission for proxy
if command -v setsebool &>/dev/null; then
    setsebool -P httpd_can_network_connect 1 2>/dev/null || true
fi

systemctl enable nginx
nginx -t && systemctl restart nginx && log "Nginx configured"

# ── Step 11: Firewall ────────────────────────────────────────
if command -v ufw &>/dev/null && ufw status 2>/dev/null | grep -q "active"; then
    ufw allow 80/tcp -q; ufw allow 9090/tcp -q
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-service=http --quiet 2>/dev/null || true
    firewall-cmd --permanent --add-port=9090/tcp --quiet 2>/dev/null || true
    firewall-cmd --reload --quiet 2>/dev/null || true
    log "firewalld rules added"
fi

# ── Done ─────────────────────────────────────────────────────
SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
BOOKAI_OK=$(systemctl is-active bookai 2>/dev/null || echo "unknown")

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       BookAI Setup Hoàn Tất! 🎉             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  🌐 Dashboard:   http://$SERVER_IP"
echo "  🔧 Admin API:   http://$SERVER_IP/admin/health"
echo "  📊 bookai svc:  $BOOKAI_OK"
echo ""
echo "  ══════════════════════════════════════════"
echo "  🔑 ADMIN TOKEN: $ADMIN_TOKEN"
echo "     → Copy token này gửi cho Junior!"
echo "  ══════════════════════════════════════════"
echo ""
echo "  Test ngay:"
echo "  curl http://$SERVER_IP/admin/health \\"
echo "       -H 'Authorization: Bearer $ADMIN_TOKEN'"
echo ""
echo "  (Token cũng lưu tại: /root/bookai_admin_token.txt)"
echo ""
