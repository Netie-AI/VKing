---
name: vking-handoff
description: Write an immutable session handoff JSON at end of every Cursor run for Claude review. Invoke before stopping any Vking work session.
---

At end of session, write docs/handoffs/run-NNNN.json:
{
  "run_id": "...", "timestamp": "...",
  "target": "<stage/version from §13 or §14 table you were working toward>",
  "plan_section": "<e.g. §6.1 — optional but helps STATE.md drill-down>",
  "interfaces_touched": [...],
  "files_changed": [...],
  "gate_results": {...},                 // only if you actually ran them
  "self_provenance": "L1_compiled",       // ceiling: L2. Never higher.
  "deviations_from_plan": ["... + why"],
  "open_questions_for_claude": [...]
}
Never edit a previous run-NNNN.json. Each run is immutable, same rule as the
plan's own run manifest in §7.

Then run `python tools/render_state.py` (or invoke state-updater) to refresh
STATE.md — never hand-edit STATE.md.

Then run `python tools/git_sync.py push-run` (or invoke vking-git-push /
git-pusher) to push branch `<run_id>` to origin. Never merge to main unless
`docs/handoffs/<run_id>-review.json` exists with `"verdict": "pass"`.
