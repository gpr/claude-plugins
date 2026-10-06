#!/bin/bash
# Render CLI deployment script for custom CI/CD or manual deployments
# Usage: ./deploy-script.sh <environment> <commit-sha>
# Example: ./deploy-script.sh staging abc123def456

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/deploy.log"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Validate arguments
if [ $# -lt 1 ]; then
    log_error "Usage: $0 <environment> [commit-sha]"
    log_error "Environments: staging, production"
    exit 1
fi

ENVIRONMENT="$1"
COMMIT_SHA="${2:-$(git rev-parse HEAD)}"

log_info "Starting deployment to ${ENVIRONMENT} environment"
log_info "Commit SHA: ${COMMIT_SHA}"

# Load environment-specific configuration
case "$ENVIRONMENT" in
    staging)
        SERVICE_ID="${RENDER_SERVICE_ID_STAGING:-}"
        API_KEY="${RENDER_API_KEY_STAGING:-}"
        ;;
    production)
        SERVICE_ID="${RENDER_SERVICE_ID_PRODUCTION:-}"
        API_KEY="${RENDER_API_KEY_PRODUCTION:-}"
        ;;
    *)
        log_error "Invalid environment: ${ENVIRONMENT}"
        log_error "Valid options: staging, production"
        exit 1
        ;;
esac

# Validate required environment variables
if [ -z "$SERVICE_ID" ]; then
    log_error "RENDER_SERVICE_ID_${ENVIRONMENT^^} environment variable is not set"
    exit 1
fi

if [ -z "$API_KEY" ]; then
    log_error "RENDER_API_KEY_${ENVIRONMENT^^} environment variable is not set"
    exit 1
fi

# Check if Render CLI is installed
if ! command -v render &> /dev/null; then
    log_error "Render CLI is not installed"
    log_info "Install with: curl -fsSL https://install.render.com/latest | bash"
    exit 1
fi

log_info "Render CLI version: $(render --version)"

# Set Render API key for this session
export RENDER_API_KEY="$API_KEY"

# Confirm deployment for production
if [ "$ENVIRONMENT" = "production" ]; then
    log_warn "You are about to deploy to PRODUCTION"
    read -p "Are you sure you want to continue? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Deployment cancelled"
        exit 0
    fi
fi

# Trigger deployment
log_info "Triggering deployment..."

if render deploys create "$SERVICE_ID" \
    --commit "$COMMIT_SHA" \
    --wait \
    --confirm >> "$LOG_FILE" 2>&1; then

    log_info "✅ Deployment to ${ENVIRONMENT} completed successfully!"
    log_info "Service ID: ${SERVICE_ID}"
    log_info "Commit: ${COMMIT_SHA}"

    # Optional: Get deployment details
    log_info "Fetching deployment history..."
    render deploys list "$SERVICE_ID" | head -n 10

    exit 0
else
    log_error "❌ Deployment to ${ENVIRONMENT} failed!"
    log_error "Check logs at: ${LOG_FILE}"
    log_error "View service logs with: render logs ${SERVICE_ID}"

    exit 1
fi

# Setup instructions:
#
# 1. Make script executable:
#    chmod +x deploy-script.sh
#
# 2. Set environment variables:
#    export RENDER_SERVICE_ID_STAGING="srv-abc123"
#    export RENDER_API_KEY_STAGING="rnd_your_staging_key"
#    export RENDER_SERVICE_ID_PRODUCTION="srv-xyz789"
#    export RENDER_API_KEY_PRODUCTION="rnd_your_production_key"
#
# 3. Run deployment:
#    ./deploy-script.sh staging           # Deploy current HEAD to staging
#    ./deploy-script.sh staging abc123    # Deploy specific commit to staging
#    ./deploy-script.sh production        # Deploy current HEAD to production
#
# 4. For persistent configuration, add to ~/.bashrc or ~/.zshrc:
#    export RENDER_SERVICE_ID_STAGING="srv-abc123"
#    export RENDER_API_KEY_STAGING="rnd_your_staging_key"
#    export RENDER_SERVICE_ID_PRODUCTION="srv-xyz789"
#    export RENDER_API_KEY_PRODUCTION="rnd_your_production_key"
