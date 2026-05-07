"""
Per-board job page parsers.
Each parser receives the page HTML + URL and returns a normalized job dict.
"""

import re
import json
import logging
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from job_search.config import SKILL_KEYWORDS, REGION_LABELS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_skills(text: str) -> list[str]:
    """Scan text for known skill keywords (case-insensitive, word-boundary aware)."""
    found = []
    text_lower = text.lower()
    for skill in SKILL_KEYWORDS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found[:10]  # cap at 10 to keep it clean


def detect_region(location_text: str) -> str:
    """Map a location string to a region label."""
    loc = location_text.lower()
    for region, keywords in REGION_LABELS.items():
        for kw in keywords:
            if kw in loc:
                return region
    return "worldwide"  # default


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# Greenhouse  (boards.greenhouse.io/company/jobs/12345)
# ---------------------------------------------------------------------------

def parse_greenhouse(html: str, url: str) -> Optional[dict]:
    soup = _soup(html)

    title_el = soup.select_one("h1.app-title") or soup.select_one("h1")
    if not title_el:
        return None

    company_el = (
        soup.select_one("span.company-name")
        or soup.select_one(".company-name")
        or soup.select_one("h2")
    )
    location_el = (
        soup.select_one(".location")
        or soup.select_one("[class*='location']")
    )
    body_el = soup.select_one("#content") or soup.select_one(".content")

    title    = title_el.get_text(strip=True)
    company  = company_el.get_text(strip=True) if company_el else _company_from_url(url)
    location = location_el.get_text(strip=True) if location_el else ""
    body     = body_el.get_text(" ", strip=True) if body_el else soup.get_text(" ", strip=True)

    # Extract job ID from URL
    match = re.search(r"/jobs/(\d+)", url)
    job_id = match.group(1) if match else url.split("/")[-1]

    return {
        "id":       f"greenhouse:{_slug(company)}:{job_id}",
        "board":    "GREENHOUSE",
        "company":  company,
        "title":    title,
        "url":      url,
        "location": location,
        "region":   detect_region(location),
        "skills":   extract_skills(body),
        "description": body[:2000],
    }


# ---------------------------------------------------------------------------
# Lever  (jobs.lever.co/company/uuid)
# ---------------------------------------------------------------------------

def parse_lever(html: str, url: str) -> Optional[dict]:
    soup = _soup(html)

    # Lever renders data in a JSON blob on the page
    script = soup.find("script", string=re.compile(r"\"title\""))
    if script:
        try:
            data = json.loads(script.string)
            title    = data.get("title", "")
            company  = data.get("company", {}).get("name", _company_from_url(url))
            location = data.get("categories", {}).get("location", "")
            body     = data.get("descriptionPlain", "") or data.get("description", "")
            job_id   = data.get("id", url.split("/")[-1])
            return {
                "id":       f"lever:{_slug(company)}:{job_id}",
                "board":    "LEVER",
                "company":  company,
                "title":    title,
                "url":      url,
                "location": location,
                "region":   detect_region(location),
                "skills":   extract_skills(body),
                "description": body[:2000],
            }
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: parse HTML directly
    title_el    = soup.select_one("h2") or soup.select_one("h1")
    location_el = soup.select_one(".location") or soup.select_one("[class*='location']")
    body_el     = soup.select_one(".content") or soup.select_one("[class*='description']")

    if not title_el:
        return None

    # Extract UUID from URL
    match = re.search(
        r"jobs\.lever\.co/([^/]+)/([0-9a-f-]{36})",
        url,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Invalid URL format")

    company = match.group(1)
    job_id  = match.group(2)
    title   = title_el.get_text(strip=True)
    location = location_el.get_text(strip=True) if location_el else ""
    body    = body_el.get_text(" ", strip=True) if body_el else soup.get_text(" ", strip=True)

    return {
        "id":       f"lever:{company}:{job_id}",
        "board":    "LEVER",
        "company":  _prettify(company),
        "title":    title,
        "url":      url,
        "location": location,
        "region":   detect_region(location),
        "skills":   extract_skills(body),
        "description": body[:2000],
    }


# ---------------------------------------------------------------------------
# Ashby  (jobs.ashbyhq.com/company/uuid)
# ---------------------------------------------------------------------------

def parse_ashby(html: str, url: str) -> Optional[dict]:
    soup = _soup(html)

    # Ashby embeds __NEXT_DATA__ JSON
    script = soup.find("script", id="__NEXT_DATA__")
    if script:
        try:
            data  = json.loads(script.string)
            props = data["props"]["pageProps"]
            job   = props.get("jobPosting") or props.get("job") or {}

            title    = job.get("title", "")
            company  = props.get("organization", {}).get("name", _company_from_url(url))
            location = job.get("locationName") or job.get("location") or ""
            body     = job.get("descriptionHtml", "") or job.get("description", "")
            body_text = BeautifulSoup(body, "lxml").get_text(" ", strip=True)
            job_id   = job.get("id", url.split("/")[-1])

            return {
                "id":       f"ashby:{_slug(company)}:{job_id}",
                "board":    "ASHBY",
                "company":  company,
                "title":    title,
                "url":      url,
                "location": location,
                "region":   detect_region(location),
                "skills":   extract_skills(body_text),
                "description": body_text[:2000],
            }
        except (KeyError, json.JSONDecodeError):
            pass

    # Fallback
    title_el    = soup.select_one("h1")
    location_el = soup.select_one("[class*='location']") or soup.select_one("[class*='Location']")
    body_el     = soup.select_one("main") or soup.select_one("[class*='description']")

    if not title_el:
        return None

    company  = _company_from_url(url)
    title    = title_el.get_text(strip=True)
    location = location_el.get_text(strip=True) if location_el else ""
    body     = body_el.get_text(" ", strip=True) if body_el else ""
    job_id   = url.rstrip("/").split("/")[-1]

    return {
        "id":       f"ashby:{_slug(company)}:{job_id}",
        "board":    "ASHBY",
        "company":  _prettify(company),
        "title":    title,
        "url":      url,
        "location": location,
        "region":   detect_region(location),
        "skills":   extract_skills(body),
        "description": body[:2000],
    }


# ---------------------------------------------------------------------------
# Workable  (apply.workable.com/company/j/ID  or  jobs.workable.com/view/...)
# ---------------------------------------------------------------------------

def parse_workable(html: str, url: str) -> Optional[dict]:
    soup = _soup(html)

    # Workable embeds JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if data.get("@type") == "JobPosting":
                title    = data.get("title", "")
                company  = data.get("hiringOrganization", {}).get("name", _company_from_url(url))
                location = _workable_location(data)
                body     = BeautifulSoup(
                    data.get("description", ""), "lxml"
                ).get_text(" ", strip=True)
                job_id   = url.rstrip("/").split("/")[-1]

                return {
                    "id":       f"workable:{_slug(company)}:{job_id}",
                    "board":    "WORKABLE",
                    "company":  company,
                    "title":    title,
                    "url":      url,
                    "location": location,
                    "region":   detect_region(location),
                    "skills":   extract_skills(body),
                    "description": body[:2000],
                }
        except (json.JSONDecodeError, AttributeError):
            continue

    # Fallback
    title_el    = soup.select_one("h1")
    location_el = soup.select_one("[class*='location']") or soup.select_one("[data-ui='job-location']")
    body_el     = soup.select_one("[class*='description']") or soup.select_one("main")

    if not title_el:
        return None

    company  = _company_from_url(url)
    title    = title_el.get_text(strip=True)
    location = location_el.get_text(strip=True) if location_el else ""
    body     = body_el.get_text(" ", strip=True) if body_el else ""
    job_id   = url.rstrip("/").split("/")[-1]

    return {
        "id":       f"workable:{_slug(company)}:{job_id}",
        "board":    "WORKABLE",
        "company":  _prettify(company),
        "title":    title,
        "url":      url,
        "location": location,
        "region":   detect_region(location),
        "skills":   extract_skills(body),
        "description": body[:2000],
    }


def _workable_location(data: dict) -> str:
    loc = data.get("jobLocation", {})
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address", {})
    parts = [
        addr.get("addressLocality", ""),
        addr.get("addressRegion", ""),
        addr.get("addressCountry", ""),
    ]
    return ", ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Router — pick the right parser based on URL
# ---------------------------------------------------------------------------

PARSERS = {
    "boards.greenhouse.io": parse_greenhouse,
    "jobs.lever.co":        parse_lever,
    "jobs.ashbyhq.com":     parse_ashby,
    "apply.workable.com":   parse_workable,
    "jobs.workable.com":    parse_workable,
}


def parse_job_page(html: str, url: str) -> Optional[dict]:
    host = urlparse(url).netloc.lstrip("www.")
    parser = PARSERS.get(host)
    if not parser:
        logger.warning("No parser for host: %s", host)
        return None
    return parser(html, url)


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def validate_lever_url(url: str) -> bool:
    """Lever URLs must be /company/uuid — filter out listing/filter pages."""
    return bool(
        re.search(r"jobs\.lever\.co/[^/]+/[0-9a-f-]{36}", url, re.IGNORECASE)
    )


def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lstrip("www.")
    if host == "jobs.lever.co":
        return validate_lever_url(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _company_from_url(url: str) -> str:
    parts = urlparse(url).path.strip("/").split("/")
    return _prettify(parts[0]) if parts else "Unknown"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _prettify(slug: str) -> str:
    """'my-company-name' → 'My Company Name'"""
    return slug.replace("-", " ").replace("_", " ").title()
