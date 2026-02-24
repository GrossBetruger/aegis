#!/bin/bash
set -euo pipefail

[[ -f "$HOME/.local/bin/env" ]] && source "$HOME/.local/bin/env"

if [[ -d /mnt/data && -w /mnt/data ]]; then
    export UV_CACHE_DIR=/mnt/data/.cache/uv
fi

echo "=== Cleaning disk ==="
sudo apt-get clean
sudo journalctl --vacuum-size=50M
uv cache clean --force
echo ""
df -h /
[[ -d /mnt/data ]] && df -h /mnt/data
echo "Done."
