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
