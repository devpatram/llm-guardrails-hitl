import json
import subprocess
import sys
from pathlib import Path

from hitl.__main__ import review
from hitl.providers import FakeProvider

ROOT = Path(__file__).resolve().parents[1]


def test_review_loop_records_each_decision(tmp_path):
    notes = [{"id": "N1", "text": "repl brg on CV-3"}, {"id": "N2", "text": "hyd lk at P-101"}]
    answers = iter(["a", "e", "Hydraulic leak found at P-101."])
    out = []
    audit = tmp_path / "audit.jsonl"
    records = review(notes, FakeProvider(), "J. Doe", audit, ask=lambda _: next(answers), out=out.append)
    assert [r["decision"] for r in records] == ["accept", "edit"]
    assert len(audit.read_text().splitlines()) == 2
    assert any("READY" in line for line in out)


def test_eval_report_runs_and_no_good_rewrite_is_blocked(tmp_path):
    report = tmp_path / "report.md"
    subprocess.run([sys.executable, str(ROOT / "eval" / "run_eval.py"), "--out", str(report)], check=True,
                   capture_output=True)
    text = report.read_text()
    assert "| Blocked by the hard checks (a false block) | 0 |" in text
    for category in ("added_number", "dropped_number", "changed_number", "asset_tag", "placeholder", "assurance"):
        line = next(l for l in text.splitlines() if l.startswith(f"| {category} |"))
        assert line.split("|")[4].strip() == "0" and line.split("|")[5].strip() == "0", line  # all blocked
