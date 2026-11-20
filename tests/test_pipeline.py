import json

import pytest

from hitl.pipeline import append_audit, decide, suggest
from hitl.providers import FakeProvider


class Scripted:
    """A provider that returns what the test tells it to."""

    name = "scripted"

    def __init__(self, reply="", opinion=None, error=None):
        self.reply, self.opinion, self.error, self.seen = reply, opinion or {"added": [], "dropped": []}, error, []

    def suggest(self, note):
        self.seen.append(note)
        if self.error:
            raise self.error
        return self.reply

    def verify(self, original, suggestion):
        return self.opinion


def test_ready_when_checks_and_second_opinion_pass():
    s = suggest("repl brg on CV-3", FakeProvider(), "N1")
    assert s.status == "ready" and s.suggestion == "Replaced bearing on CV-3."


def test_blocked_suggestions_are_withheld():
    s = suggest("repl brg on CV-3", Scripted("Replaced 2 bearings on CV-3."))
    assert s.status == "blocked" and s.suggestion is None
    assert s.findings[0].check == "numbers"


def test_second_opinion_marks_needs_attention():
    s = suggest("brg on F-2 suspect", Scripted("The bearing on F-2 failed.", {"added": ["failed"], "dropped": []}))
    assert s.status == "needs_attention" and s.suggestion == "The bearing on F-2 failed."


def test_contact_details_never_reach_the_model_but_come_back():
    provider = Scripted("Call [PHONE_1] about parts.")
    s = suggest("call 555-201-4477 about parts", provider)
    assert provider.seen == ["call [PHONE_1] about parts"]
    assert s.suggestion == "Call 555-201-4477 about parts." and s.redacted == ["[PHONE_1]"]


def test_a_failed_model_call_fails_closed():
    s = suggest("repl brg CV-3", Scripted(error=TimeoutError("deadline exceeded")))
    assert s.status == "blocked" and s.findings[0].check == "provider"


def test_input_guard():
    assert suggest("   ", FakeProvider()).status == "blocked"
    assert suggest("x" * 5000, FakeProvider()).findings[0].check == "input"


def test_a_person_decides_and_overrides_are_recorded(tmp_path):
    s = suggest("repl brg on CV-3", FakeProvider(), "N1")
    accepted = decide(s, "accept", "J. Doe")
    assert accepted["final_text"] == "Replaced bearing on CV-3." and accepted["reviewer"] == "J. Doe"
    edited = decide(s, "edit", "J. Doe", edited="Replaced 2 bearings on CV-3.")
    assert edited["edit_findings"] == [{"check": "numbers", "detail": "added 2"}]
    assert decide(s, "reject", "J. Doe")["final_text"] == "repl brg on CV-3"
    audit = tmp_path / "audit.jsonl"
    append_audit(accepted, audit)
    append_audit(edited, audit)
    assert [json.loads(line)["decision"] for line in audit.read_text().splitlines()] == ["accept", "edit"]


def test_a_blocked_suggestion_cannot_be_accepted():
    s = suggest("repl brg on CV-3", Scripted("Replaced 2 bearings on CV-3."))
    with pytest.raises(ValueError):
        decide(s, "accept", "J. Doe")
    with pytest.raises(ValueError):
        decide(s, "edit", "J. Doe", edited=" ")
