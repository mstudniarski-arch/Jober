from scout.agent import build_prompt, run_scan
from scout.config import ScoutConfig
from tests.fakes import FakeClient, fake_completion

CONFIG = ScoutConfig(roles=["AI SDET", "QA engineer"])
RESULTS = [{"title": "Acme hiring SDET", "url": "https://acme.com/jobs/1", "body": "Remote SDET role"}]


def test_build_prompt_contains_roles_results_and_format():
    prompt = build_prompt(CONFIG, results=RESULTS)
    assert "- AI SDET" in prompt
    assert "- QA engineer" in prompt
    assert "https://acme.com/jobs/1" in prompt
    assert "Acme hiring SDET" in prompt
    assert '"findings"' in prompt
    assert "VERBATIM" in prompt
    assert "US only" in prompt
    assert "SENIORITY" not in prompt


def test_junior_only_prompt_adds_seniority_filter():
    prompt = build_prompt(CONFIG, roles=["Junior AI Engineer"], junior_only=True)
    assert "- Junior AI Engineer" in prompt
    assert "- AI SDET" not in prompt
    assert "SENIORITY" in prompt
    assert '"Senior"' in prompt


def test_run_scan_searches_and_extracts():
    client = FakeClient([fake_completion("extracted")])
    searched = []
    def fn(query, max_results):
        searched.append(query)
        return [{"title": "T", "href": "https://t.io/1", "body": "b"}]
    result = run_scan(client, CONFIG, search_fn=fn)
    assert result.text == "extracted"
    assert result.web_searches == 2  # po jednym zapytaniu na rolę
    assert len(searched) == 2
    call = client.calls[0]
    assert call["model"] == "llama-3.3-70b-versatile"
    assert call["max_tokens"] == 4096
    assert "https://t.io/1" in call["messages"][0]["content"]


def test_empty_results_render_placeholder():
    prompt = build_prompt(CONFIG, results=[])
    assert "(no results)" in prompt
