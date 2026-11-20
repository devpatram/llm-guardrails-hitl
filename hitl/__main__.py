"""Command line: suggest one note, or review a file of notes one at a time.

  python -m hitl suggest "repl brg on cnvyr 3, still noisy, chk tmrw"
  python -m hitl review data/notes.jsonl --reviewer "J. Doe" --audit audit.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys

from .pipeline import append_audit, decide, suggest
from .providers import get_provider

LABEL = {"ready": "READY", "needs_attention": "CHECK THIS", "blocked": "BLOCKED"}


def show(s, out=print) -> None:
    out(f"\n--- note {s.note_id} [{LABEL[s.status]}]")
    out(f"Original:   {s.original}")
    if s.suggestion is not None:
        out(f"Suggestion: {s.suggestion}")
    if s.redacted:
        out(f"  hidden from the model: {', '.join(s.redacted)}")
    for f in s.findings:
        out(f"  blocked by {f.check}: {f.detail}")
    for kind in ("added", "dropped"):
        if s.second_opinion.get(kind):
            out(f"  second check, {kind}: {', '.join(map(str, s.second_opinion[kind]))}")


def review(notes, provider, reviewer: str, audit: str, ask=input, out=print) -> list[dict]:
    records = []
    for note in notes:
        s = suggest(note["text"], provider, note_id=str(note["id"]))
        show(s, out)
        choices = "[a]ccept / [e]dit / [r]eject / [q]uit" if s.suggestion is not None else "[e]dit / [r]eject / [q]uit"
        while True:
            answer = ask(f"{choices}: ").strip().lower()[:1]
            if answer == "q":
                return records
            if answer == "a" and s.suggestion is not None:
                record = decide(s, "accept", reviewer)
            elif answer == "e":
                record = decide(s, "edit", reviewer, edited=ask("Your text: "))
                for f in record["edit_findings"]:
                    out(f"  note: your edit {f['detail']} ({f['check']}); recorded as an override")
            elif answer == "r":
                record = decide(s, "reject", reviewer)
            else:
                continue
            append_audit(record, audit)
            records.append(record)
            break
    return records


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="fake", choices=["fake", "gemini"])
    sub = ap.add_subparsers(dest="command", required=True)
    one = sub.add_parser("suggest", help="suggest one note and print the result as JSON")
    one.add_argument("text")
    many = sub.add_parser("review", help="review a JSONL file of notes ({\"id\": ..., \"text\": ...} per line)")
    many.add_argument("notes")
    many.add_argument("--reviewer", required=True)
    many.add_argument("--audit", default="audit.jsonl")
    args = ap.parse_args(argv)
    provider = get_provider(args.provider)
    if args.command == "suggest":
        print(json.dumps(suggest(args.text, provider).to_dict(), indent=2))
        return 0
    with open(args.notes, encoding="utf-8") as f:
        notes = [json.loads(line) for line in f if line.strip()]
    records = review(notes, provider, args.reviewer, args.audit)
    print(f"\n{len(records)} decision(s) appended to {args.audit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
