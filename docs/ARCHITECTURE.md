# ARIA System Architecture

> **ARIA** — Agentic Retail Intelligence & Analytics Platform  
> A hyper-local agent-based simulation platform for Malaysian micro-business decision support.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                              │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌────────────────┐   │
│  │   Auth   │  │  Onboarding  │  │  ChatPanel │  │   Dashboard    │   │
│  │  Modal   │  │    Flow      │  │  (Scenario │  │ (Graph + Feed  │   │
│  │          │  │  (4 steps)   │  │   Input)   │  │  + Metrics)    │   │
│  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └───────┬────────┘   │
│       │                │                │                  │            │
│       │ REST           │ REST           │ REST             │ REST + SSE │
└───────┼────────────────┼────────────────┼──────────────────┼────────────┘
        │                │                │                  │
┌───────┴────────────────┴────────────────┴──────────────────┴────────────┐
│                     API LAYER (FastAPI — single server)                 │
│                                                                         │
│  /api/auth/*          /api/business/*       /api/simulation/*           │
│  (register, login)    (analyze, profile)    (suggest, start, stream,    │
│                                              pause, cancel, history)    │
│  /api/demographics/*  /api/holidays         /api/chat/message           │
│  (DOSM district data) (Malaysia calendar)   (persist messages)          │
│                                                                         │
│  Note: SSE stream (/api/simulation/{id}/stream) is a FastAPI endpoint   │
│  using StreamingResponse — same server, not a separate service.         │
└────────┬───────────────────┬────────────────────────┬───────────────────┘
         │                   │                        │
┌────────▼────────┐  ┌──────▼──────────┐  ┌──────────▼──────────────────┐
│  DATABASE LAYER │  │   AGENT LAYER   │  │     SIMULATION LAYER        │
│  (Supabase)     │  │                 │  │                             │
│                 │  │ CustomerProfiler│  │  Mesa Model + LLM Brain     │
│  Users          │  │ ScenarioAgent   │  │  CustomerAgent              │
│  Profiles       │  │ ArchetypeGen    │  │  Peer Influence             │
│  Simulations    │  │                 │  │                             │
│  Events         │  └────────┬────────┘  └──────────┬──────────────────┘
│  Analysis       │           │                      │
└─────────────────┘  ┌────────▼────────────────────────▼────────────────┐
                     │              LLM LAYER (Ollama)                   │
                     │                                                   │
                     │  OllamaClient → qwen2.5:7b (local)                │
                     │  Prompts (Malaysian context)                      │
                     │  Parsers (robust JSON extraction)                 │
                     └───────────────────────────────────────────────────┘
                     
┌────────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                                │
│                                                                        │
│  ┌─────────────────────┐        ┌──────────────────────────────────┐  │
│  │  DOSM (Dept. of     │        │  newsdata.io (optional)          │  │
│  │  Statistics Malaysia)│        │  Malaysian economic news         │  │
│  │  - Age distribution  │        │  Industry-specific context       │  │
│  │  - Income data       │        │                                  │  │
│  │  - Spending patterns │        │                                  │  │
│  └─────────────────────┘        └──────────────────────────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Malaysia Calendar API (mycal-api, no key required)              │  │
│  │  - Public holidays (49 for 2026, federal + state-specific)       │  │
│  │  - School holidays (Kumpulan B for Penang)                       │  │
│  │  - Exam schedules (SPM, STPM, MUET, PT3)                        │  │
│  │  - Triggered by keyword detection (holiday, raya, school, etc.)  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  POPULATION LAYER (IPF Engine)                                   │  │
│  │  Iterative Proportional Fitting → Synthetic Population           │  │
│  │  Joint age-income distributions matching DOSM marginals          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Layer Breakdown

### 1. Frontend (Next.js App Router)

| Component | Purpose |
|-----------|---------|
| `AuthModal` | Email/password registration and login |
| `OnboardingFlow` | 4-step business setup (info → location → AI analysis → review) |
| `ChatPanel` | Conversational scenario input, template scenarios, simulation launch |
| `SimulationSettings` | Demographic constraints (income, age, B2B size) |
| `DashboardPage` | Main view: force-directed agent graph + activity feed + metrics |
| `InfluenceGraph` | SVG force-directed visualization of agent network |
| `ActivityFeed` | Real-time stream of agent decisions during simulation |
| `HistorySidebar` | Past simulation history with restore/delete |
| `useSim` | Custom hook managing simulation state, SSE streaming, history |

**Data flow:** The frontend communicates with the backend via REST endpoints and receives real-time simulation updates through Server-Sent Events (SSE).

---

### 2. API Layer (FastAPI)

**Entry point:** `aria/api/main.py`

| Endpoint Group | Endpoints | Purpose |
|----------------|-----------|---------|
| Auth | `POST /api/auth/register`, `POST /api/auth/login` | User authentication |
| Business | `POST /api/business/analyze`, `POST /api/business/profile`, `GET/PUT /api/business/profile/{id}` | Profile creation with AI customer inference |
| Demographics | `GET /api/demographics/{district}` | DOSM demographic data for a district |
| Holidays | `GET /api/holidays` | Malaysia public holidays, school holidays, exams |
| Simulation | `POST /api/simulation/suggest` | LLM-powered scenario generation |
| Simulation | `POST /api/simulation/start` | Launch simulation, generate agents |
| Simulation | `GET /api/simulation/{id}/stream` | SSE stream of real-time events |
| Simulation | `POST /api/simulation/{id}/pause`, `/resume`, `/cancel` | Simulation control |
| Simulation | `GET /api/simulation/history/{profile_id}` | Past simulation results |
| Chat | `POST /api/chat/message` | Persist chat messages |
| Health | `GET /api/health` | System health check |

---

### 3. Agent Layer

Three specialized agents handle different stages of the user journey:

#### CustomerProfiler (`aria/agents/customer_profiler.py`)
- **Trigger:** User submits business info during onboarding
- **Input:** Business name, type, location, USPs
- **Process:** LLM infers customer segments (B2C/B2B/HYBRID)
- **Output:** Target customers, income levels, price ranges, transaction patterns

#### ScenarioSuggestionAgent (`aria/agents/scenario_suggestion.py`)
- **Trigger:** User asks a "what-if" question in chat
- **Input:** User question + business profile + optional real-world context
- **Process:**
  1. Optionally gathers context (News API + DOSM economic data)
  2. Builds prompt with business context and gathered data
  3. LLM generates 2-5 ranked scenarios
- **Output:** Scenario objects with parameters, relevance scores, expected impact

#### ArchetypeGenerator (`aria/agents/archetype_generator.py`)
- **Trigger:** Simulation start
- **Input:** Business profile + demographic constraints
- **Process:** Uses SyntheticPopulationGenerator (IPF) to create agents
- **Output:** Agent list with demographics, spending patterns, personality traits

---

### 4. Simulation Layer (Mesa + LLM Hybrid)

The simulation uses the **Mesa** agent-based modeling framework enhanced with LLM decision-making.

#### ARIAModel (`aria/simulation/mesa_model.py`)
- Mesa `Model` subclass managing the simulation lifecycle
- Handles agent scheduling, metric collection, week progression
- Coordinates the two-phase decision process

#### CustomerAgent (`aria/simulation/customer_agent.py`)
- Mesa `Agent` subclass representing individual customers
- Holds demographic data (age, income, location)
- Maintains decision history and peer connections
- Tracks spending, loyalty, and satisfaction

#### LLMAgentBrain (`aria/simulation/llm_agent_brain.py`)
- Core LLM integration for agent intelligence
- **Profile Generation:** Creates rich 3-5 sentence personality profiles
- **Decision Making:** Generates visit/skip/churn decisions with reasoning
- **B2B Support:** Separate procurement-focused decision logic
- **Peer Influence:** Processes peer messages and adjusts decisions

#### Two-Phase Decision Process

```
┌─────────────────────────────────────────────────────────┐
│                    SIMULATION WEEK                        │
│                                                          │
│  Phase 1: INDEPENDENT DECISIONS                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  For each agent:                                   │  │
│  │  1. Build context (profile + scenario + history)   │  │
│  │  2. LLM generates decision (visit/skip/churn)     │  │
│  │  3. Extract reasoning message                      │  │
│  │  4. Stream decision to frontend                    │  │
│  └────────────────────────────────────────────────────┘  │
│                          ↓                               │
│  Phase 2: PEER INFLUENCE                                 │
│  ┌────────────────────────────────────────────────────┐  │
│  │  For each susceptible agent:                       │  │
│  │  1. Gate check (income-based or personality-based) │  │
│  │  2. Collect peer messages from connected agents    │  │
│  │  3. LLM reconsiders decision given peer input      │  │
│  │  4. Stream updated decision if changed             │  │
│  └────────────────────────────────────────────────────┘  │
│                          ↓                               │
│  METRICS AGGREGATION                                     │
│  Total visits, revenue, churn rate, influence changes    │
└─────────────────────────────────────────────────────────┘
```

---

### 5. Population Layer (IPF Synthetic Population)

#### IPFEngine (`aria/population/ipf_engine.py`)
- Implements Iterative Proportional Fitting algorithm
- Generates joint age-income probability distributions
- Matches DOSM marginal totals for the business's district
- Validates convergence with confidence scoring
- Supports demographic constraints (filter to specific income/age groups)

#### SyntheticPopulationGenerator (`aria/population/synthetic_population.py`)
- Orchestrates population creation:
  1. Fetches DOSM demographics for business location
  2. Runs IPF to get joint distribution
  3. Samples agents from distribution
  4. Assigns detailed attributes (spending, loyalty, payment preferences)
- Supports B2C, B2B, and HYBRID populations
- Falls back to simple random sampling if IPF fails

```
DOSM Data (district) → IPF Engine → Joint Distribution → Agent Sampling
                                                              ↓
                                          Detailed Attributes Assignment
                                          (spending, loyalty, personality)
```

---

### 6. Database Layer (Supabase PostgreSQL)

**Client:** `aria/database/supabase_client.py` (REST API client)

#### Schema (Core Tables)

| Table | Purpose |
|-------|---------|
| `users` | User accounts (email, password hash) |
| `business_profiles` | Business info + customer profile columns |
| `archetypes` | Generated customer archetypes per profile |
| `scenarios` | Simulation scenarios with parameters |
| `simulations` | Simulation runs with status tracking |
| `simulation_events` | Individual agent decisions per week |
| `agent_interactions` | Agent-to-agent influence events |
| `simulation_analysis` | Aggregated results and insights |
| `market_impact_reports` | Generated PDF/CSV reports |
| `error_logs` | System error tracking |

#### Data Access Pattern
- All DB operations go through `SupabaseClient` (REST API over HTTP)
- SQLAlchemy models define schema but aren't used for direct ORM queries
- Supabase handles auth, RLS, and connection pooling

---

### 7. LLM Layer (Ollama)

**Model:** `qwen2.5:7b` (local, configurable)

#### OllamaClient (`aria/llm/ollama_client.py`)
- Async HTTP client for Ollama's REST API
- Retry logic with exponential backoff (3 attempts)
- 3-minute timeout for reasoning-heavy prompts
- Supports both `generate` and `chat` endpoints

#### Prompts (`aria/llm/prompts.py`)
- Structured templates with Malaysian cultural context
- Business profile synthesis
- Scenario suggestion (with/without real-world context)
- All prompts enforce JSON-only output

#### Parsers (`aria/llm/parsers.py`)
- Robust JSON extraction from LLM responses
- Handles: markdown fences, `<think>` tags, truncated JSON
- Brace-matching fallback for incomplete responses
- Repair logic for common LLM JSON mistakes

---

### 8. External Integrations

#### DOSM Client (`aria/external/dosm.py`)
- **Source:** DOSM Open Data parquet file + local income JSON
- **Data:** Age distribution (5 Penang districts), income distribution, spending patterns
- **Usage:** Provides marginal distributions for IPF, demographic context for prompts

#### News API Client (`aria/external/news_api.py`)
- **Source:** newsdata.io
- **Data:** Malaysian economic news, industry-specific articles
- **Usage:** Optional real-world context for scenario generation
- **Behavior:** Graceful fallback if API key not configured

#### Malaysia Calendar Client (`aria/external/malaysia_calendar.py`)
- **Source:** Malaysia Calendar API (mycal-api on Cloudflare Workers)
- **Data:** Public holidays, school holidays, exam schedules for all 16 states
- **Usage:** Provides holiday/school context when user asks about seasonal demand
- **Trigger:** Keyword detection — called only when question mentions holidays, school, exams, festive periods, etc.
- **No API key required** — free public API with official government gazette data

---

## Request Lifecycle Examples

### Simulation Flow (End-to-End)

```
User types: "What if I raise prices by 10%?"
         │
         ▼
┌─ ChatPanel ──────────────────────────────────────────────────────┐
│  1. POST /api/simulation/suggest                                  │
│     → ScenarioSuggestionAgent.analyze_question()                  │
│     → LLM generates 2-3 scenarios                                 │
│     → User selects "Price Change +10%"                            │
│                                                                   │
│  2. POST /api/simulation/start                                    │
│     → SyntheticPopulationGenerator.generate_population()          │
│       → DOSM demographics → IPF → Agent sampling                  │
│     → Returns simulation_id + initial agent list                  │
│                                                                   │
│  3. GET /api/simulation/{id}/stream (SSE)                         │
│     → LLMAgentBrain.generate_agent_profile() × N agents           │
│       ← SSE: agent_profile_ready (streamed as generated)          │
│     → Phase 1: Independent decisions                              │
│       ← SSE: agent_decision (visit/skip/churn + message)          │
│     → Phase 2: Peer influence                                     │
│       ← SSE: agent_decision (updated decisions)                   │
│     → Week summary                                                │
│       ← SSE: week_summary (metrics)                               │
│                                                                   │
│  4. Frontend updates:                                             │
│     - InfluenceGraph (agent nodes + connections)                   │
│     - ActivityFeed (decision messages)                             │
│     - Metrics panel (visits, revenue, churn)                       │
└───────────────────────────────────────────────────────────────────┘
```

---

## Configuration

All settings managed via `aria/config.py` (Pydantic Settings, loaded from `.env`):

| Setting | Default | Purpose |
|---------|---------|---------|
| `SUPABASE_URL` | required | Supabase project URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `SUPABASE_DB_PASSWORD` | required | Database password |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local LLM server |
| `OLLAMA_MODEL` | `qwen2.5:7b` | LLM model name |
| `NEWS_API_KEY` | optional | newsdata.io API key |
| `DOSM_API_KEY` | optional | DOSM API key |
| `MAX_VRAM_GB` | `6.0` | GPU memory limit |
| `MIN_AGENT_COUNT` | `15` | Minimum simulation agents |
| `MAX_AGENT_COUNT` | `20` | Maximum simulation agents |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), React, TypeScript |
| API | FastAPI, Pydantic, SSE (asyncio.Queue) |
| Simulation | Mesa (ABM framework), asyncio |
| LLM | Ollama (local), qwen2.5:7b |
| Database | Supabase (PostgreSQL), SQLAlchemy (models) |
| Population | NumPy (IPF), Pandas (DOSM data) |
| External | aiohttp, requests |
| Visualization | D3-style force graph (custom SVG) |

---

## Directory Structure

```
aria/
├── api/
│   └── main.py              # FastAPI app, all endpoints
├── agents/
│   ├── customer_profiler.py  # AI customer profile inference
│   ├── scenario_suggestion.py # Scenario generation agent
│   └── archetype_generator.py # Population generation orchestrator
├── simulation/
│   ├── mesa_model.py         # Mesa ABM model
│   ├── customer_agent.py     # Individual agent class
│   └── llm_agent_brain.py    # LLM decision-making core
├── population/
│   ├── ipf_engine.py         # Iterative Proportional Fitting
│   └── synthetic_population.py # Population generator
├── database/
│   ├── models.py             # SQLAlchemy ORM models
│   ├── supabase_client.py    # Supabase REST client
│   ├── repositories.py       # Data access patterns
│   └── connection.py         # DB connection management
├── external/
│   ├── dosm.py               # DOSM demographics client
│   ├── news_api.py           # newsdata.io client
│   └── malaysia_calendar.py  # Malaysia Calendar API (holidays, school, exams)
├── llm/
│   ├── ollama_client.py      # Ollama HTTP client
│   ├── prompts.py            # Prompt templates
│   └── parsers.py            # LLM response parsing
├── utils/                    # Utility helpers
└── config.py                 # Settings management

frontend/src/
├── components/
│   ├── auth/                 # Login/registration
│   ├── onboarding/           # Business setup flow
│   └── dashboard/            # Main simulation UI
├── context/                  # React context (session)
└── lib/                      # API client, utilities

data/                         # Static data files (DOSM income)
migrations/                   # SQL schema definitions
scripts/                      # Maintenance utilities
```

---

## Key Design Decisions

1. **Local LLM (Ollama)** — Privacy-first, no data leaves the machine. Trades speed for data sovereignty.

2. **IPF for Population** — Statistically valid synthetic populations that match real Malaysian demographics, not random sampling.

3. **Two-Phase Decisions** — Independent thinking + peer influence mirrors real consumer behavior (personal preference → social proof).

4. **SSE Streaming** — Real-time feedback during simulation. Users see agents "thinking" rather than waiting for batch results.

5. **Supabase REST (not ORM)** — Simpler deployment, built-in auth/RLS, no connection pool management needed for a single-user dev tool.

6. **Hybrid B2B/B2C** — Supports businesses that sell to both consumers and other businesses with separate decision logic per customer type.

7. **Constraint-Based Simulation** — Users can filter population by income/age/business-size to test specific market segments.
