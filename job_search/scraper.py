"""
Job page scraper — fetches individual job listing pages using curl_cffi.
"""

import random
import asyncio
import logging
from typing import Optional

from curl_cffi import requests as cffi_requests

from job_search.config import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from job_search.parsers import parse_job_page, validate_url

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def fetch_job_page(url: str) -> Optional[str]:
    """Fetch a job listing page. Returns HTML or None on failure."""
    try:
        resp = cffi_requests.get(
            url,
            headers=HEADERS,
            impersonate="chrome120",
            timeout=20,
            allow_redirects=True,
        )
        if resp.status_code == 404:
            raise ValueError("Job not found (404)")
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        raise exc


def scrape_job(url: str, category: str, posted_at: str = "") -> Optional[dict]:
    """
    Fetch and parse a single job page.

    Returns a job dict ready for DB insertion, or raises on failure.
    """
    if not validate_url(url):
        raise ValueError("Invalid URL format")

    html = fetch_job_page(url)
    job  = parse_job_page(html, url)

    if job is None:
        raise ValueError("Parser returned no data")

    job["posted_at"] = posted_at
    job["category"]  = category
    job["raw_html"]  = None  # set to html if you want to store it

    return job


async def scrape_job_async(url: str, category: str, posted_at: str = "") -> Optional[dict]:
    """Async wrapper — runs the blocking scrape in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, scrape_job, url, category, posted_at)


async def polite_delay():
    """Random delay between job page requests to avoid hammering boards."""
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    await asyncio.sleep(delay)
