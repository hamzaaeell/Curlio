"""
Main orchestrator — runs all board × category × region combinations,
scrapes found URLs, and saves results to the database.

Mirrors the log output you showed:
  [GREENHOUSE / DEVOPS / INTL] Searching: ...
    → 5 URL(s) found
    Scraping [20 hours ago]: https://...
      → Title @ Company | Location [region] | skills: [...]
      ✓ SAVED / ~ DUPLICATE / ✗ FAILED / ✗ SKIPPED
"""

import asyncio
import logging
import time
from typing import Optional

from job_search.config import (
    JOB_BOARDS,
    JOB_CATEGORIES,
    REGION_GROUPS,
    RESULTS_PER_SEARCH,
)
from job_search.search import build_query, google_search, close_browser
from job_search.scraper import scrape_job, polite_delay
from job_search.database import init_db, save_job, job_exists
from job_search.parsers import validate_url
from rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category filter — skip jobs that don't match the expected category
# ---------------------------------------------------------------------------

CATEGORY_TITLE_KEYWORDS = {
    "DEVOPS": [
        "devops", "sre", "platform", "cloud", "infrastructure",
        "site reliability", "kubernetes", "k8s", "devsecops",
    ],
    "DATA": [
        "data engineer", "analytics engineer", "etl", "data platform",
        "data architect",
    ],
    "AI_ML": [
        "ai engineer", "ml engineer", "machine learning", "data scientist",
        "llm", "mlops", "nlp", "computer vision",
    ],
    "BACKEND": [
        "backend", "software engineer", "python developer", "go developer",
        "rust developer", "full stack", "fullstack",
    ],
}


def matches_category(title: str, category: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    keywords = CATEGORY_TITLE_KEYWORDS.get(category, [])
    return any(kw in title_lower for kw in keywords)


# ---------------------------------------------------------------------------
# Single URL processor
# ---------------------------------------------------------------------------

async def process_url(url: str, posted_at: str, category: str) -> str:
    """
    Scrape one job URL. Returns status: SAVED | DUPLICATE | FAILED | SKIPPED | INVALID
    """
    logger.info("  Scraping [%s]: %s", posted_at or "unknown", url)

    if not validate_url(url):
        logger.warning("Cannot parse URL: %s", url)
        logger.warning("    ✗ FAILED: Invalid URL format")
        return "INVALID"

    if job_exists(url):
        logger.info("    ~ DUPLICATE (already in DB)")
        return "DUPLICATE"

    try:
        job = await asyncio.get_event_loop().run_in_executor(
            None, scrape_job, url, category, posted_at
        )
    except ValueError as exc:
        logger.warning("    ✗ FAILED: %s", exc)
        return "FAILED"
    except Exception as exc:
        logger.warning("    ✗ FAILED: %s", exc)
        return "FAILED"

    if not matches_category(job.get("title", ""), category):
        logger.info(
            "    ✗ SKIPPED job '%s' - doesn't match %s category",
            job.get("title", ""),
            category.lower(),
        )
        return "SKIPPED"

    skills   = job.get("skills", [])
    region   = job.get("region", "worldwide")
    title    = job.get("title", "")
    company  = job.get("company", "")
    location = job.get("location", "")

    logger.info(
        "    → %s @ %s | %s [%s] | skills: %s",
        title, company, location, region, skills,
    )

    saved = save_job(job)
    if saved:
        logger.info("    ✓ SAVED [%s]", region)
        return "SAVED"
    else:
        logger.info("    ~ DUPLICATE (already in DB)")
        return "DUPLICATE"


# ---------------------------------------------------------------------------
# Single search combination
# ---------------------------------------------------------------------------

async def run_search(
    board_name: str,
    board_site: str,
    category: str,
    keywords: list[str],
    region_name: str,
    regions: list[str],
) -> dict:
    """Run one Google search and process all found URLs."""
    query = build_query(board_site, keywords, regions)
    label = f"[{board_name} / {category} / {region_name}]"

    logger.info("%s Searching: %s", label, query)

    # Rate-limit Google requests
    await rate_limiter.acquire()

    try:
        results = await google_search(query, num=RESULTS_PER_SEARCH)
    except Exception as exc:
        logger.error("%s Search failed: %s", label, exc)
        return {"found": 0, "saved": 0, "failed": 0}

    if not results:
        logger.info("  → No results")
        return {"found": 0, "saved": 0, "failed": 0}

    logger.info("  → %d URL(s) found", len(results))

    counts = {"found": len(results), "saved": 0, "failed": 0, "duplicate": 0, "skipped": 0}

    for item in results:
        status = await process_url(item["url"], item["posted_at"], category)
        if status == "SAVED":
            counts["saved"] += 1
        elif status == "FAILED":
            counts["failed"] += 1
        elif status == "DUPLICATE":
            counts["duplicate"] += 1
        elif status == "SKIPPED":
            counts["skipped"] += 1

        # Polite delay between job page scrapes
        await polite_delay()

    return counts


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------

async def run_all(
    boards: Optional[list[str]] = None,
    categories: Optional[list[str]] = None,
    regions: Optional[list[str]] = None,
):
    """
    Run all board × category × region × keyword-group combinations.

    Args:
        boards:     Subset of JOB_BOARDS keys to run (None = all)
        categories: Subset of JOB_CATEGORIES keys to run (None = all)
        regions:    Subset of REGION_GROUPS keys to run (None = all)
    """
    init_db()

    selected_boards     = {k: v for k, v in JOB_BOARDS.items()     if not boards     or k in boards}
    selected_categories = {k: v for k, v in JOB_CATEGORIES.items() if not categories or k in categories}
    selected_regions    = {k: v for k, v in REGION_GROUPS.items()  if not regions    or k in regions}

    total_saved = 0
    start_time  = time.time()

    for board_name, board_site in selected_boards.items():
        for category, keyword_groups in selected_categories.items():
            for region_name, region_keywords in selected_regions.items():
                for keywords in keyword_groups:
                    counts = await run_search(
                        board_name, board_site,
                        category, keywords,
                        region_name, region_keywords,
                    )
                    total_saved += counts.get("saved", 0)

    elapsed = time.time() - start_time
    logger.info(
        "Run complete — %d new jobs saved in %.1fs",
        total_saved, elapsed,
    )

    # Clean up Playwright browser
    await close_browser()

    return total_saved
