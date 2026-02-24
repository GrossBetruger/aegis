#!/bin/bash
set -euo pipefail

# Aegis — Debian x86_64 first-time setup
# Target: Linux 6.1 cloud-amd64 (Debian 12+)

echo "=== Aegis Install ==="
echo ""

# 1. System packages (Chromium for Selenium, curl for uv installer)
echo "Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl git lsof chromium chromium-driver

# 2. Use /mnt/data for heavy storage if available (GCP data disk)
if [[ -d /mnt/data && -w /mnt/data ]]; then
    echo "Data disk detected at /mnt/data — using it for caches and venv"
    mkdir -p /mnt/data/.cache/uv /mnt/data/.local/share/uv

    export UV_CACHE_DIR=/mnt/data/.cache/uv
    export UV_PYTHON_INSTALL_DIR=/mnt/data/.local/share/uv/python

    # Persist env vars in .bashrc
    for var in \
        "export UV_CACHE_DIR=/mnt/data/.cache/uv" \
        "export UV_PYTHON_INSTALL_DIR=/mnt/data/.local/share/uv/python"; do
        grep -qF "$var" ~/.bashrc 2>/dev/null || echo "$var" >> ~/.bashrc
    done
fi

# 3. uv
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env"
    grep -q '.local/bin/env' ~/.bashrc 2>/dev/null || echo 'source $HOME/.local/bin/env' >> ~/.bashrc
else
    echo "uv found ($(uv --version))"
fi

# 4. Python 3.12 via uv
echo ""
echo "Ensuring Python 3.12..."
uv python install 3.12

# 5. Project dependencies (.venv on data disk if available)
if [[ -d /mnt/data && -w /mnt/data ]]; then
    export UV_PROJECT_ENVIRONMENT=/mnt/data/aegis-venv
fi
echo ""
echo "Syncing project dependencies..."
uv sync

echo ""
echo "Done. Usage:"
echo "  ./run.sh update   - fetch latest data"
echo "  ./run.sh serve    - start local frontend"
echo "  ./run.sh watch    - continuous update + serve"
echo "  uv run pytest     - run tests"
