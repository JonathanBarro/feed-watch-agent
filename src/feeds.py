"""Download and parse RSS 2.0 and Atom feeds into a common item format."""

import logging
import re
from html import unescape
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger("feed-watch.feeds")

ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "feed-watch-agent/1.0 (+https://github.com/)"
TIMEOUT_SECONDS = 30
SUMMARY_MAX_CHARS = 300


def _clean(text: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_feed(xml_text: str, feed_name: str) -> list[dict]:
    """Parse the XML of one feed. Returns [] if it is not valid XML."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("Feed '%s' is not valid XML: %s", feed_name, exc)
        return []

    items = []
    for node in root.findall("./channel/item"):  # RSS 2.0
        link = (node.findtext("link") or "").strip()
        items.append({
            "id": (node.findtext("guid") or link).strip(),
            "title": _clean(node.findtext("title")),
            "date": (node.findtext("pubDate") or "").strip(),
            "summary": _clean(node.findtext("description"))[:SUMMARY_MAX_CHARS],
            "url": link,
            "feed": feed_name,
        })
    for node in root.findall(f"{ATOM}entry"):  # Atom
        link_node = node.find(f"{ATOM}link")
        link = (link_node.get("href") if link_node is not None else "") or ""
        items.append({
            "id": (node.findtext(f"{ATOM}id") or link).strip(),
            "title": _clean(node.findtext(f"{ATOM}title")),
            "date": (node.findtext(f"{ATOM}updated") or node.findtext(f"{ATOM}published") or "").strip(),
            "summary": _clean(node.findtext(f"{ATOM}summary") or node.findtext(f"{ATOM}content"))[:SUMMARY_MAX_CHARS],
            "url": link.strip(),
            "feed": feed_name,
        })
    return [item for item in items if item["id"]]


def fetch_feed(feed: dict) -> list[dict]:
    """Download one feed ({name, url}). A failing feed never stops the others."""
    name, url = feed.get("name", "?"), feed.get("url")
    if not url:
        return []
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Could not download feed '%s': %s", name, exc)
        return []
    items = parse_feed(response.text, name)
    logger.info("Feed '%s': %s item(s)", name, len(items))
    return items


def matches_keywords(item: dict, keywords: list[str]) -> bool:
    """True if there are no keywords, or any keyword appears in the title or summary."""
    if not keywords:
        return True
    haystack = f"{item['title']} {item['summary']}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)
