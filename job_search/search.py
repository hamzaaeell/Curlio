"""
Google search layer — uses Playwright async API (real Chromium) to execute JS
and bypass Google's JS challenge, then extracts job URLs + post dates.
"""

import re
import logging
import urllib.parse
from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

# Shared async browser state — initialised once per run
_playwright = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None


async def _get_context() -> BrowserContext:
    global _playwright, _browser, _context
    if _context is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        _context = await _browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await _context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    return _context


async def close_browser():
    global _playwright, _browser, _context
    if _context:
        await _context.close()
        _context = None
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


def build_query(
    site: str,
    keywords: list[str],
    regions: list[str],
    extra: str = '"remote"',
) -> str:
    """
    Build a Google site: search query.

    Example:
        site:jobs.lever.co ("DevOps" OR "SRE") "remote" ("Europe" OR "EMEA")
    """
    kw_part     = " OR ".join(f'"{k}"' for k in keywords)
    region_part = " OR ".join(f'"{r}"' for r in regions)
    return f'{site} ({kw_part}) {extra} ({region_part})'


async def google_search(query: str, num: int = 20) -> list[dict]:
    """
    Run a Google search using a real Chromium browser (async).
    Returns a list of {url, posted_at} dicts.
    """
    params = {
        "q":   query,
        "num": num,
        "hl":  "en",
        "gl":  "us",
    }
    search_url = "https://www.google.com/search?" + urllib.parse.urlencode(params)
    logger.debug("Google query URL: %s", search_url)

    ctx  = await _get_context()
    page = await ctx.new_page()

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

        # Handle cookie consent dialogs (EU)
        try:
            accept = page.locator("button:has-text('Accept all'), button:has-text('I agree')")
            if await accept.count() > 0:
                await accept.first.click()
                await page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except PWTimeout:
            pass

        # Wait for results
        try:
            await page.wait_for_selector(
                "div#search, div#rso, div.g, div[data-hveid]",
                timeout=15_000,
            )
        except PWTimeout:
            logger.warning("Timed out waiting for search results")

        html = await page.content()
        return _parse_serp(html)

    except Exception as exc:
        logger.error("Playwright search failed: %s", exc)
        return []
    finally:
        await page.close()


def _parse_serp(html: str) -> list[dict]:
    """Extract job URLs and post dates from Google SERP HTML."""
    soup    = BeautifulSoup(html, "lxml")
    results = []
    seen    = set()

    job_domains = [
        "boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.ashbyhq.com",
        "apply.workable.com",
        "jobs.workable.com",
    ]

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if not href.startswith("http"):
            continue
        if "google.com" in href:
            continue
        if not any(d in href for d in job_domains):
            continue

        # Strip Google's #:~:text= highlight fragments — same underlying URL
        href = href.split("#")[0].rstrip("/")

        if href in seen:
            continue
        seen.add(href)

        # Try to find a nearby date string
        posted_at = ""
        parent = a.find_parent("div")
        if parent:
            text = parent.get_text(" ", strip=True)
            match = re.search(r"(\d+\s+(?:hour|day|week|month)s?\s+ago)", text, re.IGNORECASE)
            if match:
                posted_at = match.group(1)

        results.append({"url": href, "posted_at": posted_at})

    # Fallback: standard result containers
    if not results:
        for g in soup.select("div.g, div[data-hveid], div.tF2Cxc"):
            link_el = g.select_one("a[href]")
            if not link_el:
                continue
            href = link_el.get("href", "").split("#")[0].rstrip("/")
            if not href.startswith("http") or href in seen:
                continue
            if not any(d in href for d in job_domains):
                continue
            seen.add(href)

            posted_at = ""
            date_el = g.select_one("span.MUxGbd, span.f, [class*='date']")
            if date_el:
                t = date_el.get_text(strip=True)
                if re.search(r"\d+\s+(hour|day|week|month)", t, re.IGNORECASE):
                    posted_at = t

            results.append({"url": href, "posted_at": posted_at})

    logger.debug("SERP parsed: %d job links found", len(results))
    return results
