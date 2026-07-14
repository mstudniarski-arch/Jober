from datetime import date

from scout.parsing import Finding
from scout.report import render_report

D = date(2026, 7, 12)


def test_report_renders_all_fields():
    f = Finding(company="Acme", role="Senior SDET", apply_url="https://acme.com/jobs/1",
                project="payments platform", salary="$120k-150k",
                signal_type="career_page", source_url="https://acme.com/careers",
                location="Remote (worldwide)", published_at="2026-07-12T09:30:00Z")
    out = render_report([f], D, web_searches=18, duplicates=3, dead_links=2)
    assert "# Hidden Job Scout — raport 2026-07-12" in out
    assert "### Acme — Senior SDET" in out
    assert "- **Opublikowano:** 2026-07-12 09:30 UTC" in out
    assert "- **Typ sygnału:** Strony karier firm" in out
    assert "- **Firma:** Acme" in out
    assert "- **Projekt:** payments platform" in out
    assert "- **Rola:** Senior SDET" in out
    assert "- **Zarobki:** $120k-150k" in out
    assert "- **Lokalizacja:** Remote (worldwide)" in out
    assert "- **Link do aplikowania:** https://acme.com/jobs/1" in out
    assert "- **Źródło:** https://acme.com/careers" in out
    assert "Wyszukiwań web: 18" in out
    assert "Odfiltrowane duplikaty: 3" in out
    assert "Martwe linki: 2" in out


def test_sorted_freshest_first_and_unknown_dates_last():
    old = Finding(company="Old", role="QA", apply_url="https://o.io/1",
                  published_at="2026-07-11T10:00:00Z")
    new = Finding(company="New", role="SDET", apply_url="https://n.io/1",
                  published_at="2026-07-12T09:00:00Z")
    undated = Finding(company="Undated", role="Tester", apply_url="https://u.io/1")
    out = render_report([old, undated, new], D, web_searches=1, duplicates=0)
    assert out.index("New — SDET") < out.index("Old — QA") < out.index("Undated — Tester")
    assert "- **Opublikowano:** —" in out


def test_missing_optional_fields_render_as_dash():
    f = Finding(company="Beta", role="AI tester", apply_url="")
    out = render_report([f], D, web_searches=0, duplicates=0)
    assert "- **Projekt:** —" in out
    assert "- **Zarobki:** —" in out
    assert "- **Link do aplikowania:** —" in out
    assert "- **Typ sygnału:** Ogłoszenia o pracę" in out
    assert "Źródło" not in out


def test_empty_findings():
    out = render_report([], D, web_searches=20, duplicates=5)
    assert "Brak nowych znalezisk" in out
