# MRAYEH

**Sales Tracking & Planning Platform for Food Production**

A containerized platform for tracking sales, orders, and inventory across multiple channels for a food production business.

## Quick Start

```bash
# Clone
git clone https://github.com/djwawa/mrayeh.git
cd mrayeh

# Configure
cp config/env.example .env
# Edit .env with your API keys

# Run
docker compose up -d

# View logs
docker compose logs -f

# Access
open http://localhost:8000
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MRAYEH ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   DATA SOURCES                    DRIVERS                   DATABASE        │
│   ────────────                    ───────                   ────────        │
│                                                                             │
│   ┌──────────────┐               ┌─────────────┐                            │
│   │ Google Sheet │──────────────▶│ Mezze Sheet │──┐                         │
│   │ (Mezze)      │               │ Driver      │  │      ┌──────────────┐   │
│   └──────────────┘               └─────────────┘  │      │              │   │
│                                                   ├─────▶│   DuckDB     │   │
│   ┌──────────────┐               ┌─────────────┐  │      │              │   │
│   │ PSFH Portal  │──────────────▶│ LFM Scraper │──┤      │  (Embedded)  │   │
│   │ (LFM)        │               │ Driver      │  │      │              │   │
│   └──────────────┘               └─────────────┘  │      └──────┬───────┘   │
│                                                   │             │           │
│   ┌──────────────┐               ┌─────────────┐  │             │           │
│   │ Tony's Portal│──────────────▶│ Tony's      │──┤             ▼           │
│   │ (TBD)        │               │ Driver      │  │      ┌──────────────┐   │
│   └──────────────┘               └─────────────┘  │      │              │   │
│                                                   │      │  FastAPI     │   │
│   ┌──────────────┐               ┌─────────────┐  │      │  + REST API  │   │
│   │ Email Orders │──────────────▶│ Gmail       │──┘      │              │   │
│   │              │               │ Driver      │         └──────┬───────┘   │
│   └──────────────┘               └─────────────┘                │           │
│                                                                 ▼           │
│                                                          ┌──────────────┐   │
│                                                          │  Dashboard   │   │
│                                                          │  (Web UI)    │   │
│                                                          └──────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Runtime** | Python 3.12 | Application code |
| **Database** | DuckDB | Embedded analytics database |
| **API** | FastAPI | REST API & web server |
| **Container** | Docker | Portable deployment |
| **Scheduler** | APScheduler | Periodic data pulls |
| **Browser** | Playwright | Portal scraping (when needed) |
| **Google APIs** | Sheets, Drive, Gmail | Data sources |

## Project Structure

```
mrayeh/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── drivers/             # Data source drivers
│   │   ├── __init__.py
│   │   └── google_sheets_driver.py
│   └── helpers/             # Shared utilities
│       └── __init__.py
├── config/
│   └── env.example          # Environment template
├── data/                    # DuckDB database (gitignored)
├── scripts/                 # Utility scripts
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `app` | 8000 | Main API server |
| `scheduler` | - | Background job runner |
| `browser` | - | Playwright worker (optional) |

## Configuration

Copy `config/env.example` to `.env` and configure:

```bash
GOOGLE_API_KEY=your-key-here
MEZZE_SHEET_ID=your-sheet-id
```

## Development

```bash
# Local development (without Docker)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run API server
python -m src.main

# Run tests
pytest
```

## License

Private - Mamnoon Restaurant Group
