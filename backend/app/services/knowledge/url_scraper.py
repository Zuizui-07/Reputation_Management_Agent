"""
================================================
  URL Scraper — Recursive full-site crawler
================================================
Crawls an entire website by following internal links.
Stays within the same domain, respects max depth and page limits.
"""

import logging
import re
from typing import List, Dict, Any, Set
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Elements to strip from pages
STRIP_TAGS = [
    "script", "style", "noscript", "iframe", "svg",
    "nav", "footer", "header",
]

# File extensions to skip
SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp4", ".mp3", ".avi", ".mov", ".zip", ".tar", ".gz",
    ".css", ".js", ".ico", ".woff", ".woff2", ".ttf", ".eot",
}


def _is_same_domain(url: str, base_domain: str) -> bool:
    """Check if a URL belongs to the same domain."""
    try:
        parsed = urlparse(url)
        return parsed.netloc == base_domain or parsed.netloc == ""
    except Exception:
        return False


def _should_skip_url(url: str) -> bool:
    """Skip URLs with non-content file extensions or fragments."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    return any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS)


def _clean_url(url: str) -> str:
    """Normalize a URL by removing fragments and trailing slashes."""
    parsed = urlparse(url)
    # Rebuild without fragment
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        clean += f"?{parsed.query}"
    return clean.rstrip("/")


def _extract_text(soup: BeautifulSoup) -> str:
    """Extract clean body text from a BeautifulSoup object."""
    # Remove unwanted tags
    for tag_name in STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Get text from body, or full page if no body
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    # Remove lines that are too short (likely menu items, buttons)
    meaningful_lines = [line for line in text.splitlines() if len(line) > 10]
    return "\n".join(meaningful_lines)


def _extract_links(soup: BeautifulSoup, base_url: str, base_domain: str) -> List[str]:
    """Extract all internal links from a page."""
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        # Skip anchors, javascript, mailto, tel
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        # Only keep same-domain links
        if _is_same_domain(full_url, base_domain) and not _should_skip_url(full_url):
            links.append(_clean_url(full_url))
    return links


async def crawl_website(
    root_url: str,
    max_depth: int = 3,
    max_pages: int = 50,
) -> List[Dict[str, Any]]:
    """
    Recursively crawl a website starting from root_url.

    Args:
        root_url: The starting URL to crawl.
        max_depth: Maximum link-following depth (default: 3).
        max_pages: Maximum number of pages to scrape (default: 50).

    Returns:
        List of dicts: [{ "text": str, "metadata": { "url": str, "title": str, "depth": int } }]
    """
    parsed_root = urlparse(root_url)
    base_domain = parsed_root.netloc
    root_clean = _clean_url(root_url)

    visited: Set[str] = set()
    results: List[Dict[str, Any]] = []

    # BFS queue: (url, depth)
    queue: List[tuple] = [(root_clean, 0)]

    logger.info(f"Starting recursive crawl of {base_domain} (max_depth={max_depth}, max_pages={max_pages})")

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ReputationAgent/1.0)"},
    ) as client:
        while queue and len(results) < max_pages:
            url, depth = queue.pop(0)

            # Skip if already visited or too deep
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            try:
                response = await client.get(url)
                response.raise_for_status()

                # Only process HTML content
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    continue

                soup = BeautifulSoup(response.text, "lxml")

                # Extract title
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else url

                # Extract text
                text = _extract_text(soup)
                if text and len(text) > 50:  # Skip near-empty pages
                    results.append({
                        "text": text,
                        "metadata": {
                            "url": url,
                            "title": title,
                            "depth": depth,
                            "source_type": "url",
                        },
                    })
                    logger.info(f"  ✓ Crawled [{depth}] {url} ({len(text)} chars)")

                # Extract and queue internal links
                if depth < max_depth:
                    new_links = _extract_links(soup, url, base_domain)
                    for link in new_links:
                        if link not in visited:
                            queue.append((link, depth + 1))

            except httpx.HTTPStatusError as e:
                logger.warning(f"  ✗ HTTP {e.response.status_code} for {url}")
            except httpx.RequestError as e:
                logger.warning(f"  ✗ Request failed for {url}: {e}")
            except Exception as e:
                logger.warning(f"  ✗ Error crawling {url}: {e}")

    logger.info(f"Crawl complete: {len(results)} pages scraped from {base_domain}")
    return results
