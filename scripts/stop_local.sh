#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="stop_local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local_dev_common.sh
source "${SCRIPT_DIR}/local_dev_common.sh"
cd "${REPO_ROOT}"

require_command docker "Install Docker Desktop if you need to stop Compose-managed services."
docker compose down

cat <<'EOF'
Swiss Lawyer services stopped.
Local data has been preserved.
EOF
