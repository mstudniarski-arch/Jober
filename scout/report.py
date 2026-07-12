"""Render raportu Markdown z listy znalezisk."""
from datetime import date

from scout.parsing import Finding

SIGNAL_LABELS = {
    "linkedin_post": "Posty na LinkedIn",
    "career_page": "Strony karier firm",
    "funding_news": "Sygnały finansowania i ekspansji",
    "recruiter_post": "Rekruterzy",
    "job_posting": "Ogłoszenia o pracę",
}
_OTHER = "Inne sygnały"


def render_report(findings: list, report_date: date, web_searches: int, duplicates: int) -> str:
    lines = [f"# Hidden Job Scout — raport {report_date.isoformat()}", ""]
    if not findings:
        lines += ["Brak nowych znalezisk w tym przebiegu.", ""]
    else:
        by_signal: dict = {}
        for f in findings:
            signal = f.signal_type if f.signal_type in SIGNAL_LABELS else "_other"
            by_signal.setdefault(signal, []).append(f)
        order = [s for s in SIGNAL_LABELS if s in by_signal] + (["_other"] if "_other" in by_signal else [])
        for signal in order:
            lines += [f"## {SIGNAL_LABELS.get(signal, _OTHER)}", ""]
            for f in by_signal[signal]:
                lines += _render_finding(f)
    lines += ["---", f"*Wyszukiwań web: {web_searches} · Nowe znaleziska: {len(findings)} · "
              f"Odfiltrowane duplikaty: {duplicates}*", ""]
    return "\n".join(lines)


def _render_finding(f: Finding) -> list:
    lines = [
        f"### {f.company} — {f.role}",
        "",
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
