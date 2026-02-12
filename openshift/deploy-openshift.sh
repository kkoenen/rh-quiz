#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# deploy-openshift.sh
#
# Deploys RH Quiz to an OpenShift namespace.
#
# Prerequisites:
#   - oc CLI logged in
#   - Target namespace/project selected (oc project <name>)
#
# Usage:
#   ./deploy-openshift.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OC_DIR="${SCRIPT_DIR}"

# Pre-checks
command -v oc &>/dev/null || err "oc CLI not found. Install it first."
oc whoami &>/dev/null || err "Not logged in. Run: oc login <cluster>"

NAMESPACE=$(oc project -q 2>/dev/null)
log "Deploying to namespace: $NAMESPACE"

# Step 1: Apply manifests (secret, pvc, build, deployment, service, route)
log "Applying OpenShift manifests..."
for f in "${OC_DIR}"/0*.yaml; do
  echo "  Applying $(basename "$f")..."
  oc apply -f "$f"
done

# Step 2: Trigger binary build from project root
log "Starting binary build from project source..."
cd "$PROJECT_DIR"
oc start-build rh-quiz --from-dir=. --follow --wait

# Step 3: Wait for rollout
log "Waiting for deployment rollout..."
oc rollout status deployment/rh-quiz --timeout=120s

# Step 4: Get route
ROUTE_HOST=$(oc get route rh-quiz -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🎩 RH Quiz deployed to OpenShift!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Namespace:  ${YELLOW}${NAMESPACE}${NC}"
if [[ -n "$ROUTE_HOST" ]]; then
echo -e "  App URL:    ${YELLOW}https://${ROUTE_HOST}${NC}"
fi
echo ""
echo -e "  Useful commands:"
echo -e "    oc logs -f deployment/rh-quiz"
echo -e "    oc get pods -l app=rh-quiz"
echo -e "    oc rsh deployment/rh-quiz"
echo ""
