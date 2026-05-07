"""
Google SERP scraper using curl_cffi for TLS fingerprint impersonation.
Parses organic results, knowledge graph, people also ask, and related searches.
"""

import urllib.parse
import re
import logging
from typing import Optional
from curl_cffi import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def google_search(
    query: str,
    num: int = 10,
    lang: str = "en",
    country: str = "us",
    page: int = 1,
) -> dict:
    """
    Perform a Google search and return structured results.

    Args:
        query:   Search query string
        num:     Number of results (max 100)
        lang:    Language code (hl param), e.g. "en"
        country: Country code (gl param), e.g. "us"
        page:    Page number (1-based)

    Returns:
        dict with keys: query, organic, knowledgeGraph, peopleAlsoAsk,
                        relatedSearches, searchInformation
    """
    num = min(num, 100)
    start = (page - 1) * num

    params = {
        "q": query,
        "num": num,
        "hl": lang,
        "gl": country,
        "start": start,
        "ie": "UTF-8",
        "oe": "UTF-8",
    }

    url = "https://www.google.com/search?" + urllib.parse.urlencode(params)
    logger.info("Fetching: %s", url)

    response = requests.get(
        url,
        headers=HEADERS,
        impersonate="chrome120",  # TLS + HTTP/2 fingerprint = Chrome 120
        timeout=20,
    )
    response.raise_for_status()

    return parse_results(response.text, query)


def parse_results(html: str, query: str) -> dict:
    """Parse Google SERP HTML into structured JSON."""
    soup = BeautifulSoup(html, "lxml")

    return {
        "query": query,
        "searchInformation": _parse_search_info(soup),
        "organic": _parse_organic(soup),
        "knowledgeGraph": _parse_knowledge_graph(soup),
        "peopleAlsoAsk": _parse_paa(soup),
        "relatedSearches": _parse_related(soup),
    }


def _parse_search_info(soup: BeautifulSoup) -> dict:
    """Extract result stats (e.g. 'About 1,230,000,000 results (0.45 seconds)')."""
    el = soup.select_one("#result-stats")
    if not el:
        return {}
    text = el.get_text()
    # Extract number of results
    match = re.search(r"([\d,]+)\s+results", text)
    return {
        "totalResults": match.group(1).replace(",", "") if match else None,
        "formattedTotalResults": match.group(1) if match else None,
        "rawText": text.strip(),
    }


def _parse_organic(soup: BeautifulSoup) -> list[dict]:
    """Extract organic search results."""
    results = []
    position = 1

    # Google uses div.g as the main result container
    for g in soup.select("div.g"):
        # Skip nested .g elements (e.g. inside featured snippets)
        if g.find_parent("div", class_="g"):
            continue

        title_el = g.select_one("h3")
        link_el = g.select_one("a[href]")
        snippet_el = g.select_one("div.VwiC3b") or g.select_one("[data-sncf]")
        date_el = g.select_one("span.MUxGbd.wuQ4Ob") or g.select_one("span.f")

        if not (title_el and link_el):
            continue

        href = link_el.get("href", "")
        # Filter out Google-internal links
        if not href.startswith("http"):
            continue

        result = {
            "position": position,
            "title": title_el.get_text(strip=True),
            "link": href,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            "displayedLink": _extract_displayed_link(g),
        }

        if date_el:
            result["date"] = date_el.get_text(strip=True)

        # Sitelinks (sub-links shown under some results)
        sitelinks = _extract_sitelinks(g)
        if sitelinks:
            result["sitelinks"] = sitelinks

        results.append(result)
        position += 1

    return results


def _extract_displayed_link(g) -> str:
    """Extract the green URL shown under the title."""
    el = g.select_one("cite") or g.select_one("span.qzEoUe")
    return el.get_text(strip=True) if el else ""


def _extract_sitelinks(g) -> list[dict]:
    """Extract sitelinks block if present."""
    sitelinks = []
    for sl in g.select("div.usJj9c a, div.HiHjCd a"):
        title = sl.get_text(strip=True)
        href = sl.get("href", "")
        if title and href.startswith("http"):
            sitelinks.append({"title": title, "link": href})
    return sitelinks


def _parse_knowledge_graph(soup: BeautifulSoup) -> Optional[dict]:
    """Extract knowledge graph panel (right-side info box)."""
    kg = soup.select_one("div.kp-wholepage") or soup.select_one("[data-attrid='title']")
    if not kg:
        return None

    title_el = kg.select_one("h2") or kg.select_one("[data-attrid='title'] span")
    type_el = kg.select_one("div.wwUB2c span") or kg.select_one(".YhemCb")
    desc_el = kg.select_one("div.kno-rdesc span") or kg.select_one("[data-attrid='description'] span")

    if not title_el:
        return None

    result = {
        "title": title_el.get_text(strip=True),
        "type": type_el.get_text(strip=True) if type_el else None,
        "description": desc_el.get_text(strip=True) if desc_el else None,
        "attributes": {},
    }

    # Extract key-value attributes (e.g. "Founded: 1998")
    for row in kg.select("div.rVusze"):
        key_el = row.select_one("span.w8qArf")
        val_el = row.select_one("span.LrzXr, a.fl")
        if key_el and val_el:
            key = key_el.get_text(strip=True).rstrip(":")
            result["attributes"][key] = val_el.get_text(strip=True)

    return result


def _parse_paa(soup: BeautifulSoup) -> list[dict]:
    """Extract 'People Also Ask' questions."""
    questions = []
    for el in soup.select("div[data-q]"):
        question = el.get("data-q", "").strip()
        if question:
            questions.append({"question": question})

    # Fallback selector
    if not questions:
        for el in soup.select("span.CSkcDe"):
            text = el.get_text(strip=True)
            if text and text.endswith("?"):
                questions.append({"question": text})

    return questions


def _parse_related(soup: BeautifulSoup) -> list[dict]:
    """Extract related searches shown at the bottom."""
    related = []
    for el in soup.select("div.k8XOCe a, a.k8XOCe"):
        text = el.get_text(strip=True)
        if text:
            related.append({"query": text})

    # Fallback
    if not related:
        for el in soup.select("#brs a"):
            text = el.get_text(strip=True)
            if text:
                related.append({"query": text})

    return related
