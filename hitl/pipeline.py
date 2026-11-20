"""Suggest, check, then a person decides. Nothing reaches the record without a human decision.

  status "ready"            the hard checks passed and the second opinion found nothing
  status "needs_attention"  the hard checks passed but the second opinion lists added or dropped facts
  status "blocked"          a hard check failed (or the model call failed): the suggestion is withheld
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .redact import redact, restore
from .rules import Finding, check

MAX_NOTE_CHARS = 4000
DECISIONS = ("accept", "edit", "reject")


@dataclass
class Suggestion:
    note_id: str
    original: str
    provider: str
    status: str
    suggestion: str | None = None  # what the reviewer sees; None when blocked
    findings: list[Finding] = field(default_factory=list)
    second_opinion: dict = field(default_factory=dict)
    redacted: list[str] = field(default_factory=list)  # placeholder names only, never the values

    def to_dict(self) -> dict:
        return asdict(self)


def suggest(note: str, provider, note_id: str = "") -> Suggestion:
    """Runs one note through the input guard, the model, the hard checks and the second opinion."""
    base = dict(note_id=note_id, original=note, provider=provider.name)
    if not note.strip():
        return Suggestion(**base, status="blocked", findings=[Finding("input", "the note is empty")])
    if len(note) > MAX_NOTE_CHARS:
        return Suggestion(**base, status="blocked",
                          findings=[Finding("input", f"the note is over {MAX_NOTE_CHARS} characters")])

    sent, found = redact(note)  # contact details never reach the model
    try:
        raw = provider.suggest(sent)
    except Exception as e:  # fail closed: no suggestion, the original stands
        return Suggestion(**base, status="blocked", findings=[Finding("provider", f"model call failed: {e}")],
                          redacted=list(found))

    findings = check(sent, raw)
    if findings:
        return Suggestion(**base, status="blocked", findings=findings, redacted=list(found))
    try:
        opinion = provider.verify(sent, raw)
    except Exception as e:
        opinion = {"added": [f"(second check failed: {e})"], "dropped": []}
    status = "needs_attention" if opinion.get("added") or opinion.get("dropped") else "ready"
    return Suggestion(**base, status=status, suggestion=restore(raw, found), second_opinion=opinion,
                      redacted=list(found))


def decide(s: Suggestion, decision: str, reviewer: str, edited: str | None = None) -> dict:
    """Records what the person chose. The final text is always one a person approved."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    if decision == "accept" and s.suggestion is None:
        raise ValueError("a blocked suggestion cannot be accepted; edit or reject")
    if decision == "edit" and not (edited and edited.strip()):
        raise ValueError("an edit needs the edited text")
    final = {"accept": s.suggestion, "edit": edited, "reject": s.original}[decision]
    # A person may override the checks, but the record shows it.
    overrides = [asdict(f) for f in check(s.original, final)] if decision == "edit" else []
    return {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note_id": s.note_id,
        "provider": s.provider,
        "status": s.status,
        "findings": [asdict(f) for f in s.findings],
        "second_opinion": s.second_opinion,
        "decision": decision,
        "reviewer": reviewer,
        "final_text": final,
        "final_sha256": hashlib.sha256(final.encode()).hexdigest(),
        "edit_findings": overrides,
    }


def append_audit(record: dict, path: str | Path) -> None:
    """One JSON line per decision, appended, never rewritten."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
