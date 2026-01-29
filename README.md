# Aegis - StrikeRadar

Real-time geopolitical risk monitor tracking USA-Iran tension indicators. Aggregates data from news feeds, aviation tracking, prediction markets, and more.

## Requirements

- **UV** - Fast Python package manager (required)
- Python 3.10+ (managed by UV)

## Installing UV

UV is a fast Python package installer and resolver. Install it with:

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Homebrew (macOS):**
```bash
brew install uv
```

After installation, restart your terminal or run `source ~/.bashrc` (or `~/.zshrc`).

## Quick Start

```bash
# Clone the repo
git clone https://github.com/your-username/aegis.git
cd aegis

# Run the system (updates data + serves frontend)
./run.sh all
```

Then open http://localhost:8000 in your browser.

## Commands

| Command | Description |
|---------|-------------|
| `./run.sh update` | Run the backend data updater (updates npoint.io) |
| `./run.sh serve` | Serve the frontend locally at http://localhost:8000 |
| `./run.sh all` | Run update once, then serve frontend |
| `./run.sh watch` | Run updates every 30 min + serve frontend (like production) |
| `./run.sh kill` | Kill any running background server on port 8000 |

## How It Works

**Backend** (`update_data.py`):
- Fetches Polymarket prediction market odds
- Scrapes news from RSS feeds (BBC, Al Jazeera) and GDELT
- Tracks Brent crude oil prices via Yahoo Finance
- Monitors Google Trends search interest
- Tracks civil aviation and military tanker activity via OpenSky
- Simulates Pentagon pizza activity patterns
- Writes aggregated data to frontend/data.json

**Frontend** (`frontend/`):
- Static HTML/CSS/JS dashboard
- Reads cached data from npoint.io
- Displays risk gauge, signals, and trend charts
- No build step required - pure vanilla JS

**GitHub Actions**:
- `pentagon-pizza.yml` - Runs backend every 30 minutes
- `deploy-pages.yml` - Deploys frontend to GitHub Pages