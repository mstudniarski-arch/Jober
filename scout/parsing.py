"""Parsowanie znalezisk z odpowiedzi modelu (fenced block ```json)."""
import json
import re
from dataclasses import dataclass


class ParseError(Exception):
    """Odpowiedź modelu nie zawiera poprawnego bloku JSON ze znaleziskami."""


@dataclass
class Finding:
    company: str
    role: str
    apply_url: str
    project: str | None = None
    salary: str | None = None
    signal_type: str = "job_posting"
    source_url: str | None = None
    location: str | None = None
    published_at: str | None = None


_JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.DOTALL)


def extract_findings(text: str) -> list[Finding]:
    blocks = _JSON_BLOCK.findall(text or "")
    if not blocks:
        raise ParseError("Brak bloku ```json w odpowiedzi modelu")
    try:
        data = json.loads(blocks[-1])
    except json.JSONDecodeError as e:
        raise ParseError(f"Nieparsowalny JSON: {e}") from e
    items = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ParseError("JSON nie zawiera listy 'findings'")

    findings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        company = str(item.get("company") or "").strip()
        role = str(item.get("role") or "").strip()
        if not company or not role:
            continue
        findings.append(Finding(
            company=company,
            role=role,
            apply_url=str(item.get("apply_url") or "").strip(),
            project=item.get("project") or None,
            salary=item.get("salary") or None,
            signal_type=str(item.get("signal_type") or "job_posting"),
            source_url=item.get("source_url") or None,
            location=item.get("location") or None,
            published_at=item.get("published_at") or None,
        ))
    return findings
