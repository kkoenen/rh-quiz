#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# deploy-proxmox.sh
#
# Creates a Proxmox LXC container, installs Docker inside it,
# and deploys the RH Quiz application.
#
# Run this on the Proxmox host (as root).
#
# Usage:
#   chmod +x deploy-proxmox.sh
#   ./deploy-proxmox.sh
#
# Configurable variables are at the top of this script.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration (edit these) ───────────────────────────────
CTID="${CTID:-201}"                          # Container ID
CT_HOSTNAME="${CT_HOSTNAME:-rh-quiz}"        # Container hostname
CT_MEMORY="${CT_MEMORY:-2048}"               # RAM in MB
CT_SWAP="${CT_SWAP:-512}"                    # Swap in MB
CT_DISK="${CT_DISK:-8}"                      # Root disk in GB
CT_CORES="${CT_CORES:-2}"                    # CPU cores
CT_BRIDGE="${CT_BRIDGE:-vmbr0}"              # Network bridge
CT_IP="${CT_IP:-dhcp}"                       # IP: "dhcp" or "192.168.1.100/24"
CT_GW="${CT_GW:-}"                           # Gateway (required if static IP)
CT_STORAGE="${CT_STORAGE:-local-lvm}"        # Proxmox storage pool
CT_TEMPLATE="${CT_TEMPLATE:-local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst}"
CT_NAMESERVER="${CT_NAMESERVER:-8.8.8.8}"    # DNS

APP_PORT="${APP_PORT:-8000}"                 # Port to expose on the host
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://192.168.1.153:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-mistral:7b-instruct}"
ADMIN_TOKEN="${ADMIN_TOKEN:-SECRET}"

# Repo (if cloning from GitHub — leave empty to copy local files)
GIT_REPO="${GIT_REPO:-}"
# Local path to the rh-quiz project (if not using git)
LOCAL_PROJECT="${LOCAL_PROJECT:-$(cd "$(dirname "$0")" && pwd)}"

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ── Pre-checks ──────────────────────────────────────────────
[[ $(id -u) -eq 0 ]] || err "Run this script as root on the Proxmox host."
command -v pct &>/dev/null || err "pct not found — are you on a Proxmox host?"

# Check if CTID already exists
if pct status "$CTID" &>/dev/null; then
  warn "Container $CTID already exists."
  read -rp "Destroy and recreate? (y/N): " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    pct stop "$CTID" 2>/dev/null || true
    pct destroy "$CTID" --purge
    log "Destroyed existing container $CTID"
  else
    err "Aborted."
  fi
fi

# Auto-detect template if default doesn't exist
if ! pveam list local 2>/dev/null | grep -q "$(echo "$CT_TEMPLATE" | sed 's|local:vztmpl/||')"; then
  DETECTED=$(pveam list local 2>/dev/null | grep "debian-12" | head -1 | awk '{print $1}')
  if [[ -n "$DETECTED" ]]; then
    warn "Configured template not found. Using detected: $DETECTED"
    CT_TEMPLATE="$DETECTED"
  else
    warn "No Debian 12 template found. Downloading latest..."
    AVAILABLE=$(pveam available --section system 2>/dev/null | grep "debian-12" | tail -1 | awk '{print $2}')
    if [[ -n "$AVAILABLE" ]]; then
      pveam download local "$AVAILABLE" || err "Failed to download template."
      CT_TEMPLATE="local:vztmpl/${AVAILABLE}"
    else
      err "Cannot find a Debian 12 template. Download one manually: pveam available --section system"
    fi
  fi
fi
log "Using template: $CT_TEMPLATE"

# ── Step 1: Create LXC Container ────────────────────────────
log "Creating LXC container $CTID ($CT_HOSTNAME)..."

# Build network string
NET_STR="name=eth0,bridge=${CT_BRIDGE}"
if [[ "$CT_IP" == "dhcp" ]]; then
  NET_STR="${NET_STR},ip=dhcp"
else
  NET_STR="${NET_STR},ip=${CT_IP}"
  [[ -n "$CT_GW" ]] && NET_STR="${NET_STR},gw=${CT_GW}"
fi

pct create "$CTID" "$CT_TEMPLATE" \
  --hostname "$CT_HOSTNAME" \
  --memory "$CT_MEMORY" \
  --swap "$CT_SWAP" \
  --cores "$CT_CORES" \
  --rootfs "${CT_STORAGE}:${CT_DISK}" \
  --net0 "$NET_STR" \
  --nameserver "$CT_NAMESERVER" \
  --unprivileged 0 \
  --features nesting=1,keyctl=1 \
  --onboot 1 \
  --start 0

log "Container $CTID created."

# ── Step 2: Start Container ─────────────────────────────────
log "Starting container..."
pct start "$CTID"
sleep 5

# Wait for network
for i in $(seq 1 30); do
  if pct exec "$CTID" -- ping -c1 -W2 8.8.8.8 &>/dev/null; then
    break
  fi
  sleep 2
done
pct exec "$CTID" -- ping -c1 -W5 8.8.8.8 &>/dev/null || err "Container has no network connectivity."
log "Container is up and has network."

# ── Step 3: Install Docker ───────────────────────────────────
log "Installing Docker inside container..."

pct exec "$CTID" -- bash -c '
  set -e
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg git >/dev/null 2>&1

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null 2>&1

  systemctl enable docker
  systemctl start docker
'

log "Docker installed."

# ── Step 4: Deploy Application ───────────────────────────────
log "Deploying RH Quiz application..."

if [[ -n "$GIT_REPO" ]]; then
  # Clone from GitHub
  pct exec "$CTID" -- bash -c "
    cd /opt
    git clone ${GIT_REPO} rh-quiz
    cd rh-quiz
  "
else
  # Copy local files into container
  TMPTAR="/tmp/rh-quiz-deploy-$$.tar.gz"
  tar -czf "$TMPTAR" -C "$LOCAL_PROJECT" \
    --exclude='.git' \
    --exclude='data' \
    --exclude='__pycache__' \
    --exclude='.venv' \
    --exclude='.env' \
    .
  pct push "$CTID" "$TMPTAR" /tmp/rh-quiz.tar.gz
  rm -f "$TMPTAR"

  pct exec "$CTID" -- bash -c '
    mkdir -p /opt/rh-quiz
    tar -xzf /tmp/rh-quiz.tar.gz -C /opt/rh-quiz
    rm -f /tmp/rh-quiz.tar.gz
  '
fi

# Write .env file
pct exec "$CTID" -- bash -c "
cat > /opt/rh-quiz/.env << 'ENVEOF'
OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
OLLAMA_MODEL=${OLLAMA_MODEL}
DB_PATH=/data/quiz.db
APP_HOST=0.0.0.0
APP_PORT=8000
ADMIN_TOKEN=${ADMIN_TOKEN}
ENVEOF
"

log "Application files deployed."

# ── Step 5: Build & Start ────────────────────────────────────
log "Building and starting container..."

pct exec "$CTID" -- bash -c '
  cd /opt/rh-quiz
  docker compose up -d --build
'

log "Application is starting..."

# ── Step 6: Verify ───────────────────────────────────────────
sleep 8
HEALTH=$(pct exec "$CTID" -- curl -sf http://localhost:8000/health 2>/dev/null || echo "FAIL")

if echo "$HEALTH" | grep -q '"ok"'; then
  log "Health check passed!"
else
  warn "Health check returned: $HEALTH (app may still be starting)"
fi

# Get container IP
CT_ACTUAL_IP=$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}')

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🎩 RH Quiz deployed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Container ID:   ${YELLOW}${CTID}${NC}"
echo -e "  Hostname:       ${YELLOW}${CT_HOSTNAME}${NC}"
echo -e "  Container IP:   ${YELLOW}${CT_ACTUAL_IP:-unknown}${NC}"
echo -e "  App URL:        ${YELLOW}http://${CT_ACTUAL_IP:-<CONTAINER_IP>}:${APP_PORT}${NC}"
echo -e "  Ollama:         ${YELLOW}${OLLAMA_BASE_URL}${NC}"
echo -e "  Model:          ${YELLOW}${OLLAMA_MODEL}${NC}"
echo -e "  Admin Token:    ${YELLOW}${ADMIN_TOKEN}${NC}"
echo ""
echo -e "  Manage:"
echo -e "    pct enter ${CTID}"
echo -e "    cd /opt/rh-quiz && docker compose logs -f"
echo ""
