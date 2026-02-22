#!/bin/bash
set -e

# StrikeRadar — macOS first-time setup
# Installs uv, Python >=3.10, and all project dependencies.

echo "=== StrikeRadar Install ==="
echo ""

# 1. Homebrew (needed for uv)
if ! command -v brew &>/dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon Macs
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✅ Homebrew found"
fi

# 2. uv (Python package/project manager)
if ! command -v uv &>/dev/null; then
    echo "📦 Installing uv..."
    brew install uv
else
    echo "✅ uv found ($(uv --version))"
fi

# 3. Python (uv manages its own Python, but ensure >=3.10 is available)
echo ""
echo "📦 Ensuring Python >=3.10 via uv..."
uv python install 3.12

# 4. Project dependencies (from pyproject.toml)
echo ""
echo "📦 Syncing project dependencies..."
uv sync --all-extras

echo ""
echo "=== Installed packages ==="
echo "  Runtime:  requests, pytrends, beautifulsoup4, selenium, transformers, torch"
echo "  Dev:      pytest"
echo ""
echo "✅ All done! Run the project with:"
echo "   ./run.sh update   — fetch latest data"
echo "   ./run.sh serve    — start local frontend"
echo "   ./run.sh watch    — continuous update + serve"
echo "   uv run pytest     — run tests"
