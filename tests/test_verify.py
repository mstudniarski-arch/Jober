from scout.parsing import Finding
from scout.verify import verify_findings


def make(url, company="Acme"):
    return Finding(company=company, role="SDET", apply_url=url)


def fake_fetch(responses):
    def fetch(url):
        return responses[url]
    return fetch


def test_drops_404_and_410():
    findings = [make("https://a.io/1", "A"), make("https://b.io/1", "B"), make("https://c.io/1", "C")]
    fetch = fake_fetch({
        "https://a.io/1": (200, "apply now"),
        "https://b.io/1": (404, ""),
        "https://c.io/1": (410, ""),
    })
    kept, dropped = verify_findings(findings, fetch=fetch)
    assert [f.company for f in kept] == ["A"]
    assert [f.company for f in dropped] == ["B", "C"]


def test_drops_expired_page_returning_200():
    findings = [make("https://a.io/1")]
    fetch = fake_fetch({"https://a.io/1": (200, "<html>This job is no longer available.</html>")})
    kept, dropped = verify_findings(findings, fetch=fetch)
    assert kept == []
    assert len(dropped) == 1


def test_keeps_bot_blocked_and_transient_errors():
    findings = [make("https://a.io/1", "A"), make("https://b.io/1", "B"), make("https://c.io/1", "C")]
    fetch = fake_fetch({
        "https://a.io/1": (403, ""),   # blokada anty-botowa
        "https://b.io/1": (999, ""),   # LinkedIn
        "https://c.io/1": (-1, ""),    # timeout — błąd przejściowy
    })
    kept, dropped = verify_findings(findings, fetch=fetch)
    assert len(kept) == 3
    assert dropped == []


def test_drops_unreachable_domain_and_keeps_missing_url():
    findings = [make("https://ghost.example/1", "Ghost"), make("", "NoUrl")]
    fetch = fake_fetch({"https://ghost.example/1": (None, "")})
    kept, dropped = verify_findings(findings, fetch=fetch)
    assert [f.company for f in kept] == ["NoUrl"]
    assert [f.company for f in dropped] == ["Ghost"]
