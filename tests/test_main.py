import json
from datetime import date
from pathlib import Path

import pytest
from google.genai import errors as genai_errors

from scout.config import ScoutConfig
from scout.main import _scan_with_retry, run
from tests.fakes import FakeClient, fake_response

D = date(2026, 7, 12)

ANSWER = """Research done.

```json
{"findings": [
  {"company": "Acme", "role": "SDET", "apply_url": "https://acme.com/jobs/1",
   "project": "payments", "salary": "$100k", "signal_type": "career_page",
   "source_url": "https://acme.com/careers", "location": "Remote (worldwide)"}
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
    client = FakeClient([fake_response(ANSWER, queries=["remote sdet jobs"])])
    assert run(cfg, client=client, report_date=D, verify=no_verify) == 0

    report = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    assert "Acme — SDET" in report
    assert "Wyszukiwań web: 1" in report

    seen = json.loads((tmp_path / "data" / "seen.json").read_text(encoding="utf-8"))
    assert seen["seen"] == ["acme.com/jobs/1"]


def test_second_run_filters_duplicates(tmp_path):
    cfg = write_config(tmp_path)
    run(cfg, client=FakeClient([fake_response(ANSWER)]), report_date=D, verify=no_verify)
    run(cfg, client=FakeClient([fake_response(ANSWER)]), report_date=date(2026, 7, 13), verify=no_verify)

    report2 = (tmp_path / "reports" / "2026-07-13.md").read_text(encoding="utf-8")
    assert "Brak nowych znalezisk" in report2
    assert "Odfiltrowane duplikaty: 1" in report2


def test_unparseable_answer_writes_raw_fallback(tmp_path):
    cfg = write_config(tmp_path)
    client = FakeClient([fake_response("no json here, sorry")])
    assert run(cfg, client=client, report_date=D, verify=no_verify) == 0

    raw = tmp_path / "reports" / "2026-07-12-raw.md"
    assert raw.read_text(encoding="utf-8") == "no json here, sorry"
    assert not (tmp_path / "reports" / "2026-07-12.md").exists()


def test_second_run_same_day_does_not_overwrite_report(tmp_path):
    cfg = write_config(tmp_path)
    run(cfg, client=FakeClient([fake_response(ANSWER)]), report_date=D, verify=no_verify)
    first = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    run(cfg, client=FakeClient([fake_response(ANSWER)]), report_date=D, verify=no_verify)
    assert (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8") == first
    assert len(list((tmp_path / "reports").glob("*.md"))) == 2


CONFIG = ScoutConfig(roles=["SDET"])


def _server_error():
    return genai_errors.ServerError(
        503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


def test_retry_on_server_error_then_success():
    client = FakeClient([_server_error(), _server_error(), fake_response("done")])
    delays = []
    result = _scan_with_retry(client, CONFIG, sleep=delays.append)
    assert result.text == "done"
    assert delays == [60, 120]  # backoff między próbami
    assert len(client.models.calls) == 3


def test_retry_on_429_rate_limit():
    rate_limited = genai_errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    client = FakeClient([rate_limited, fake_response("done")])
    delays = []
    result = _scan_with_retry(client, CONFIG, sleep=delays.append)
    assert result.text == "done"
    assert delays == [60]


def test_no_retry_on_non_transient_client_error():
    bad_request = genai_errors.ClientError(
        400, {"error": {"code": 400, "message": "bad request", "status": "INVALID_ARGUMENT"}})
    client = FakeClient([bad_request])

    def sleep_forbidden(_):  # przy 400 nie wolno czekać ani ponawiać
        raise AssertionError("sleep nie powinien być wywołany")

    with pytest.raises(genai_errors.ClientError):
        _scan_with_retry(client, CONFIG, sleep=sleep_forbidden)
    assert len(client.models.calls) == 1


def test_retry_gives_up_after_four_attempts():
    client = FakeClient([_server_error() for _ in range(4)])
    delays = []
    with pytest.raises(genai_errors.ServerError):
        _scan_with_retry(client, CONFIG, sleep=delays.append)
    assert delays == [60, 120, 240]
    assert len(client.models.calls) == 4


def test_dead_links_are_dropped_counted_and_remembered(tmp_path):
    cfg = write_config(tmp_path)

    def drop_all(findings):
        return [], list(findings)

    client = FakeClient([fake_response(ANSWER)])
    assert run(cfg, client=client, report_date=D, verify=drop_all) == 0
    report = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    assert "Brak nowych znalezisk" in report
    assert "Martwe linki: 1" in report
    seen = json.loads((tmp_path / "data" / "seen.json").read_text(encoding="utf-8"))
    assert seen["seen"] == ["acme.com/jobs/1"]  # martwy link też zapamiętany

