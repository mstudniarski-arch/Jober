"""Wyszukiwanie ofert w DuckDuckGo (ddgs) — bez klucza API."""
import logging
import time

logger = logging.getLogger(__name__)

_AD_MARKERS = ("bing.com/aclick", "duckduckgo.com/y.js", "googleadservices")


def _ddg_search(query, max_results):
    from ddgs import DDGS
    return DDGS().text(query, timelimit="d", max_results=max_results)


def build_queries(roles) -> list:
    return [f'"{role}" remote job apply' for role in roles]


def search_offers(roles, search_fn=None, per_query=6, pause=2.0, sleep=time.sleep):
    """Zwraca (wyniki bez duplikatów i reklam, liczba zapytań)."""
    search_fn = search_fn or _ddg_search
    queries = build_queries(roles)
    results, seen_urls = [], set()
    for i, query in enumerate(queries):
        try:
            hits = search_fn(query, per_query) or []
        except Exception as e:
            logger.warning("DDG: zapytanie %r nieudane (%s) — pomijam", query, e)
            hits = []
        for hit in hits:
            url = (hit.get("href") or hit.get("url") or "").strip()
            if not url or url in seen_urls or any(marker in url for marker in _AD_MARKERS):
                continue
            seen_urls.add(url)
            results.append({"title": hit.get("title") or "", "url": url,
                            "body": (hit.get("body") or "")[:300]})
        if i < len(queries) - 1:
            sleep(pause)
    logger.info("DDG: %d zapytań, %d unikalnych wyników", len(queries), len(results))
    return results, len(queries)
