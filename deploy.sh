#!/bin/bash
# BookAI — One-click deploy script for Ubuntu VPS
# Run as root: bash deploy.sh
# Then access: http://YOUR_IP:8501

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     BookAI — Auto Deploy to VPS         ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# -----------------------------------------------------------
# 0. Root check
# -----------------------------------------------------------
[[ $EUID -ne 0 ]] && err "Run as root: sudo bash deploy.sh"

# -----------------------------------------------------------
# 1. System packages
# -----------------------------------------------------------
info "Updating system packages..."
apt-get update -qq

info "Installing Python 3.11, FFmpeg, Tesseract, git, nginx..."
apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    ffmpeg \
    tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng \
    git curl wget nginx \
    build-essential libssl-dev libffi-dev \
    2>&1 | grep -E "(installed|upgraded|error)" || true
log "System packages installed"

# -----------------------------------------------------------
# 2. Clone / update repo
# -----------------------------------------------------------
DEPLOY_DIR="/opt/bookai"
REPO_URL="https://github.com/bilonglo9x-code/bookai.git"
BRANCH="initial-setup"

if [ -d "$DEPLOY_DIR/.git" ]; then
    info "Updating existing repo..."
    cd "$DEPLOY_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    info "Cloning BookAI repo..."
    git clone -b "$BRANCH" "$REPO_URL" "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi
log "Repo ready at $DEPLOY_DIR"

# -----------------------------------------------------------
# 3. Python virtual environment
# -----------------------------------------------------------
cd "$DEPLOY_DIR"
info "Setting up Python venv..."
python3.11 -m venv venv
source venv/bin/activate

info "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -e ".[dev]" -q
pip install streamlit edge-tts -q
log "Python environment ready"

# -----------------------------------------------------------
# 4. Environment config
# -----------------------------------------------------------
ENV_FILE="$DEPLOY_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVEOF'
# BookAI Environment Config
# Set your API key here (optional — mock mode works without it)
# key_api=your_api_key_here

# Custom API endpoint (optional)
# BOOKAI_BASE_URL=https://rh486zc.abc-tunnel.us/v1
# BOOKAI_MODEL=WindsurfAPI/gemini-2.5-flash
ENVEOF
    warn "Created .env file at $ENV_FILE — edit to add your API key"
fi

# -----------------------------------------------------------
# 5. Run tests
# -----------------------------------------------------------
info "Running tests to verify installation..."
cd "$DEPLOY_DIR"
source venv/bin/activate
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5
log "Tests passed"

# -----------------------------------------------------------
# 6. Systemd service for Streamlit
# -----------------------------------------------------------
SERVICE_FILE="/etc/systemd/system/bookai.service"
cat > "$SERVICE_FILE" << SVCEOF
[Unit]
Description=BookAI Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DEPLOY_DIR
Environment=PATH=$DEPLOY_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
EnvironmentFile=-$DEPLOY_DIR/.env
ExecStart=$DEPLOY_DIR/venv/bin/streamlit run src/bookai/app.py \\
    --server.port 8501 \\
    --server.address 0.0.0.0 \\
    --server.headless true \\
    --server.enableCORS false \\
    --server.enableXsrfProtection false \\
    --browser.gatherUsageStats false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable bookai
systemctl restart bookai
log "Streamlit service started"

# -----------------------------------------------------------
# 7. Nginx reverse proxy (port 80 → 8501)
# -----------------------------------------------------------
NGINX_CONF="/etc/nginx/sites-available/bookai"
cat > "$NGINX_CONF" << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 200M;

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

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/bookai
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
log "Nginx configured (port 80 → 8501)"

# -----------------------------------------------------------
# 8. Firewall (if ufw active)
# -----------------------------------------------------------
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 22/tcp -q
    ufw allow 80/tcp -q
    ufw allow 443/tcp -q
    ufw allow 8501/tcp -q
    log "Firewall rules added"
fi

# -----------------------------------------------------------
# 9. CLI test
# -----------------------------------------------------------
info "Testing bookai CLI..."
source "$DEPLOY_DIR/venv/bin/activate"
bookai --version 2>/dev/null || bookai --help | head -3

# -----------------------------------------------------------
# Done!
# -----------------------------------------------------------
SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║         BookAI Deploy Thành Công! 🎉    ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  🌐 Dashboard:  ${BOLD}http://$SERVER_IP${NC}"
echo -e "  🌐 Direct:     ${BOLD}http://$SERVER_IP:8501${NC}"
echo -e "  📁 Deploy dir: $DEPLOY_DIR"
echo -e "  ⚙️  Service:    systemctl status bookai"
echo -e "  📋 Logs:       journalctl -u bookai -f"
echo ""
echo -e "  ${YELLOW}Để thêm API key, edit: $ENV_FILE${NC}"
echo -e "  ${YELLOW}Sau đó restart: systemctl restart bookai${NC}"
echo ""
echo -e "  ${BLUE}bookai CLI available at: $DEPLOY_DIR/venv/bin/bookai${NC}"
echo -e "  ${BLUE}Add to PATH: echo 'export PATH=$DEPLOY_DIR/venv/bin:\$PATH' >> ~/.bashrc${NC}"
echo ""
