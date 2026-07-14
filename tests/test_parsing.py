import pytest

from scout.parsing import Finding, ParseError, extract_findings

VALID = """Here is my research summary.

```json
{"findings": [
  {"company": "Acme", "role": "Senior SDET", "apply_url": "https://acme.com/jobs/1",
   "project": "payments platform", "salary": "$120k-150k",
   "signal_type": "career_page", "source_url": "https://acme.com/careers",
   "location": "Remote (worldwide)", "published_at": "2026-07-14T06:00:00Z"},
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
        published_at="2026-07-14T06:00:00Z",
    )
    assert findings[1].published_at is None
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
