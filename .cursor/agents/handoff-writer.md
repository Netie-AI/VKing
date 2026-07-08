---
name: handoff-writer
description: Write an immutable session handoff JSON for Claude review. Use at the end of every Cursor run before stopping. Never edit prior run-NNNN.json files.
---

At session end, invoke the vking-handoff skill and write `docs/handoffs/run-NNNN.json`.

**Process:**
1. Read existing `docs/handoffs/run-*.json` to determine the next run number (max + 1, zero-padded to four digits).
2. Collect: run_id, timestamp, target stage/version worked toward (§13 or §14), interfaces touched (§4.4), files changed, gate results (only if actually run), self_provenance (ceiling L2), deviations from plan, open questions for Claude.
3. Write the new file. Never modify a previous `run-NNNN.json`.
4. Run `python tools/render_state.py` to refresh STATE.md (or delegate to state-updater).
5. Confirm the handoff file path and STATE.md regeneration.

**Provenance rules (§8):**
- `self_provenance` max: `L2_sim_active` — only if gates were mechanically run.
- Default: `L1_compiled` if code was written but gates not run.
- Never assign L3+ or write "reviewed" / "verified".

Claude writes `run-NNNN-review.json` in the same directory; you do not.
