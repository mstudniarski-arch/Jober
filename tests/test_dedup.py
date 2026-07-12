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
