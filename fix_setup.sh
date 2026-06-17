#!/bin/bash
# BookAI — Fix venv + complete setup
# Run on VPS: bash <(curl -fsSL https://raw.githubusercontent.com/bilonglo9x-code/bookai/initial-setup/fix_setup.sh)

set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

DEPLOY_DIR="/opt/bookai"
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   BookAI — Fix & Complete Setup         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: Ensure system deps ──────────────────────────────
info "Ensuring system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev python3-pip python3-full \
    ffmpeg tesseract-ocr tesseract-ocr-vie git curl nginx \
    build-essential libssl-dev 2>/dev/null | grep -E "(installed|upgraded)" || true
log "System deps OK"

# ── Step 2: Ensure repo exists ──────────────────────────────
if [ ! -d "$DEPLOY_DIR/.git" ]; then
    info "Cloning repo..."
    git clone -b initial-setup https://github.com/bilonglo9x-code/bookai.git "$DEPLOY_DIR"
else
    info "Updating repo..."
    cd "$DEPLOY_DIR" && git pull origin initial-setup
fi
log "Repo at $DEPLOY_DIR"

# ── Step 3: Create venv ──────────────────────────────────────
cd "$DEPLOY_DIR"
info "Creating Python 3.11 venv..."
python3.11 -m venv venv
log "Venv created: $DEPLOY_DIR/venv"

# ── Step 4: Install dependencies ────────────────────────────
info "Installing Python dependencies (may take 2-3 min)..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
pip install -e . -q
pip install streamlit edge-tts fastapi uvicorn psutil -q
log "Python packages installed"

# ── Step 5: Run tests ────────────────────────────────────────
info "Running tests..."
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5 || true

# ── Step 6: Create .env ──────────────────────────────────────
ADMIN_TOKEN="bookai_admin_$(openssl rand -hex 8)"
cat > "$DEPLOY_DIR/.env" << ENVEOF
VPS_ADMIN_TOKEN=$ADMIN_TOKEN
DEPLOY_DIR=$DEPLOY_DIR
ENVEOF
log ".env created with admin token"

# ── Step 7: Streamlit systemd service ───────────────────────
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
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

# ── Step 8: Admin API systemd service ───────────────────────
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
log "Services started"

# ── Step 9: Nginx config ─────────────────────────────────────
cat > /etc/nginx/sites-available/bookai << 'NGINXEOF'
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

ln -sf /etc/nginx/sites-available/bookai /etc/nginx/sites-enabled/bookai
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
log "Nginx configured"

# ── Step 10: Firewall ────────────────────────────────────────
if command -v ufw &>/dev/null && ufw status 2>/dev/null | grep -q "active"; then
    ufw allow 22/tcp -q; ufw allow 80/tcp -q; ufw allow 9090/tcp -q
    log "Firewall rules OK"
fi

# ── Done ─────────────────────────────────────────────────────
SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         BookAI Setup Hoàn Tất! 🎉           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  🌐 Dashboard:   http://$SERVER_IP"
echo "  🔧 Admin API:   http://$SERVER_IP/admin/health"
echo ""
echo "  🔑 ADMIN TOKEN: $ADMIN_TOKEN"
echo "     → Copy token này gửi cho Junior!"
echo ""
echo "  Kiểm tra ngay:"
echo "  curl http://$SERVER_IP/admin/health -H 'Authorization: Bearer $ADMIN_TOKEN'"
echo ""

# Save token to file for easy retrieval
echo "$ADMIN_TOKEN" > /root/bookai_admin_token.txt
echo "  (Token cũng lưu tại: /root/bookai_admin_token.txt)"
echo ""
