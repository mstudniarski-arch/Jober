from datetime import date

from scout.parsing import Finding
from scout.report import render_report

D = date(2026, 7, 12)


def test_report_renders_all_fields():
    f = Finding(company="Acme", role="Senior SDET", apply_url="https://acme.com/jobs/1",
                project="payments platform", salary="$120k-150k",
                signal_type="career_page", source_url="https://acme.com/careers",
                location="Remote (worldwide)")
    out = render_report([f], D, web_searches=18, duplicates=3)
    assert "# Hidden Job Scout — raport 2026-07-12" in out
    assert "## Strony karier firm" in out
    assert "### Acme — Senior SDET" in out
    assert "- **Firma:** Acme" in out
    assert "- **Projekt:** payments platform" in out
    assert "- **Rola:** Senior SDET" in out
    assert "- **Zarobki:** $120k-150k" in out
    assert "- **Lokalizacja:** Remote (worldwide)" in out
    assert "- **Link do aplikowania:** https://acme.com/jobs/1" in out
    assert "- **Źródło:** https://acme.com/careers" in out
    assert "Wyszukiwań web: 18" in out
    assert "Nowe znaleziska: 1" in out
    assert "Odfiltrowane duplikaty: 3" in out


def test_missing_optional_fields_render_as_dash():
    f = Finding(company="Beta", role="AI tester", apply_url="")
    out = render_report([f], D, web_searches=0, duplicates=0)
    assert "- **Projekt:** —" in out
    assert "- **Zarobki:** —" in out
    assert "- **Link do aplikowania:** —" in out
    assert "Źródło" not in out  # brak source_url -> linia pomijana


def test_empty_findings():
    out = render_report([], D, web_searches=20, duplicates=5)
    assert "Brak nowych znalezisk" in out


def test_groups_by_signal_type_with_unknown_as_other():
    findings = [
        Finding(company="A", role="QA", apply_url="https://a.io/1", signal_type="linkedin_post"),
        Finding(company="B", role="QA", apply_url="https://b.io/1", signal_type="job_posting"),
        Finding(company="C", role="QA", apply_url="https://c.io/1", signal_type="weird_type"),
    ]
    out = render_report(findings, D, web_searches=1, duplicates=0)
    assert "## Posty na LinkedIn" in out
    assert "## Ogłoszenia o pracę" in out
    assert "## Inne sygnały" in out
    # linkedin przed job_posting w kolejności sekcji
    assert out.index("Posty na LinkedIn") < out.index("Ogłoszenia o pracę")
