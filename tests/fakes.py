"""Fałszywy klient Gemini do testów — bez sieci."""
from types import SimpleNamespace


def fake_response(text, queries=()):
    metadata = SimpleNamespace(web_search_queries=list(queries))
    candidate = SimpleNamespace(grounding_metadata=metadata)
    return SimpleNamespace(text=text, candidates=[candidate])


class _FakeModels:
    def __init__(self, queue):
        self._queue = list(queue)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self._queue.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.models = _FakeModels(responses)
