"""Scores the guardrails on labeled cases and writes eval/report.md.

Each case is an original note, a suggestion and whether the suggestion should reach a reviewer ("pass") or be stopped
("block"). The hard checks run first; on what they pass, the provider's second opinion runs.

  python eval/run_eval.py                    offline second opinion (the fake provider)
  python eval/run_eval.py --provider gemini  Gemini as the second opinion (needs Google Cloud or an API key)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hitl.providers import get_provider  # noqa: E402
from hitl.rules import check  # noqa: E402


def outcome(case: dict, provider) -> tuple[str, str]:
    found = check(case["original"], case["suggestion"])
    if found:
        return "blocked", "; ".join(f"{f.check}: {f.detail}" for f in found)
    opinion = provider.verify(case["original"], case["suggestion"])
    if opinion.get("added") or opinion.get("dropped"):
        return "flagged", f"added {opinion.get('added')}, dropped {opinion.get('dropped')}"
    return "passed", ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="fake", choices=["fake", "gemini"])
    ap.add_argument("--out", default=ROOT / "eval" / "report.md", type=Path)
    args = ap.parse_args(argv)
    provider = get_provider(args.provider)
    cases = [json.loads(line) for line in open(ROOT / "eval" / "cases.jsonl", encoding="utf-8")]
    results = [(c, *outcome(c, provider)) for c in cases]

    bad = [r for r in results if r[0]["expect"] == "block"]
    good = [r for r in results if r[0]["expect"] == "pass"]
    by_rules = sum(r[1] == "blocked" for r in bad)
    by_second = sum(r[1] == "flagged" for r in bad)
    slipped = [r for r in bad if r[1] == "passed"]
    good_counts = Counter(r[1] for r in good)

    per_cat: dict[str, Counter] = defaultdict(Counter)
    for c, result, _ in results:
        per_cat[c["category"]][result] += 1

    lines = [
        "# Guardrail evaluation", "",
        f"{len(cases)} labeled cases: {len(good)} good rewrites that should reach the reviewer and {len(bad)} bad ones "
        f"that should not. Second opinion: `{provider.name}`.", "",
        "## Bad suggestions", "",
        "| Stopped by | Cases | Share |", "| --- | --- | --- |",
        f"| Hard checks (blocked, withheld from the reviewer) | {by_rules} | {by_rules / len(bad):.0%} |",
        f"| Second opinion (shown to the reviewer with a warning) | {by_second} | {by_second / len(bad):.0%} |",
        f"| Neither (reached the reviewer looking clean) | {len(slipped)} | {len(slipped) / len(bad):.0%} |", "",
        "## Good suggestions", "",
        "| Outcome | Cases |", "| --- | --- |",
        f"| Passed clean | {good_counts['passed']} |",
        f"| Flagged by the second opinion (a false alarm the reviewer clears) | {good_counts['flagged']} |",
        f"| Blocked by the hard checks (a false block) | {good_counts['blocked']} |", "",
        "## By category", "",
        "| Category | Expect | Blocked | Flagged | Passed |", "| --- | --- | --- | --- | --- |",
    ]
    for cat, counts in per_cat.items():
        expect = next(c["expect"] for c, _, _ in results if c["category"] == cat)
        lines.append(f"| {cat} | {expect} | {counts['blocked']} | {counts['flagged']} | {counts['passed']} |")
    lines += ["", "## Every case", "", "| Case | Category | Result | Why |", "| --- | --- | --- | --- |"]
    for c, result, why in results:
        lines.append(f"| {c['id']} | {c['category']} | {result} | {why.replace('|', '/')} |")
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:22]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
