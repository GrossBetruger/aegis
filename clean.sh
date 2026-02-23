#!/bin/bash
set -euo pipefail

echo "=== Cleaning disk ==="
sudo apt-get clean
sudo journalctl --vacuum-size=50M
uv cache clean --force
echo ""
df -h /
echo "Done."
