"""Render raportu Markdown z listy znalezisk."""
from datetime import date, datetime, timezone

from scout.parsing import Finding

SIGNAL_LABELS = {
    "linkedin_post": "Posty na LinkedIn",
    "career_page": "Strony karier firm",
    "funding_news": "Sygnały finansowania i ekspansji",
    "recruiter_post": "Rekruterzy",
    "job_posting": "Ogłoszenia o pracę",
}
_OTHER = "Inne sygnały"

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _parse_published(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_published(value):
    parsed = _parse_published(value)
    if parsed:
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return value or "—"


def render_report(findings: list, report_date: date, web_searches: int, duplicates: int) -> str:
    lines = [f"# Hidden Job Scout — raport {report_date.isoformat()}", ""]
    if not findings:
        lines += ["Brak nowych znalezisk w tym przebiegu.", ""]
    else:
        lines += ["Najświeższe zdalne oferty z całego świata, posortowane od najnowszych.", ""]
        ordered = sorted(
            findings,
            key=lambda f: _parse_published(f.published_at) or _EPOCH,
            reverse=True,
        )
        for finding in ordered:
            lines += _render_finding(finding)
    lines += ["---", f"*Wyszukiwań web: {web_searches} · Nowe znaleziska: {len(findings)} · "
              f"Odfiltrowane duplikaty: {duplicates}*", ""]
    return "\n".join(lines)


def _render_finding(f: Finding) -> list:
    lines = [
        f"### {f.company} — {f.role}",
        "",
        f"- **Opublikowano:** {_format_published(f.published_at)}",
        f"- **Typ sygnału:** {SIGNAL_LABELS.get(f.signal_type, _OTHER)}",
        f"- **Firma:** {f.company}",
        f"- **Projekt:** {f.project or '—'}",
        f"- **Rola:** {f.role}",
        f"- **Zarobki:** {f.salary or '—'}",
        f"- **Lokalizacja:** {f.location or 'Remote'}",
        f"- **Link do aplikowania:** {f.apply_url or '—'}",
    ]
    if f.source_url and f.source_url != f.apply_url:
        lines.append(f"- **Źródło:** {f.source_url}")
    lines.append("")
    return lines
