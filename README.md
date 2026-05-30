# 🕵️ 北美华人美食侦探 · US Foodie Scout

> AI-powered restaurant discovery for the LA Chinese community — combining real Google ratings with authentic 小红书 (XHS) community sentiment.

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-purple)](https://platform.deepseek.com)

---

## What It Does

US Foodie Scout helps LA's Chinese community find restaurants by combining two data sources most apps ignore together:

- 🔵 **Google Places** — real ratings, addresses, price levels
- 🌸 **小红书 (XHS)** — authentic Chinese community sentiment, scraped offline via 八爪鱼

Every restaurant gets a **dual badge**:

| Badge | Meaning |
|-------|---------|
| 🔥 华人必打卡 | Google ≥ 75 AND XHS ≥ 70 — community-verified |
| 💎 隐藏宝藏 | XHS ≥ 70, Google lower — hidden gem locals love |
| ⚠️ 网红店慎入 | Google ≥ 75, XHS lower — possible tourist trap |
| ⭐ 普通推荐 | Both average |
| 🔍 网络口碑 | Out-of-database restaurant, evaluated via live web search |

---

## Features

- **Structured intent extraction** — DeepSeek JSON mode rewrites fuzzy NL queries into `{cuisine, price, area, authenticity_pref, keywords, exclude_names}` before hitting the search layer; degrades to raw-query passthrough on failure with zero pipeline disruption
- **Conversation-aware retrieval** — last 4 turns passed to the intent extractor so refine queries ("有没有近一点的") inherit previous area/cuisine; "换几家" triggers exclude_names extraction from history, bypassing the cache to prevent stale results
- **Multi-tier fallback chain** — static DB (87 restaurants) → area-miss or thin results (< 3) → live Google Places API → supplements rather than replaces, deduped by place_id + name
- **Offline XHS pipeline** — 8,604 notes scraped via 八爪鱼 desktop client (template 2996), ingested and deduplicated by note URL; likes-primary scoring formula since saves are structurally uncollectable from search-list cards
- **Tavily web search fallback** — when a restaurant has no XHS batch data, Tavily queries return Chinese-community snippets filtered by `_is_relevant()` (blocks hotel-record spam, requires food signal or restaurant name match) before LLM synthesis
- **LLM grounding** — when a named restaurant isn't found in the returned results, a `not_found_name` note is injected into the LLM context to prevent parametric-memory hallucination about the missing restaurant
- **Area alias expansion** — "SGV" expands to 8 San Gabriel Valley cities; "USC" maps to University Park / Exposition Park (deliberately excludes "Los Angeles" to avoid matching the entire database)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, Tailwind CSS, `@vis.gl/react-google-maps` |
| Backend | FastAPI, LangChain, DeepSeek API |
| Data | Google Places API (New), 八爪鱼 XHS scraping, Tavily web search |
| Cache | Redis — sessions, rate limiting, Places cache |
| Deployment | Vercel (frontend) + Railway (backend + Redis) |

---

## Dataset

- **87 restaurants** in `data/restaurants.json` — real Google Places data, LA area, SGV-focused
- **102 restaurants / 8,604 notes** in `data/xhs_notes.json` — authentic XHS community data
- Coverage: SGV Chinese restaurants + 28 American-local LA favorites (In-N-Out, Bestia, Langer's Deli, Guelaguetza, Jitlada, etc.)

---

## Architecture

```
User Query (natural language)
  ↓
Step 0: Intent Extraction  (DeepSeek JSON mode, with conversation history)
        → {restaurant_name, cuisine, price, area, pref, keywords, exclude_names}
  ↓
Step 1: Restaurant Search
        Static DB (87 restaurants)
        → area not covered / thin results / zero → live Google Places API
  ↓
Step 2: XHS Sentiment  (parallel, with Yelp photo overlay)
        Batch data (xhs_notes.json)
        → not found → Tavily web search fallback (spam-filtered)
  ↓
Step 3: LLM Recommendation  (DeepSeek streaming SSE)
        Strict: only recommends restaurants in provided data
  ↓
Frontend: cards + Google Maps
```

---

## Local Development

### Prerequisites
- Python 3.12, Node.js 20
- Redis: `brew install redis && brew services start redis`
- API keys: DeepSeek, Google Places (backend), Google Maps JS (frontend), Tavily

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
# create frontend/.env.local with:
# NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_GOOGLE_MAPS_KEY=your_key
# NEXT_PUBLIC_GOOGLE_MAPS_ID=DEMO_MAP_ID
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Docker (all-in-one)

```bash
docker compose up --build
```

---

## Environment Variables

**Backend (`.env`)**
```env
DEEPSEEK_API_KEY=
GOOGLE_API_KEY=           # Google Places API (New) — server side only
TAVILY_API_KEY=           # Tavily web search fallback
XHS_SOURCE=bazhuayu       # "mock" for development without XHS data
GOOGLE_SOURCE=real        # "mock" for development without Google data
XHS_HIGH_THRESHOLD=70
REDIS_URL=redis://localhost:6379
ALLOWED_ORIGINS=http://localhost:3000
```

**Frontend (`frontend/.env.local`)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GOOGLE_MAPS_KEY=    # Google Maps JavaScript API (HTTP-referrer restricted)
NEXT_PUBLIC_GOOGLE_MAPS_ID=DEMO_MAP_ID
```

---

## Data Collection

XHS data is collected offline via **八爪鱼 (Octoparse) desktop client** (template 2996, local QR login with a secondary account). Do NOT use the `xhs` PyPI package — it triggers immediate account bans.

Scripts in `backend/scripts/`:
- `xhs_watch.py` — merge new 八爪鱼 CSV exports into `xhs_notes.json`
- `enrich_google.py` — enrich restaurants with Google Places data
- `ingest_xhs_export.py` — convert 八爪鱼 exports to normalized JSON

---

## License

MIT
