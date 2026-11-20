"""Input guard: personal contact details are replaced with placeholders before any text reaches a model.

The placeholders ([EMAIL_1], [PHONE_1]) go to the model, the model must keep them, and they are put back afterwards.
"""
from __future__ import annotations

import re

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)")
PLACEHOLDER = re.compile(r"\[(?:EMAIL|PHONE)_\d+\]")


def redact(text: str) -> tuple[str, dict[str, str]]:
    """Returns the text with emails and phone numbers replaced, and the map to put them back."""
    found: dict[str, str] = {}

    def swap(kind: str):
        def inner(m: re.Match) -> str:
            for key, value in found.items():  # the same value twice gets the same placeholder
                if value == m.group(0):
                    return key
            key = f"[{kind}_{sum(k.startswith(f'[{kind}') for k in found) + 1}]"
            found[key] = m.group(0)
            return key
        return inner

    text = EMAIL.sub(swap("EMAIL"), text)
    text = PHONE.sub(swap("PHONE"), text)
    return text, found


def restore(text: str, found: dict[str, str]) -> str:
    for key, value in found.items():
        text = text.replace(key, value)
    return text
