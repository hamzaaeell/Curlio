"""
Self-hosted Google Search API — Serper.dev alternative
Uses curl_cffi for TLS fingerprint impersonation (Chrome 120)

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000

Endpoints:
    GET /search?q=<query>&num=10&lang=en&country=us&page=1
    GET /health
    GET /cache/stats
    DELETE /cache
"""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from scraper import google_search
from cache import cache
from rate_limiter import rate_limiter

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional API key auth (set API_KEY env var to enable, leave unset to disable)
# ---------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY")  # e.g. export API_KEY=mysecretkey
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str = Security(api_key_header)):
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Search API starting up")
    logger.info("API key auth: %s", "enabled" if API_KEY else "disabled")
    yield
    logger.info("Search API shutting down")


app = FastAPI(
    title="Self-Hosted Search API",
    description="Serper.dev alternative using curl_cffi + Google SERP parsing",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "DELETE"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/search", summary="Search Google")
async def search(
    q: str = Query(..., description="Search query", min_length=1, max_length=500),
    num: int = Query(10, description="Number of results", ge=1, le=100),
    lang: str = Query("en", description="Language code (hl)", max_length=10),
    country: str = Query("us", description="Country code (gl)", max_length=10),
    page: int = Query(1, description="Page number", ge=1, le=10),
    _: str = Depends(verify_api_key),
):
    """
    Perform a Google search and return structured JSON results.

    Returns organic results, knowledge graph, people also ask,
    related searches, and search metadata.
    """
    # Check cache first — no need to hit Google for repeated queries
    cached = cache.get(q, num, lang, country, page)
    if cached:
        return JSONResponse(content={**cached, "cached": True})

    # Respect rate limit before hitting Google
    await rate_limiter.acquire()

    start_time = time.perf_counter()
    try:
        results = google_search(q, num=num, lang=lang, country=country, page=page)
    except Exception as exc:
        logger.error("Scrape failed for query '%s': %s", q, exc)
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}")

    elapsed = time.perf_counter() - start_time
    results["responseTime"] = round(elapsed, 3)
    results["cached"] = False

    # Store in cache
    cache.set(q, num, lang, country, page, results)

    return results


@app.get("/health", summary="Health check")
async def health():
    """Returns service status and cache stats."""
    return {
        "status": "ok",
        "cache": {
            "size": cache.size,
            "ttl_seconds": cache.ttl,
            "max_size": cache.max_size,
        },
    }


@app.get("/cache/stats", summary="Cache statistics")
async def cache_stats(_: str = Depends(verify_api_key)):
    return {
        "entries": cache.size,
        "ttl_seconds": cache.ttl,
        "max_size": cache.max_size,
    }


@app.delete("/cache", summary="Clear cache")
async def clear_cache(_: str = Depends(verify_api_key)):
    count = cache.clear()
    return {"cleared": count}
