#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

if [[ -d /opt/homebrew/opt/bun/bin ]]; then
  export PATH="/opt/homebrew/opt/bun/bin:$PATH"
fi
if [[ -d /opt/homebrew/opt/uv/bin ]]; then
  export PATH="/opt/homebrew/opt/uv/bin:$PATH"
fi

if command -v ummaya >/dev/null 2>&1; then
  exec ummaya
fi

exec "$ROOT_DIR/bin/ummaya"
