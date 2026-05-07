# Self-Hosted Search API

A Serper.dev alternative using [`curl_cffi`](https://github.com/yifeikong/curl_cffi) for Chrome TLS fingerprint impersonation. Designed for **1,000–2,000 Google searches/day** from a single IP.

## How it works

Google blocks most scrapers at the TLS handshake level before even looking at your headers. `curl_cffi` makes the TLS + HTTP/2 fingerprint byte-for-byte identical to Chrome 120, which bypasses this detection. At your volume (~1–2 req/min), no proxy pool is needed.

```
Your App → FastAPI → Rate Limiter → curl_cffi (Chrome120 TLS) → Google → Parser → JSON
```

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: set an API key
cp .env.example .env
# edit .env and set API_KEY=your_secret

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API

### `GET /search`

| Param     | Type   | Default | Description                        |
|-----------|--------|---------|------------------------------------|
| `q`       | string | —       | Search query (required)            |
| `num`     | int    | 10      | Number of results (1–100)          |
| `lang`    | string | `en`    | Language code (`hl` param)         |
| `country` | string | `us`    | Country code (`gl` param)          |
| `page`    | int    | 1       | Page number (1–10)                 |

**Auth:** Pass `X-API-Key: your_secret` header if `API_KEY` is set.

**Example:**
```bash
curl "http://localhost:8000/search?q=python+fastapi&num=5" \
  -H "X-API-Key: your_secret"
```

**Response:**
```json
{
  "query": "python fastapi",
  "cached": false,
  "responseTime": 1.243,
  "searchInformation": {
    "totalResults": "12300000",
    "formattedTotalResults": "12,300,000",
    "rawText": "About 12,300,000 results (1.24 seconds)"
  },
  "organic": [
    {
      "position": 1,
      "title": "FastAPI - Modern, fast web framework for Python",
      "link": "https://fastapi.tiangolo.com/",
      "snippet": "FastAPI framework, high performance, easy to learn...",
      "displayedLink": "fastapi.tiangolo.com"
    }
  ],
  "knowledgeGraph": null,
  "peopleAlsoAsk": [
    { "question": "Is FastAPI better than Flask?" }
  ],
  "relatedSearches": [
    { "query": "fastapi tutorial" }
  ]
}
```

### `GET /health`
Returns service status and cache info. No auth required.

### `GET /cache/stats`
Returns cache entry count and config.

### `DELETE /cache`
Clears the result cache.

## Rate limiting

The built-in rate limiter enforces **2 requests/minute** with random jitter (±5s) to avoid mechanical patterns. This keeps you well within safe limits for 2,000 queries/day.

Results are cached for **1 hour** by default — repeated identical queries don't hit Google at all.

## Configuration

| Env var   | Default | Description                          |
|-----------|---------|--------------------------------------|
| `API_KEY` | unset   | If set, requires `X-API-Key` header  |

To change rate limits or cache TTL, edit `rate_limiter.py` and `cache.py` directly.
