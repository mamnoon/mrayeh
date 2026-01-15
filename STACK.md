# MRAYEH Stack Definition

## Core Principles

1. **Container-first** — No local environment dependencies
2. **Driver architecture** — Each data source has isolated driver with normalization
3. **Embedded database** — DuckDB for portable analytics
4. **Lambda-style** — Stateless functions, persistence via database
5. **Agent-assisted** — LLM inference for pattern detection where ROI is clear

---

## Technology Stack

### Runtime & Language

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.12 | Rich ecosystem for data, APIs, automation |
| **Container** | Docker | Portable, reproducible deployments |
| **Orchestration** | Docker Compose | Simple multi-service management |

### Data Layer

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Database** | DuckDB | Embedded, fast analytics, SQL, no server needed |
| **Format** | Native DuckDB | Single file, portable, ACID |
| **Schema** | Typed tables | See DDL in docs |

### API Layer

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Framework** | FastAPI | Modern, async, auto-docs, type-safe |
| **Server** | Uvicorn | High-performance ASGI |
| **Validation** | Pydantic | Data validation via types |

### Data Ingestion

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Google APIs** | google-api-python-client | Sheets, Drive, Gmail access |
| **Browser automation** | Playwright | Portal scraping when no API |
| **Scheduling** | APScheduler | Cron-like job scheduling |
| **HTTP** | httpx | Async HTTP client |

### Future Considerations

| Component | Options | Notes |
|-----------|---------|-------|
| **Frontend** | HTMX + Alpine.js, or React | TBD based on complexity |
| **LLM inference** | OpenAI API, local Ollama | For pattern detection, email parsing |
| **Hosting** | Fly.io, Railway, AWS ECS | Container-native platforms |

---

## Driver Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DRIVER ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         SOURCE DRIVERS                              │   │
│   │                                                                     │   │
│   │   Each driver:                                                      │   │
│   │   • Connects to ONE data source                                     │   │
│   │   • Handles authentication                                          │   │
│   │   • Fetches raw data                                                │   │
│   │   • Normalizes to common schema                                     │   │
│   │   • Reports warnings/errors                                         │   │
│   │                                                                     │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│   │   │ GoogleSheet │  │ LFM Portal  │  │ Tony's      │  │ Gmail     │  │   │
│   │   │ Driver      │  │ Driver      │  │ Driver      │  │ Driver    │  │   │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │   │
│   │          │                │                │               │        │   │
│   └──────────┼────────────────┼────────────────┼───────────────┼────────┘   │
│              │                │                │               │            │
│              ▼                ▼                ▼               ▼            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      HELPER SERVICES                                │   │
│   │                                                                     │   │
│   │   Shared utilities available to all drivers:                        │   │
│   │   • Date parsing                                                    │   │
│   │   • Customer name normalization                                     │   │
│   │   • Product mapping                                                 │   │
│   │   • Quantity parsing                                                │   │
│   │   • PO# extraction                                                  │   │
│   │                                                                     │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    NORMALIZATION PIPELINE                           │   │
│   │                                                                     │   │
│   │   • Deduplication                                                   │   │
│   │   • Entity resolution (same customer across sources)                │   │
│   │   • Canonical transforms                                            │   │
│   │   • Cross-source joins (e.g., order → PO → invoice)                 │   │
│   │                                                                     │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         DUCKDB                                      │   │
│   │                    (Canonical Data Model)                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model (Summary)

### Core Entities

| Entity | Description |
|--------|-------------|
| **Account** | Customer/store (leaf node) |
| **AccountGroup** | Hierarchy container (chain, distributor) |
| **Product** | SKU with pricing, packaging info |
| **Order** | Single order with header info |
| **OrderLine** | Line item (product × quantity × unit) |
| **Invoice** | Billing document |
| **Payment** | Payment record |

### Analysis Entities

| Entity | Description |
|--------|-------------|
| **TimeSeries** | Pre-computed aggregates by time period |
| **SeasonalEvent** | Holidays, seasons, special events |
| **Promo** | Promotional campaigns |

---

## Agent Integration Points

Where LLM inference adds clear ROI:

| Use Case | Input | Output | ROI Justification |
|----------|-------|--------|-------------------|
| **Email order parsing** | Raw email text | Structured order | High variability, >10 rules to replicate |
| **Customer name resolution** | Fuzzy names | Canonical entity | Pattern matching across typos |
| **Anomaly detection** | Order patterns | Alerts | Identify unusual orders |
| **Portal navigation recovery** | DOM changes | Updated selectors | Self-healing scrapers |

---

## Deployment Targets

| Environment | Platform | Notes |
|-------------|----------|-------|
| **Local dev** | Docker Desktop | Full stack locally |
| **Local prod** | Mac Mini / NAS | Always-on home server |
| **Cloud** | Fly.io / Railway | Container-native, easy scaling |
| **Enterprise** | AWS ECS / GCP Run | If scale demands |
