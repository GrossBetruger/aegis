#!/bin/bash
set -euo pipefail

# Migrate uv caches, Python installs, and venv to /mnt/data
# Run once after attaching the data disk.

echo "=== Migrating to /mnt/data ==="

if [[ ! -d /mnt/data || ! -w /mnt/data ]]; then
    echo "ERROR: /mnt/data not mounted or not writable"
    exit 1
fi

# 1. Set up directories on data disk
echo "Creating directories on /mnt/data..."
mkdir -p /mnt/data/.cache/uv /mnt/data/.local/share/uv

# 2. Add env vars to .bashrc (idempotent)
echo "Updating ~/.bashrc..."
for var in \
    "export UV_CACHE_DIR=/mnt/data/.cache/uv" \
    "export UV_PYTHON_INSTALL_DIR=/mnt/data/.local/share/uv/python" \
    "export UV_PROJECT_ENVIRONMENT=/mnt/data/aegis-venv"; do
    grep -qF "$var" ~/.bashrc 2>/dev/null || echo "$var" >> ~/.bashrc
done

# 3. Export for this session
export UV_CACHE_DIR=/mnt/data/.cache/uv
export UV_PYTHON_INSTALL_DIR=/mnt/data/.local/share/uv/python
export UV_PROJECT_ENVIRONMENT=/mnt/data/aegis-venv

# 4. Remove old caches from boot disk
echo "Removing old caches from boot disk..."
rm -rf ~/.cache/uv ~/.local/share/uv/python .venv

# 5. Pull latest code and re-sync
echo "Pulling latest code..."
cd ~/aegis
git pull

echo "Installing Python 3.12 (on data disk)..."
uv python install 3.12

echo "Syncing dependencies (venv on data disk)..."
uv sync

# 6. Report
echo ""
echo "=== Done ==="
df -h / /mnt/data
echo ""
echo "Boot disk and data disk usage shown above."
echo "All heavy storage now lives on /mnt/data."
