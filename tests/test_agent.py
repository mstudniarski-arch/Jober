from types import SimpleNamespace

from scout.agent import build_prompt, run_scan
from scout.config import ScoutConfig
from tests.fakes import FakeClient, fake_response

CONFIG = ScoutConfig(roles=["AI SDET", "QA engineer"])


def test_build_prompt_contains_roles_scope_and_format():
    prompt = build_prompt(CONFIG)
    assert "- AI SDET" in prompt
    assert "- QA engineer" in prompt
    assert "remote" in prompt.lower()
    assert '"findings"' in prompt
    assert "30" in prompt  # recency_days


def test_run_scan_returns_text_and_search_count():
    client = FakeClient([fake_response("final answer", queries=["q1", "q2"])])
    result = run_scan(client, CONFIG)
    assert result.text == "final answer"
    assert result.web_searches == 2
    call = client.models.calls[0]
    assert call["model"] == "gemini-3.5-flash"
    assert call["config"].tools[0].google_search is not None
    assert call["config"].max_output_tokens == 32000
    assert '"findings"' in call["contents"]


def test_run_scan_handles_missing_grounding_metadata():
    response = SimpleNamespace(text="ok", candidates=[SimpleNamespace(grounding_metadata=None)])
    result = run_scan(FakeClient([response]), CONFIG)
    assert result.text == "ok"
    assert result.web_searches == 0
