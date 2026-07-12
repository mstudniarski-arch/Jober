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
