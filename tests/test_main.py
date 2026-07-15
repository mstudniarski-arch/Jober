import json
from datetime import date
from pathlib import Path

import groq
import httpx
import pytest

from scout.config import ScoutConfig
from scout.main import _scan_with_retry, run
from tests.fakes import FakeClient, fake_completion, no_search

D = date(2026, 7, 12)

ANSWER = """Research done.

```json
{"findings": [
  {"company": "Acme", "role": "SDET", "apply_url": "https://acme.com/jobs/1",
   "project": "payments", "salary": "$100k", "signal_type": "career_page",
   "source_url": "https://acme.com/careers", "location": "Remote (worldwide)"}
]}
```"""

AI_ANSWER = """Research done.

```json
{"findings": [
  {"company": "NeuralWorks", "role": "Junior AI Engineer",
   "apply_url": "https://neural.works/jobs/7", "signal_type": "job_posting",
   "location": "Remote (worldwide)"},
  {"company": "BigCorp", "role": "Senior AI Engineer",
   "apply_url": "https://bigcorp.io/jobs/9", "signal_type": "job_posting",
   "location": "Remote (worldwide)"}
]}
```"""


def no_verify(findings):
    return list(findings), []


def write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "roles: [SDET]\n"
        f"reports_dir: {tmp_path / 'reports'}\n"
        f"seen_file: {tmp_path / 'data' / 'seen.json'}\n"
        f"logs_dir: {tmp_path / 'logs'}\n",
        encoding="utf-8",
    )
    return cfg


def test_run_writes_report_and_updates_seen(tmp_path):
    cfg = write_config(tmp_path)
    client = FakeClient([fake_completion(ANSWER)])
    assert run(cfg, client=client, report_date=D, verify=no_verify, search_fn=no_search) == 0

    report = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    assert "Acme — SDET" in report
    assert "Wyszukiwań web: 1" in report

    seen = json.loads((tmp_path / "data" / "seen.json").read_text(encoding="utf-8"))
    assert seen["seen"] == ["acme.com/jobs/1"]


def test_second_run_filters_duplicates(tmp_path):
    cfg = write_config(tmp_path)
    run(cfg, client=FakeClient([fake_completion(ANSWER)]), report_date=D, verify=no_verify,
        search_fn=no_search)
    run(cfg, client=FakeClient([fake_completion(ANSWER)]), report_date=date(2026, 7, 13),
        verify=no_verify, search_fn=no_search)

    report2 = (tmp_path / "reports" / "2026-07-13.md").read_text(encoding="utf-8")
    assert "Brak nowych znalezisk" in report2
    assert "Odfiltrowane duplikaty: 1" in report2


def test_unparseable_answer_writes_raw_fallback(tmp_path):
    cfg = write_config(tmp_path)
    client = FakeClient([fake_completion("no json here, sorry")])
    assert run(cfg, client=client, report_date=D, verify=no_verify, search_fn=no_search) == 0

    raw = tmp_path / "reports" / "2026-07-12-raw.md"
    assert raw.read_text(encoding="utf-8") == "no json here, sorry"
    assert not (tmp_path / "reports" / "2026-07-12.md").exists()


def test_second_run_same_day_does_not_overwrite_report(tmp_path):
    cfg = write_config(tmp_path)
    run(cfg, client=FakeClient([fake_completion(ANSWER)]), report_date=D, verify=no_verify,
        search_fn=no_search)
    first = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    run(cfg, client=FakeClient([fake_completion(ANSWER)]), report_date=D, verify=no_verify,
        search_fn=no_search)
    assert (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8") == first
    assert len(list((tmp_path / "reports").glob("*.md"))) == 2


CONFIG = ScoutConfig(roles=["SDET"])


def _api_error(status, message):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status, request=request, json={"error": {"message": message}})
    if status == 429:
        return groq.RateLimitError(message, response=response, body=None)
    if status >= 500:
        return groq.InternalServerError(message, response=response, body=None)
    return groq.BadRequestError(message, response=response, body=None)


def _server_error():
    return _api_error(503, "high demand")


def test_retry_on_server_error_then_success():
    client = FakeClient([_server_error(), _server_error(), fake_completion("done")])
    delays = []
    result = _scan_with_retry(client, CONFIG, sleep=delays.append, search_fn=no_search)
    assert result.text == "done"
    assert delays == [60, 120]  # backoff między próbami
    assert len(client.calls) == 3


def test_retry_on_429_rate_limit():
    rate_limited = _api_error(429, "quota")
    client = FakeClient([rate_limited, fake_completion("done")])
    delays = []
    result = _scan_with_retry(client, CONFIG, sleep=delays.append, search_fn=no_search)
    assert result.text == "done"
    assert delays == [60]


def test_no_retry_on_non_transient_client_error():
    bad_request = _api_error(400, "bad request")
    client = FakeClient([bad_request])

    def sleep_forbidden(_):  # przy 400 nie wolno czekać ani ponawiać
        raise AssertionError("sleep nie powinien być wywołany")

    with pytest.raises(groq.BadRequestError):
        _scan_with_retry(client, CONFIG, sleep=sleep_forbidden, search_fn=no_search)
    assert len(client.calls) == 1


def test_retry_gives_up_after_four_attempts():
    client = FakeClient([_server_error() for _ in range(4)])
    delays = []
    with pytest.raises(groq.InternalServerError):
        _scan_with_retry(client, CONFIG, sleep=delays.append, search_fn=no_search)
    assert delays == [60, 120, 240]
    assert len(client.calls) == 4


def test_dead_links_are_dropped_counted_and_remembered(tmp_path):
    cfg = write_config(tmp_path)

    def drop_all(findings):
        return [], list(findings)

    client = FakeClient([fake_completion(ANSWER)])
    assert run(cfg, client=client, report_date=D, verify=drop_all, search_fn=no_search) == 0
    report = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    assert "Brak nowych znalezisk" in report
    assert "Martwe linki: 1" in report
    seen = json.loads((tmp_path / "data" / "seen.json").read_text(encoding="utf-8"))
    assert seen["seen"] == ["acme.com/jobs/1"]  # martwy link też zapamiętany


def write_config_with_ai(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "roles: [SDET]\n"
        "ai_roles: [Junior AI Engineer, AI Engineer]\n"
        f"reports_dir: {tmp_path / 'reports'}\n"
        f"seen_file: {tmp_path / 'data' / 'seen.json'}\n"
        f"logs_dir: {tmp_path / 'logs'}\n",
        encoding="utf-8",
    )
    return cfg


def test_ai_section_scanned_filtered_and_rendered(tmp_path):
    cfg = write_config_with_ai(tmp_path)
    client = FakeClient([fake_completion(ANSWER), fake_completion(AI_ANSWER)])
    assert run(cfg, client=client, report_date=D, verify=no_verify, search_fn=no_search) == 0
    assert len(client.calls) == 2  # osobny skan QA i osobny AI
    assert "Junior AI Engineer" in client.calls[1]["messages"][0]["content"]

    report = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    assert "## AI Jobs" in report
    assert "NeuralWorks — Junior AI Engineer" in report
    assert "Senior AI Engineer" not in report  # twardy filtr Senior
    assert report.index("Acme — SDET") < report.index("## AI Jobs")

    seen = json.loads((tmp_path / "data" / "seen.json").read_text(encoding="utf-8"))
    assert "neural.works/jobs/7" in seen["seen"]
