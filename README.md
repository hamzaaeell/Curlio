# Curlio — Self-Hosted Job Search Scraper

A job board scraper that uses Google `site:` searches to find remote job listings across Greenhouse, Lever, Ashby, and Workable, then scrapes and stores each result in a local SQLite database.

## How it works

```
run.py
  └── Google site: search (Playwright / headless Chromium)
        └── Job URLs extracted from SERP
              └── Job pages fetched (curl_cffi — Chrome TLS fingerprint)
                    └── Parsed → SQLite (jobs.db)
```

**Google search** uses a real headless Chromium browser via Playwright to handle JavaScript challenges. **Job page fetching** uses [`curl_cffi`](https://github.com/yifeikong/curl_cffi) which impersonates Chrome's TLS fingerprint for fast, reliable scraping without a proxy pool.

## Project structure

```
.
├── job_search/
│   ├── config.py      ← boards, categories, regions, skill keywords
│   ├── database.py    ← SQLite storage layer
│   ├── parsers.py     ← per-board HTML parsers
│   ├── scraper.py     ← fetches individual job pages
│   ├── search.py      ← builds + runs Google site: queries
│   └── runner.py      ← orchestrates everything
├── run.py             ← CLI entry point
├── main.py            ← optional REST API wrapper (FastAPI)
├── cache.py           ← in-memory TTL cache
├── rate_limiter.py    ← token bucket rate limiter
└── requirements.txt
```

## Setup

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install the Chromium browser for Playwright
playwright install chromium

# Optional: set an API key for the REST API
cp .env.example .env
# edit .env and set API_KEY=your_secret
```

## Running the scraper

```bash
# Scrape all boards, categories, and regions
python run.py

# Target specific boards
python run.py --boards LEVER ASHBY

# Target specific categories
python run.py --categories DEVOPS AI_ML

# Target specific regions
python run.py --regions INTL

# Combine filters
python run.py --boards LEVER GREENHOUSE --categories DEVOPS --regions INTL

# Print database stats
python run.py --stats

# Export all saved jobs to JSON
python run.py --export jobs_export.json
```

## Supported boards

| Key          | Site                        |
|--------------|-----------------------------|
| `GREENHOUSE` | `boards.greenhouse.io`      |
| `LEVER`      | `jobs.lever.co`             |
| `ASHBY`      | `jobs.ashbyhq.com`          |
| `WORKABLE`   | `apply.workable.com` + `jobs.workable.com` |

## Job categories

| Key       | Roles searched                                                      |
|-----------|---------------------------------------------------------------------|
| `DEVOPS`  | DevOps, SRE, Platform Engineer, Cloud Engineer, Kubernetes, etc.   |
| `DATA`    | Data Engineer, Analytics Engineer, ETL, Data Platform              |
| `AI_ML`   | ML Engineer, Data Scientist, LLM Engineer, MLOps, NLP              |
| `BACKEND` | Backend Engineer, Python/Go/Rust Developer                         |

Add new categories or roles in `job_search/config.py` — no code changes needed.

## Regions

| Key    | Targets                                                    |
|--------|------------------------------------------------------------|
| `INTL` | Europe, EMEA, India, APAC, LATAM, UAE, worldwide, global  |
| `US`   | United States, USA, US-based, nationwide                  |

## Log output

```
18:08:28 [INFO] [LEVER / DEVOPS / INTL] Searching: site:jobs.lever.co ("DevOps" OR "SRE" ...) "remote" ("Europe" OR ...)
18:09:03 [INFO]   → 10 URL(s) found
18:09:03 [INFO]   Scraping [unknown]: https://jobs.lever.co/mistral/6e16e4fa-...
18:09:04 [INFO]     → Site Reliability Engineer @ Mistral | Remote [worldwide] | skills: ['Kubernetes', 'Terraform', 'Go', ...]
18:09:04 [INFO]     ✓ SAVED [worldwide]
18:09:06 [INFO]   Scraping [unknown]: https://jobs.lever.co/acme/...
18:09:07 [INFO]     ~ DUPLICATE (already in DB)
```

Logs are also written to `job_search.log`.

## Rate limiting

Google searches are rate-limited to **2 requests/minute** with random jitter (±5s). Job page scrapes have a separate **2–5 second random delay** between requests. At 1,000–2,000 searches/day you're averaging ~1.4 req/min — well within safe limits for a single IP.

## Optional REST API

A FastAPI wrapper is included if you want to query the search engine over HTTP.

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### `GET /search`

| Param     | Type   | Default | Description               |
|-----------|--------|---------|---------------------------|
| `q`       | string | —       | Search query (required)   |
| `num`     | int    | 10      | Number of results (1–100) |
| `lang`    | string | `en`    | Language code             |
| `country` | string | `us`    | Country code              |
| `page`    | int    | 1       | Page number (1–10)        |

**Auth:** Pass `X-API-Key: your_secret` header if `API_KEY` is set in `.env`.

```bash
curl "http://localhost:8000/search?q=devops+remote+europe&num=10" \
  -H "X-API-Key: your_secret"
```

Other endpoints: `GET /health`, `GET /cache/stats`, `DELETE /cache`.

## Configuration

All tunable settings live in `job_search/config.py`:

- **`JOB_BOARDS`** — add or remove job board sites
- **`JOB_CATEGORIES`** — add roles or keyword groups
- **`REGION_GROUPS`** — add region targets
- **`SKILL_KEYWORDS`** — skills to extract from job descriptions
- **`RESULTS_PER_SEARCH`** — Google results per query (default 20)
- **`REQUEST_DELAY_MIN/MAX`** — delay between job page scrapes

Rate limiter settings are in `rate_limiter.py`, cache TTL in `cache.py`.
