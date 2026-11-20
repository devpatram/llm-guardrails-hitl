"""Deterministic output checks: the hard guardrails.

Each check compares the original note with the model's suggestion and returns a Finding when something is wrong.
They are plain Python on purpose: fast, free, testable, and the same answer every time. A suggestion that fails any of
them is withheld from the reviewer (status "blocked").
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .redact import PLACEHOLDER

# Asset tags and part or order numbers: capital letters, an optional dash, then digits (CV-3, P101, WO4105, M3).
ID = re.compile(r"\b[A-Z]{1,4}-?\d{1,6}[A-Z]?\b")
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,/]\d+)*")
NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}
NUMBER_WORD = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.I)

# Stronger claims than a technician's note can support. Allowed only if the original already says them.
ASSURANCES = ("guarantee", "permanent", "fully resolved", "no further issues", "no issues", "all clear",
              "root cause", "safe to operate", "safe to run", "100%", "will not fail", "fixed for good", "resolved")
# Signs the model talked to us instead of returning the note.
CHATTER = ("as an ai", "i cannot", "i can't", "here is", "here's", "rewritten note", "suggestion:", "sure,")

MIN_RATIO, MAX_RATIO = 0.6, 2.5
SHORT_NOTE = 8  # words; a shorter note ("chk guard ok") may shrink, so only the upper bound applies


@dataclass(frozen=True)
class Finding:
    check: str
    detail: str


def ids(text: str) -> set[str]:
    return {m.group(0).replace("-", "") for m in ID.finditer(text)}


def numbers(text: str) -> list[str]:
    """Numbers outside asset tags, normalized: '3.0' -> '3', '1,200' -> '1200', 'two' -> '2'."""
    text = PLACEHOLDER.sub(" ", ID.sub(" ", text))
    text = NUMBER_WORD.sub(lambda m: NUMBER_WORDS[m.group(0).lower()], text)
    out = []
    for raw in NUMBER.findall(text):
        value = raw.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", raw) else raw
        if re.fullmatch(r"\d+\.\d+", value):
            value = value.rstrip("0").rstrip(".")
        out.append(value)
    return sorted(out)


def _diff(name: str, before: list[str] | set[str], after: list[str] | set[str]) -> list[Finding]:
    before, after = list(before), list(after)
    added = [x for x in after if after.count(x) > before.count(x)]
    dropped = [x for x in before if before.count(x) > after.count(x)]
    found = []
    if added:
        found.append(Finding(name, "added " + ", ".join(sorted(set(added)))))
    if dropped:
        found.append(Finding(name, "dropped " + ", ".join(sorted(set(dropped)))))
    return found


def check(original: str, suggestion: str) -> list[Finding]:
    """All hard checks. An empty list means the suggestion may be shown to the reviewer."""
    if not suggestion.strip():
        return [Finding("empty", "the model returned nothing")]
    found: list[Finding] = []
    found += _diff("numbers", numbers(original), numbers(suggestion))
    found += _diff("ids", ids(original), ids(suggestion))
    found += _diff("placeholders", PLACEHOLDER.findall(original), PLACEHOLDER.findall(suggestion))

    lo, so = original.lower(), suggestion.lower()
    new_claims = [a for a in ASSURANCES if a in so and a not in lo]
    if new_claims:
        found.append(Finding("assurance", "adds " + ", ".join(f"'{a}'" for a in new_claims)))
    chatter = [c for c in CHATTER if c in so and c not in lo]
    if chatter:
        found.append(Finding("format", "talks to the reader: " + ", ".join(f"'{c}'" for c in chatter)))

    words = len(original.split())
    ratio = len(suggestion.split()) / max(words, 5)
    if ratio > MAX_RATIO or (words >= SHORT_NOTE and ratio < MIN_RATIO):
        found.append(Finding("length", f"{ratio:.1f}x the original's words (allowed {MIN_RATIO} to {MAX_RATIO})"))
    return found
