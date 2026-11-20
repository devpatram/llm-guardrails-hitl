import json
from types import SimpleNamespace

import pytest

from hitl.providers import FakeProvider, GeminiProvider


def test_fake_expands_shorthand_but_not_tags():
    f = FakeProvider()
    assert f.suggest("lube brgs per wo WO4410") == "Lubricated bearings per work order WO4410."
    assert f.suggest("did not repl seal on PU-3") == "Did not replace seal on PU-3."
    assert f.verify("repl brg", "Replaced bearing.") == {"added": [], "dropped": []}


class FakeModels:
    def __init__(self, text):
        self.text, self.calls = text, []

    def generate_content(self, model, contents, config):
        self.calls.append((model, contents, config))
        return SimpleNamespace(text=self.text)


def test_gemini_provider_calls_with_temperature_zero_and_fences_the_note():
    pytest.importorskip("google.genai")
    models = FakeModels("Replaced the bearing on CV-3.")
    g = GeminiProvider(model="gemini-test", client=SimpleNamespace(models=models))
    assert g.suggest("repl brg CV-3") == "Replaced the bearing on CV-3."
    model, contents, config = models.calls[0]
    assert model == "gemini-test" and config.temperature == 0
    assert "<<<\nrepl brg CV-3\n>>>" in contents


def test_gemini_second_opinion_reads_json_and_fails_safe():
    pytest.importorskip("google.genai")
    good = GeminiProvider(model="m", client=SimpleNamespace(models=FakeModels(json.dumps({"added": ["failed"]}))))
    assert good.verify("a", "b") == {"added": ["failed"], "dropped": []}
    bad = GeminiProvider(model="m", client=SimpleNamespace(models=FakeModels("not json")))
    assert bad.verify("a", "b")["added"]  # unreadable is a reason to look, never a pass
