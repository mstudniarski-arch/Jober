import json
from datetime import date
from pathlib import Path

from scout.main import run
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
    assert run(cfg, client=client, report_date=D) == 0

    report = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    assert "Acme — SDET" in report
    assert "Wyszukiwań web: 1" in report

    seen = json.loads((tmp_path / "data" / "seen.json").read_text(encoding="utf-8"))
    assert seen["seen"] == ["acme.com/jobs/1"]


def test_second_run_filters_duplicates(tmp_path):
    cfg = write_config(tmp_path)
    run(cfg, client=FakeClient([fake_response(ANSWER)]), report_date=D)
    run(cfg, client=FakeClient([fake_response(ANSWER)]), report_date=date(2026, 7, 13))

    report2 = (tmp_path / "reports" / "2026-07-13.md").read_text(encoding="utf-8")
    assert "Brak nowych znalezisk" in report2
    assert "Odfiltrowane duplikaty: 1" in report2


def test_unparseable_answer_writes_raw_fallback(tmp_path):
    cfg = write_config(tmp_path)
    client = FakeClient([fake_response("no json here, sorry")])
    assert run(cfg, client=client, report_date=D) == 0

    raw = tmp_path / "reports" / "2026-07-12-raw.md"
    assert raw.read_text(encoding="utf-8") == "no json here, sorry"
    assert not (tmp_path / "reports" / "2026-07-12.md").exists()
