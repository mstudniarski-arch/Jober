"""Fałszywe obiekty do testów — bez sieci."""
from types import SimpleNamespace


def fake_completion(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class _FakeCompletions:
    def __init__(self, queue):
        self._queue = list(queue)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))

    @property
    def calls(self):
        return self.chat.completions.calls


def no_search(query, max_results):
    return []
