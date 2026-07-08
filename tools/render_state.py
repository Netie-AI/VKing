#!/usr/bin/env python3
"""Mechanically roll up the latest handoff JSON into STATE.md.

Reads the newest docs/handoffs/run-*.json (+ its -review.json if present).
Fills STATE.md by field lookup only — no summarization, no free text.
Exits nonzero if a required field is missing (fail closed).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFFS_DIR = ROOT / "docs" / "handoffs"
STATE_PATH = ROOT / "STATE.md"

GATES = ("G0", "G1", "G1.5", "G2", "G3", "G4")

REQUIRED_HANDOFF_FIELDS = ("run_id", "timestamp", "target", "self_provenance")


def _find_latest_handoff() -> Path:
    runs = sorted(
        HANDOFFS_DIR.glob("run-*.json"),
        key=lambda p: int(re.search(r"run-(\d+)\.json$", p.name).group(1)),  # type: ignore[union-attr]
    )
    runs = [p for p in runs if not p.name.endswith("-review.json")]
    if not runs:
        print("error: no docs/handoffs/run-*.json found", file=sys.stderr)
        sys.exit(1)
    return runs[-1]


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _gate_symbol(gate_results: dict, gate: str) -> str:
    if gate not in gate_results:
        return "—"
    value = gate_results[gate]
    if isinstance(value, dict):
        status = value.get("status") or value.get("result") or value.get("pass")
    else:
        status = value
    if status is None:
        return "—"
    normalized = str(status).strip().lower()
    if normalized in {"pass", "passed", "ok", "true", "success"}:
        return "✔"
    if normalized in {"fail", "failed", "error", "false", "vacuous"}:
        return "✘"
    return "—"


def _review_verdict(review: dict | None) -> str:
    if review is None:
        return "not yet reviewed"
    verdict = review.get("verdict")
    if verdict is None:
        print("error: review JSON missing required field 'verdict'", file=sys.stderr)
        sys.exit(1)
    return str(verdict)


def _require_fields(data: dict, fields: tuple[str, ...], label: str) -> None:
    missing = [f for f in fields if f not in data]
    if missing:
        print(f"error: {label} missing required fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def _open_questions(handoff: dict) -> list[str]:
    questions = handoff.get("open_questions_for_claude")
    if questions is None:
        print("error: handoff JSON missing required field 'open_questions_for_claude'", file=sys.stderr)
        sys.exit(1)
    if not isinstance(questions, list):
        print("error: open_questions_for_claude must be a list", file=sys.stderr)
        sys.exit(1)
    return [str(q) for q in questions]


def render() -> str:
    handoff_path = _find_latest_handoff()
    handoff = _load_json(handoff_path)
    _require_fields(handoff, REQUIRED_HANDOFF_FIELDS, handoff_path.name)

    run_id = handoff["run_id"]
    review_path = handoff_path.with_name(f"{run_id}-review.json")
    review = _load_json(review_path) if review_path.exists() else None

    gate_results = handoff.get("gate_results")
    if gate_results is None:
        print("error: handoff JSON missing required field 'gate_results'", file=sys.stderr)
        sys.exit(1)

    questions = _open_questions(handoff)
    plan_section = handoff.get("plan_section", "(not specified in handoff — read target)")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    review_suffix = f" + {run_id}-review" if review else ""

    gate_line = "  ".join(f"{g} <{_gate_symbol(gate_results, g)}>" for g in GATES)

    question_lines = "\n".join(f"- {q}" for q in questions) if questions else "- (none)"

    return f"""# VKing STATE (auto-generated — do not hand-edit; regenerate, don't patch)
Generated: {generated_at} from {run_id}{review_suffix}

## Now
- Target: {handoff['target']}
- Last self_provenance ceiling: {handoff['self_provenance']}
- Last review verdict: {_review_verdict(review)}

## Gate snapshot (most recent run only)
{gate_line}

## Open questions (carried from latest handoff)
{question_lines}

## Drill-down index (read only if the task needs it)
- Plan: vking-master-plan.md {plan_section}
- Latest handoff: docs/handoffs/{run_id}.json
- Latest review: docs/handoffs/{run_id}-review.json
- Repo knowledge: .cursor/skills/repo-knowledge/<name>/SKILL.md

## Rule
This file may only assert what the cited JSON already contains. Never
hand-edit. If it looks stale, regenerate from source, never patch it.
"""


def main() -> None:
    content = render()
    STATE_PATH.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {STATE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
