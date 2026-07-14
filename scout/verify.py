"""Weryfikacja linków znalezisk — odrzucanie martwych i nieaktualnych ofert."""
import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

logger = logging.getLogger(__name__)

_DEAD_STATUSES = {404, 410}
_EXPIRED_MARKERS = (
    "no longer accepting applications",
    "job is no longer available",
    "position is no longer available",
    "this job has expired",
    "this position has been filled",
    "job posting has expired",
    "job has been closed",
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _fetch(url: str):
    """Zwraca (status, fragment treści strony).

    (None, "")  — domena nieosiągalna (np. zmyślona),
    (-1, "")    — błąd przejściowy (timeout itp.) — oferty nie karzemy.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=8.0, headers=_HEADERS) as client:
            response = client.get(url)
        return response.status_code, response.text[:65536]
    except httpx.ConnectError:
        return None, ""
    except httpx.HTTPError:
        return -1, ""


def _is_alive(fetch, finding) -> bool:
    url = (finding.apply_url or "").strip()
    if not url.startswith(("http://", "https://")):
        return True  # brak linku HTTP (np. sygnał) — nie weryfikujemy
    status, text = fetch(url)
    if status is None or status in _DEAD_STATUSES:
        return False
    if status is not None and 0 <= status < 400:
        lowered = text.lower()
        if any(marker in lowered for marker in _EXPIRED_MARKERS):
            return False
    return True


def verify_findings(findings, fetch=_fetch, max_workers=8):
    """Dzieli znaleziska na (żywe, martwe) sprawdzając apply_url przez HTTP."""
    if not findings:
        return [], []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        alive_flags = list(pool.map(lambda f: _is_alive(fetch, f), findings))
    kept = [f for f, alive in zip(findings, alive_flags) if alive]
    dropped = [f for f, alive in zip(findings, alive_flags) if not alive]
    for finding in dropped:
        logger.info("Martwy/nieaktualny link — odrzucam: %s (%s)", finding.apply_url, finding.company)
    return kept, dropped
