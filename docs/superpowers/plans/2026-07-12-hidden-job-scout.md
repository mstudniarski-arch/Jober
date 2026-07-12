# Hidden Job Scout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily agent that scans the web (via Claude Opus 4.8 + server-side web search) for remote QA/SDET job opportunities and hidden-job-market signals, writing a deduplicated Markdown report into the repo.

**Architecture:** A single Python package (`scout/`) with one API call per run: `claude-opus-4-8` + `web_search_20260209` server tool does all searching; the script parses a fenced JSON block from the final answer, filters duplicates against `data/seen.json`, and renders `reports/YYYY-MM-DD.md`. Scheduling is external (GitHub Actions cron or launchd).

**Tech Stack:** Python 3.11+, `anthropic` SDK (streaming), `pyyaml`, `pytest`. No scraping libraries — searching happens server-side at Anthropic.

## Global Constraints

- Repo root: `/Users/mski/Developer/hidden-job-scout` (already a git repo, branch `main`). All paths below are relative to it.
- Model string exactly `claude-opus-4-8`; web search tool type exactly `web_search_20260209`, name `web_search`.
- `thinking={"type": "adaptive"}` on every API call; never `budget_tokens`, never `temperature`/`top_p`/`top_k`.
- Use `client.messages.stream(...)` + `get_final_message()` (max_tokens=32000 requires streaming).
- Default roles list (exact, in this order): SDET, QA engineer, tester, test engineer, test automation engineer, test developer, test lead, test manager, AI tester, AI test engineer, AI SDET.
- Report field labels in Polish: Firma, Projekt, Rola, Zarobki, Lokalizacja, Link do aplikowania, Źródło. Missing values render as `—`.
- Tests never call the live API. Use fakes from `tests/fakes.py`.
- All test commands run via `.venv/bin/pytest` from the repo root.
- Commit messages end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Scaffolding + config loading

**Files:**
- Create: `requirements.txt`, `.gitignore`, `config.yaml`, `data/seen.json`, `scout/__init__.py`, `tests/__init__.py`, `scout/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `scout.config.ScoutConfig` dataclass with fields `roles: list[str]`, `max_web_searches: int = 20`, `model: str = "claude-opus-4-8"`, `max_tokens: int = 32000`, `recency_days: int = 30`, `reports_dir: str = "reports"`, `seen_file: str = "data/seen.json"`, `logs_dir: str = "logs"`; and `scout.config.load_config(path: str | Path) -> ScoutConfig` raising `ValueError` when `roles` is missing/empty.

- [ ] **Step 1: Create the scaffolding files**

`requirements.txt`:

```
anthropic>=0.116.0
pyyaml>=6.0
pytest>=8.0
```

`.gitignore`:

```
__pycache__/
*.pyc
.venv/
.env
logs/
.pytest_cache/
```

`data/seen.json`:

```json
{"seen": []}
```

`scout/__init__.py` and `tests/__init__.py`: empty files.

`config.yaml`:

```yaml
# Hidden Job Scout — konfiguracja
# Role do wyszukiwania — dopisz/zmień dowolną, bez zmian w kodzie.
roles:
  - SDET
  - QA engineer
  - tester
  - test engineer
  - test automation engineer
  - test developer
  - test lead
  - test manager
  - AI tester
  - AI test engineer
  - AI SDET

# Limit wyszukiwań web na jeden przebieg (koszt ~$10/1000 wyszukiwań + tokeny)
max_web_searches: 20

model: claude-opus-4-8
max_tokens: 32000

# Oferty starsze niż tyle dni są pomijane
recency_days: 30

reports_dir: reports
seen_file: data/seen.json
logs_dir: logs
```

- [ ] **Step 2: Create venv and install dependencies**

Run:
```bash
cd /Users/mski/Developer/hidden-job-scout
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
Expected: successful install of anthropic, pyyaml, pytest.

- [ ] **Step 3: Write the failing test**

`tests/test_config.py`:

```python
from pathlib import Path

import pytest

from scout.config import ScoutConfig, load_config


def write_config(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_config_reads_roles_and_defaults(tmp_path):
    p = write_config(tmp_path, "roles:\n  - AI SDET\n  - tester\n")
    config = load_config(p)
    assert config.roles == ["AI SDET", "tester"]
    assert config.max_web_searches == 20
    assert config.model == "claude-opus-4-8"
    assert config.max_tokens == 32000
    assert config.recency_days == 30
    assert config.seen_file == "data/seen.json"


def test_load_config_overrides_defaults(tmp_path):
    p = write_config(tmp_path, "roles: [QA]\nmax_web_searches: 5\nmodel: claude-haiku-4-5\n")
    config = load_config(p)
    assert config.max_web_searches == 5
    assert config.model == "claude-haiku-4-5"


def test_load_config_requires_roles(tmp_path):
    p = write_config(tmp_path, "max_web_searches: 5\n")
    with pytest.raises(ValueError):
        load_config(p)


def test_load_config_ignores_unknown_keys(tmp_path):
    p = write_config(tmp_path, "roles: [QA]\nfuture_option: 42\n")
    config = load_config(p)
    assert isinstance(config, ScoutConfig)


def test_repo_config_yaml_is_valid():
    config = load_config(Path(__file__).parent.parent / "config.yaml")
    assert "SDET" in config.roles
    assert "AI SDET" in config.roles
    assert "AI tester" in config.roles
    assert "AI test engineer" in config.roles
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scout.config'`

- [ ] **Step 5: Write minimal implementation**

`scout/config.py`:

```python
"""Wczytywanie konfiguracji z config.yaml."""
from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass
class ScoutConfig:
    roles: list
    max_web_searches: int = 20
    model: str = "claude-opus-4-8"
    max_tokens: int = 32000
    recency_days: int = 30
    reports_dir: str = "reports"
    seen_file: str = "data/seen.json"
    logs_dir: str = "logs"


def load_config(path) -> ScoutConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("roles"):
        raise ValueError("config.yaml: pole 'roles' jest wymagane i nie może być puste")
    known = {f.name for f in fields(ScoutConfig)}
    return ScoutConfig(**{k: v for k, v in data.items() if k in known})
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore config.yaml data/seen.json scout tests
git commit -m "feat: szkielet projektu i wczytywanie konfiguracji

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Parsing model output (`scout/parsing.py`)

**Files:**
- Create: `scout/parsing.py`
- Test: `tests/test_parsing.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `scout.parsing.Finding` dataclass (fields: `company: str`, `role: str`, `apply_url: str`, `project: str | None = None`, `salary: str | None = None`, `signal_type: str = "job_posting"`, `source_url: str | None = None`, `location: str | None = None`); `scout.parsing.extract_findings(text: str) -> list[Finding]`; `scout.parsing.ParseError(Exception)`.

- [ ] **Step 1: Write the failing test**

`tests/test_parsing.py`:

````python
import pytest

from scout.parsing import Finding, ParseError, extract_findings

VALID = """Here is my research summary.

```json
{"findings": [
  {"company": "Acme", "role": "Senior SDET", "apply_url": "https://acme.com/jobs/1",
   "project": "payments platform", "salary": "$120k-150k",
   "signal_type": "career_page", "source_url": "https://acme.com/careers",
   "location": "Remote (worldwide)"},
  {"company": "Beta", "role": "AI tester", "apply_url": "https://beta.io/x",
   "salary": null}
]}
```"""


def test_extracts_findings_from_fenced_block():
    findings = extract_findings(VALID)
    assert len(findings) == 2
    f = findings[0]
    assert f == Finding(
        company="Acme", role="Senior SDET", apply_url="https://acme.com/jobs/1",
        project="payments platform", salary="$120k-150k", signal_type="career_page",
        source_url="https://acme.com/careers", location="Remote (worldwide)",
    )
    assert findings[1].salary is None
    assert findings[1].signal_type == "job_posting"  # default


def test_uses_last_json_block():
    text = '```json\n{"findings": []}\n```\nmore text\n' + VALID
    assert len(extract_findings(text)) == 2


def test_skips_entries_missing_company_or_role():
    text = '```json\n{"findings": [{"company": "X", "role": ""}, {"role": "QA"}, {"company": "OK", "role": "QA", "apply_url": ""}]}\n```'
    findings = extract_findings(text)
    assert len(findings) == 1
    assert findings[0].company == "OK"


def test_raises_when_no_json_block():
    with pytest.raises(ParseError):
        extract_findings("no code block here")


def test_raises_on_malformed_json():
    with pytest.raises(ParseError):
        extract_findings("```json\n{not json}\n```")


def test_raises_when_findings_not_a_list():
    with pytest.raises(ParseError):
        extract_findings('```json\n{"findings": "oops"}\n```')
````

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scout.parsing'`

- [ ] **Step 3: Write minimal implementation**

`scout/parsing.py`:

```python
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
        ))
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_parsing.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scout/parsing.py tests/test_parsing.py
git commit -m "feat: parsowanie znalezisk z bloku JSON w odpowiedzi modelu

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Deduplication (`scout/dedup.py`)

**Files:**
- Create: `scout/dedup.py`
- Test: `tests/test_dedup.py`

**Interfaces:**
- Consumes: `scout.parsing.Finding` (Task 2).
- Produces: `finding_key(finding: Finding) -> str` (normalized apply_url; fallback `"{company}|{role}"` lowercased), `load_seen(path) -> set[str]`, `filter_new(findings: list[Finding], seen: set[str]) -> list[Finding]` (also removes duplicates within the batch), `save_seen(path, seen: set[str]) -> None` (writes `{"seen": [sorted...]}`).

- [ ] **Step 1: Write the failing test**

`tests/test_dedup.py`:

```python
import json

from scout.dedup import filter_new, finding_key, load_seen, save_seen
from scout.parsing import Finding


def make(company="Acme", role="SDET", apply_url="https://acme.com/jobs/1"):
    return Finding(company=company, role=role, apply_url=apply_url)


def test_key_normalizes_url():
    assert finding_key(make(apply_url="HTTPS://WWW.Acme.com/jobs/1/")) == "acme.com/jobs/1"
    assert finding_key(make(apply_url="http://acme.com/jobs/1")) == "acme.com/jobs/1"


def test_key_keeps_query_string():
    assert finding_key(make(apply_url="https://boards.io/apply?id=42")) == "boards.io/apply?id=42"


def test_key_falls_back_to_company_and_role():
    assert finding_key(make(apply_url="")) == "acme|sdet"
    assert finding_key(Finding(company="Acme ", role=" QA Lead", apply_url="")) == "acme|qa lead"


def test_filter_new_removes_seen_and_batch_duplicates():
    seen = {"acme.com/jobs/1"}
    findings = [
        make(),  # already seen
        make(company="Beta", apply_url="https://beta.io/x"),
        make(company="Beta", apply_url="https://beta.io/x/"),  # dup within batch
    ]
    new = filter_new(findings, seen)
    assert [f.company for f in new] == ["Beta"]


def test_load_seen_missing_file_returns_empty_set(tmp_path):
    assert load_seen(tmp_path / "nope.json") == set()


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "data" / "seen.json"
    save_seen(path, {"b", "a"})
    assert load_seen(path) == {"a", "b"}
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"seen": ["a", "b"]}  # sorted, stable diffs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_dedup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scout.dedup'`

- [ ] **Step 3: Write minimal implementation**

`scout/dedup.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_dedup.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scout/dedup.py tests/test_dedup.py
git commit -m "feat: deduplikacja znalezisk po znormalizowanym URL

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Markdown report (`scout/report.py`)

**Files:**
- Create: `scout/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `scout.parsing.Finding` (Task 2).
- Produces: `render_report(findings: list[Finding], report_date: datetime.date, web_searches: int, duplicates: int) -> str`.

- [ ] **Step 1: Write the failing test**

`tests/test_report.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scout.report'`

- [ ] **Step 3: Write minimal implementation**

`scout/report.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_report.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add scout/report.py tests/test_report.py
git commit -m "feat: render raportu Markdown pogrupowanego po typie sygnału

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Anthropic API call (`scout/agent.py`)

**Files:**
- Create: `scout/agent.py`, `tests/fakes.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `scout.config.ScoutConfig` (Task 1).
- Produces: `scout.agent.ScanResult` dataclass (`text: str`, `web_searches: int`); `build_prompt(config: ScoutConfig) -> str`; `run_scan(client, config: ScoutConfig) -> ScanResult` (client = `anthropic.Anthropic()` or a fake with the same `messages.stream(**kwargs)` shape); `scout.agent.MAX_CONTINUATIONS = 5`. Test helpers in `tests/fakes.py`: `FakeClient(messages_to_return)`, `fake_message(text, stop_reason="end_turn", extra_blocks=())`, `text_block(text)`, `search_block()`.

- [ ] **Step 1: Write the test fakes**

`tests/fakes.py`:

```python
"""Fałszywy klient Anthropic do testów — bez sieci."""
from types import SimpleNamespace


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def search_block():
    return SimpleNamespace(type="server_tool_use", name="web_search")


def fake_message(text, stop_reason="end_turn", extra_blocks=()):
    return SimpleNamespace(stop_reason=stop_reason, content=[*extra_blocks, text_block(text)])


class _FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeMessages:
    def __init__(self, queue):
        self._queue = list(queue)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self._queue.pop(0))


class FakeClient:
    def __init__(self, messages_to_return):
        self.messages = _FakeMessages(messages_to_return)
```

- [ ] **Step 2: Write the failing test**

`tests/test_agent.py`:

```python
import pytest

from scout.agent import MAX_CONTINUATIONS, build_prompt, run_scan
from scout.config import ScoutConfig
from tests.fakes import FakeClient, fake_message, search_block

CONFIG = ScoutConfig(roles=["AI SDET", "QA engineer"], max_web_searches=7)


def test_build_prompt_contains_roles_scope_and_format():
    prompt = build_prompt(CONFIG)
    assert "- AI SDET" in prompt
    assert "- QA engineer" in prompt
    assert "remote" in prompt.lower()
    assert '"findings"' in prompt
    assert "30" in prompt  # recency_days


def test_run_scan_returns_text_and_search_count():
    msg = fake_message("final answer", extra_blocks=[search_block(), search_block()])
    client = FakeClient([msg])
    result = run_scan(client, CONFIG)
    assert result.text == "final answer"
    assert result.web_searches == 2
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["tools"] == [{"type": "web_search_20260209", "name": "web_search", "max_uses": 7}]
    assert call["max_tokens"] == 32000
    assert call["messages"][0]["role"] == "user"


def test_run_scan_continues_on_pause_turn():
    client = FakeClient([
        fake_message("partial", stop_reason="pause_turn"),
        fake_message("done"),
    ])
    result = run_scan(client, CONFIG)
    assert result.text == "done"
    assert len(client.messages.calls) == 2
    second = client.messages.calls[1]["messages"]
    assert second[0]["role"] == "user"
    assert second[1]["role"] == "assistant"  # doklejona odpowiedź do kontynuacji


def test_run_scan_raises_after_max_continuations():
    client = FakeClient([fake_message("p", stop_reason="pause_turn")] * (MAX_CONTINUATIONS + 1))
    with pytest.raises(RuntimeError):
        run_scan(client, CONFIG)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scout.agent'`

- [ ] **Step 4: Write minimal implementation**

`scout/agent.py`:

````python
"""Wywołanie Anthropic API: Opus 4.8 + serwerowe narzędzie web search."""
import logging
from dataclasses import dataclass

from scout.config import ScoutConfig

logger = logging.getLogger(__name__)

MAX_CONTINUATIONS = 5

_PROMPT = """You are a job-market research agent. Find CURRENT, fully remote job \
opportunities and hidden-job-market hiring signals, worldwide, for these roles:

{roles}

Search strategy — cover ALL of these angles, not just job boards:
1. LinkedIn posts by hiring managers, team leads, and employees announcing open roles \
("we're hiring", "join my team", "DM me").
2. Company career pages with relevant openings (prefer postings NOT syndicated to big aggregators).
3. Recent funding rounds, product launches, or expansion news implying the company is hiring \
QA/test engineers — then check their careers page.
4. Recruiter and executive-search posts looking for candidates for these roles.
5. Classic job postings as a supplement — only with a direct application link.

Constraints:
- Fully remote positions only (worldwide or broad-region remote). Skip onsite/hybrid.
- Only opportunities that appear posted or active within the last {recency_days} days.
- Prefer primary sources (the company's own page, the original LinkedIn post) over aggregators.
- Do not invent anything. Every finding must come from a page you actually found via search. \
If salary is not stated, use null.

After your research, end your reply with EXACTLY ONE fenced code block labeled json:

```json
{{"findings": [
  {{
    "company": "company name",
    "project": "what the company/team builds (short)",
    "role": "job title",
    "salary": "salary or range as stated, else null",
    "apply_url": "direct URL to apply or make contact",
    "signal_type": "job_posting | linkedin_post | career_page | funding_news | recruiter_post",
    "source_url": "URL where you found the signal",
    "location": "remote scope, e.g. 'Remote (worldwide)' or 'Remote (US only)'"
  }}
]}}
```

Include up to 25 of the best findings. The JSON block must be the last thing in your reply."""


@dataclass
class ScanResult:
    text: str
    web_searches: int


def build_prompt(config: ScoutConfig) -> str:
    roles = "\n".join(f"- {role}" for role in config.roles)
    return _PROMPT.format(roles=roles, recency_days=config.recency_days)


def _final_text(message) -> str:
    return "\n\n".join(b.text for b in message.content if getattr(b, "type", None) == "text")


def _count_web_searches(message) -> int:
    return sum(
        1 for b in message.content
        if getattr(b, "type", None) == "server_tool_use" and getattr(b, "name", "") == "web_search"
    )


def run_scan(client, config: ScoutConfig) -> ScanResult:
    user_message = {"role": "user", "content": build_prompt(config)}
    messages = [user_message]
    tools = [{"type": "web_search_20260209", "name": "web_search",
              "max_uses": config.max_web_searches}]

    for attempt in range(MAX_CONTINUATIONS + 1):
        with client.messages.stream(
            model=config.model,
            max_tokens=config.max_tokens,
            thinking={"type": "adaptive"},
            tools=tools,
            messages=messages,
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason != "pause_turn":
            return ScanResult(text=_final_text(message), web_searches=_count_web_searches(message))
        logger.info("pause_turn — kontynuacja %d/%d", attempt + 1, MAX_CONTINUATIONS)
        messages = [user_message, {"role": "assistant", "content": message.content}]

    raise RuntimeError(f"Skan nie zakończył się po {MAX_CONTINUATIONS} kontynuacjach pause_turn")
````

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agent.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add scout/agent.py tests/fakes.py tests/test_agent.py
git commit -m "feat: wywołanie Opus 4.8 z web search i obsługą pause_turn

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Orchestration + CLI (`scout/main.py`)

**Files:**
- Create: `scout/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5 (`load_config`, `run_scan`, `extract_findings`/`ParseError`, `load_seen`/`filter_new`/`finding_key`/`save_seen`, `render_report`).
- Produces: `scout.main.run(config_path="config.yaml", client=None, report_date=None) -> int` (0 = OK, also 0 for the raw-fallback path); `scout.main.main() -> int` (typed exception chain → exit codes 2–5); runnable via `python -m scout.main`.

- [ ] **Step 1: Write the failing test**

`tests/test_main.py`:

````python
import json
from datetime import date
from pathlib import Path

from scout.main import run
from tests.fakes import FakeClient, fake_message, search_block

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
    client = FakeClient([fake_message(ANSWER, extra_blocks=[search_block()])])
    assert run(cfg, client=client, report_date=D) == 0

    report = (tmp_path / "reports" / "2026-07-12.md").read_text(encoding="utf-8")
    assert "Acme — SDET" in report
    assert "Wyszukiwań web: 1" in report

    seen = json.loads((tmp_path / "data" / "seen.json").read_text(encoding="utf-8"))
    assert seen["seen"] == ["acme.com/jobs/1"]


def test_second_run_filters_duplicates(tmp_path):
    cfg = write_config(tmp_path)
    run(cfg, client=FakeClient([fake_message(ANSWER)]), report_date=D)
    run(cfg, client=FakeClient([fake_message(ANSWER)]), report_date=date(2026, 7, 13))

    report2 = (tmp_path / "reports" / "2026-07-13.md").read_text(encoding="utf-8")
    assert "Brak nowych znalezisk" in report2
    assert "Odfiltrowane duplikaty: 1" in report2


def test_unparseable_answer_writes_raw_fallback(tmp_path):
    cfg = write_config(tmp_path)
    client = FakeClient([fake_message("no json here, sorry")])
    assert run(cfg, client=client, report_date=D) == 0

    raw = tmp_path / "reports" / "2026-07-12-raw.md"
    assert raw.read_text(encoding="utf-8") == "no json here, sorry"
    assert not (tmp_path / "reports" / "2026-07-12.md").exists()
````

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scout.main'`

- [ ] **Step 3: Write minimal implementation**

`scout/main.py`:

```python
"""Entrypoint: jeden dzienny przebieg skanu."""
import logging
import sys
from datetime import date
from pathlib import Path

import anthropic

from scout.agent import run_scan
from scout.config import load_config
from scout.dedup import filter_new, finding_key, load_seen, save_seen
from scout.parsing import ParseError, extract_findings
from scout.report import render_report

logger = logging.getLogger("scout")


def _setup_logging(logs_dir: str, report_date: date) -> None:
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path(logs_dir) / f"{report_date.isoformat()}.log", encoding="utf-8"),
        ],
        force=True,
    )


def run(config_path="config.yaml", client=None, report_date=None) -> int:
    config = load_config(config_path)
    report_date = report_date or date.today()
    _setup_logging(config.logs_dir, report_date)
    client = client or anthropic.Anthropic()
    reports_dir = Path(config.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Start skanu: %d ról, limit wyszukiwań %d", len(config.roles), config.max_web_searches)
    result = run_scan(client, config)

    try:
        findings = extract_findings(result.text)
    except ParseError as e:
        logger.warning("Nieparsowalna odpowiedź (%s) — zapisuję raport awaryjny", e)
        raw_path = reports_dir / f"{report_date.isoformat()}-raw.md"
        raw_path.write_text(result.text, encoding="utf-8")
        logger.info("Raport awaryjny: %s", raw_path)
        return 0

    seen = load_seen(config.seen_file)
    new_findings = filter_new(findings, seen)
    duplicates = len(findings) - len(new_findings)

    report_path = reports_dir / f"{report_date.isoformat()}.md"
    report_path.write_text(
        render_report(new_findings, report_date, result.web_searches, duplicates),
        encoding="utf-8",
    )
    seen.update(finding_key(f) for f in new_findings)
    save_seen(config.seen_file, seen)
    logger.info("Raport: %s (%d nowych, %d duplikatów)", report_path, len(new_findings), duplicates)
    return 0


def main() -> int:
    try:
        return run()
    except anthropic.AuthenticationError:
        logger.error("Błąd uwierzytelnienia — ustaw ANTHROPIC_API_KEY (env / .env / GitHub Secret)")
        return 2
    except anthropic.RateLimitError:
        logger.error("Rate limit API — spróbuj później")
        return 3
    except anthropic.APIStatusError as e:
        logger.error("Błąd API %s: %s", e.status_code, e.message)
        return 4
    except anthropic.APIConnectionError:
        logger.error("Błąd połączenia z API Anthropic")
        return 5


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/pytest -v`
Expected: all tests pass (config 5, parsing 6, dedup 6, report 4, agent 4, main 3 = 28 passed)

- [ ] **Step 5: Commit**

```bash
git add scout/main.py tests/test_main.py
git commit -m "feat: orkiestracja przebiegu i CLI z kodami wyjścia

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Scheduling (GitHub Actions + launchd) i README

**Files:**
- Create: `.github/workflows/daily-scan.yml`, `scripts/run.sh`, `scripts/com.mski.hidden-job-scout.plist`, `README.md`

**Interfaces:**
- Consumes: `python -m scout.main` (Task 6), `config.yaml` (Task 1).
- Produces: nothing consumed by code — operational files only.

- [ ] **Step 1: Create the GitHub Actions workflow**

`.github/workflows/daily-scan.yml`:

```yaml
name: Daily job scan

on:
  schedule:
    - cron: "0 7 * * *"   # 07:00 UTC codziennie
  workflow_dispatch: {}    # ręczne uruchomienie z zakładki Actions

permissions:
  contents: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - name: Run scan
        run: python -m scout.main
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - name: Commit report
        run: |
          git config user.name "hidden-job-scout"
          git config user.email "actions@users.noreply.github.com"
          git add reports data/seen.json
          git diff --cached --quiet || git commit -m "Raport $(date -u +%F)"
          git push
```

- [ ] **Step 2: Create the local runner script**

`scripts/run.sh`:

```bash
#!/usr/bin/env bash
# Lokalny przebieg skanu + commit raportu (używany przez launchd).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

.venv/bin/python -m scout.main

git add reports data/seen.json
git diff --cached --quiet || git commit -m "Raport $(date +%F)"
```

Run: `chmod +x scripts/run.sh`

- [ ] **Step 3: Create the launchd plist**

`scripts/com.mski.hidden-job-scout.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mski.hidden-job-scout</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/mski/Developer/hidden-job-scout/scripts/run.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mski/Developer/hidden-job-scout/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mski/Developer/hidden-job-scout/logs/launchd.err.log</string>
</dict>
</plist>
```

- [ ] **Step 4: Validate the operational files**

Run:
```bash
cd /Users/mski/Developer/hidden-job-scout
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-scan.yml'))" && echo YAML_OK
bash -n scripts/run.sh && echo SH_OK
plutil -lint scripts/com.mski.hidden-job-scout.plist
```
Expected: `YAML_OK`, `SH_OK`, `scripts/com.mski.hidden-job-scout.plist: OK`

- [ ] **Step 5: Write README**

`README.md`:

````markdown
# Hidden Job Scout

Agent AI, który raz dziennie skanuje internet (Claude Opus 4.8 + serwerowe
wyszukiwanie web Anthropic) w poszukiwaniu **zdalnych ofert pracy z całego
świata** i sygnałów tzw. ukrytego rynku pracy dla ról QA/SDET/test — i zapisuje
raport Markdown do `reports/`.

## Jak to działa

1. Jedno wywołanie API: `claude-opus-4-8` z narzędziem `web_search_20260209`
   (limit wyszukiwań w `config.yaml`). Model szuka: postów hiring managerów na
   LinkedIn, stron karier firm, newsów o finansowaniu/ekspansji, postów
   rekruterów i klasycznych ogłoszeń z bezpośrednim linkiem.
2. Znaleziska (firma, projekt, rola, zarobki, link do aplikowania) wracają jako
   JSON, są odfiltrowywane z duplikatów (`data/seen.json`) i renderowane do
   `reports/RRRR-MM-DD.md`.

## Konfiguracja

- **Role**: edytuj listę `roles` w [config.yaml](config.yaml) — dowolna rola,
  bez zmian w kodzie.
- **Budżet**: `max_web_searches` (domyślnie 20 ≈ $0.5–1/dzień).
- **Klucz API**: zmienna `ANTHROPIC_API_KEY` (lokalnie plik `.env`, w GitHub
  Actions sekret repo).

## Uruchomienie ręczne

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
bash scripts/run.sh
```

## Harmonogram — wybierz jedno

**GitHub Actions** (zalecane — działa bez włączonego komputera):
1. Wypchnij repo na GitHub (prywatne).
2. Settings → Secrets and variables → Actions → dodaj `ANTHROPIC_API_KEY`.
3. Workflow `daily-scan.yml` odpala się codziennie 07:00 UTC i commituje raport.

**Lokalnie (launchd, macOS)** — Mac musi być włączony o 08:00:
```bash
cp scripts/com.mski.hidden-job-scout.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mski.hidden-job-scout.plist
```

## Testy

```bash
.venv/bin/pytest
```
(28 testów, bez wywołań prawdziwego API)
````

- [ ] **Step 6: Run the full test suite one more time**

Run: `.venv/bin/pytest`
Expected: 28 passed

- [ ] **Step 7: Commit**

```bash
git add .github scripts README.md
git commit -m "feat: harmonogram (GitHub Actions + launchd) i README

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Weryfikacja końcowa (po wszystkich zadaniach)

- [ ] `.venv/bin/pytest` → 28 passed
- [ ] Smoke test na żywym API (opcjonalny, ~$0.5–1, wymaga `ANTHROPIC_API_KEY`):
  `bash scripts/run.sh` → powstaje `reports/<dzisiejsza-data>.md` z prawdziwymi
  znaleziskami i commit w repo. Sprawdź, że linki w raporcie działają.
