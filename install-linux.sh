#!/bin/bash
set -euo pipefail

# Aegis — Debian x86_64 first-time setup
# Target: Linux 6.1 cloud-amd64 (Debian 12+)

echo "=== Aegis Install ==="
echo ""

# 1. System packages (Chromium for Selenium, curl for uv installer)
echo "Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl git chromium chromium-driver

# 2. uv
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "uv found ($(uv --version))"
fi

# 3. Python 3.12 via uv
echo ""
echo "Ensuring Python 3.12..."
uv python install 3.12

# 4. Project dependencies
echo ""
echo "Syncing project dependencies..."
uv sync

echo ""
echo "Done. Usage:"
echo "  ./run.sh update   - fetch latest data"
echo "  ./run.sh serve    - start local frontend"
echo "  ./run.sh watch    - continuous update + serve"
echo "  uv run pytest     - run tests"
