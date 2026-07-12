"""Deduplikacja znalezisk względem stanu w data/seen.json."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from scout.parsing import Finding


def finding_key(finding: Finding) -> str:
    url = (finding.apply_url or "").strip().lower()
    if url:
        parts = urlsplit(url)
        host = parts.netloc.removeprefix("www.")
        if host:
            key = f"{host}{parts.path.rstrip('/')}"
            if parts.query:
                key += f"?{parts.query}"
            return key
    return f"{finding.company.strip().lower()}|{finding.role.strip().lower()}"


def load_seen(path) -> set:
    p = Path(path)
    if not p.exists():
        return set()
    data = json.loads(p.read_text(encoding="utf-8") or "{}")
    return set(data.get("seen", []))


def filter_new(findings: list, seen: set) -> list:
    new, batch_keys = [], set()
    for finding in findings:
        key = finding_key(finding)
        if key in seen or key in batch_keys:
            continue
        batch_keys.add(key)
        new.append(finding)
    return new


def save_seen(path, seen: set) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"seen": sorted(seen)}, ensure_ascii=False, indent=2)
    p.write_text(text + "\n", encoding="utf-8")
