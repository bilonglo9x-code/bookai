#!/bin/bash
# BookAI Monitoring Setup — installs admin API + Cockpit for remote monitoring
# Run AFTER deploy.sh: bash deploy_monitor.sh
# Junior accesses: http://104.207.75.43/admin/*  (via nginx proxy)
# Cockpit UI:       http://104.207.75.43:9090

set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

DEPLOY_DIR="/opt/bookai"
ADMIN_TOKEN="${VPS_ADMIN_TOKEN:-bookai_admin_$(openssl rand -hex 8)}"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   BookAI Monitoring Setup               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# -----------------------------------------------------------
# 1. Install Cockpit (web-based server management UI)
# -----------------------------------------------------------
info "Installing Cockpit (web terminal + monitoring)..."
apt-get install -y -qq cockpit cockpit-packagekit 2>/dev/null || \
apt-get install -y -qq cockpit 2>/dev/null || true
systemctl enable --now cockpit.socket 2>/dev/null || true
log "Cockpit installed → port 9090"

# -----------------------------------------------------------
# 2. Install Admin API dependencies
# -----------------------------------------------------------
info "Installing Admin API dependencies..."
source "$DEPLOY_DIR/venv/bin/activate"
pip install fastapi uvicorn psutil -q
log "FastAPI + uvicorn + psutil installed"

# -----------------------------------------------------------
# 3. Copy admin_api.py to deploy dir
# -----------------------------------------------------------
info "Setting up admin_api.py..."
cp "$DEPLOY_DIR/admin_api.py" "$DEPLOY_DIR/admin_api.py" 2>/dev/null || true
# Save admin token to .env
if ! grep -q "VPS_ADMIN_TOKEN" "$DEPLOY_DIR/.env" 2>/dev/null; then
    echo "VPS_ADMIN_TOKEN=$ADMIN_TOKEN" >> "$DEPLOY_DIR/.env"
fi
log "Admin token configured"

# -----------------------------------------------------------
# 4. Systemd service for Admin API
# -----------------------------------------------------------
cat > /etc/systemd/system/bookai-admin.service << SVCEOF
[Unit]
Description=BookAI Admin API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DEPLOY_DIR
EnvironmentFile=-$DEPLOY_DIR/.env
ExecStart=$DEPLOY_DIR/venv/bin/uvicorn admin_api:app --host 127.0.0.1 --port 8502 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable bookai-admin
systemctl restart bookai-admin
sleep 2
log "Admin API service started on :8502"

# -----------------------------------------------------------
# 5. Nginx: proxy /admin/* → :8502 (add to existing config)
# -----------------------------------------------------------
cat > /etc/nginx/sites-available/bookai << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 200M;

    # Admin API (Junior uses this for monitoring)
    location /admin/ {
        proxy_pass http://127.0.0.1:8502/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 180;
    }

    # Streamlit Dashboard
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}
NGINXEOF

nginx -t && systemctl restart nginx
log "Nginx updated: /admin/* → Admin API, / → Dashboard"

# -----------------------------------------------------------
# 6. Firewall: allow Cockpit port
# -----------------------------------------------------------
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 9090/tcp -q
    log "Firewall: port 9090 (Cockpit) opened"
fi

# -----------------------------------------------------------
# Done
# -----------------------------------------------------------
SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
SAVED_TOKEN=$(grep VPS_ADMIN_TOKEN "$DEPLOY_DIR/.env" | cut -d= -f2)

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     BookAI Monitoring Setup Xong! 🎉        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  📊 Dashboard:    http://$SERVER_IP"
echo "  🔧 Admin API:    http://$SERVER_IP/admin/"
echo "  🖥️  Cockpit UI:  http://$SERVER_IP:9090"
echo ""
echo "  🔑 Admin Token: $SAVED_TOKEN"
echo "     → Junior dùng token này để gọi API"
echo ""
echo "  Test Admin API:"
echo "  curl -H 'Authorization: Bearer $SAVED_TOKEN' http://$SERVER_IP/admin/health"
echo ""
