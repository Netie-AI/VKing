---
name: vking-state
description: Regenerate STATE.md from the latest handoff JSON via tools/render_state.py. Never hand-edit STATE.md.
---

STATE.md is a mechanical rollup of the latest `docs/handoffs/run-*.json` — never hand-edit it.

**To refresh:**
```bash
python tools/render_state.py
```

The script reads the newest handoff (+ its `-review.json` if present), fills the template by field lookup only, and overwrites `STATE.md`. It exits nonzero if required fields are missing (fail closed).

**Rules:**
- Do not write or patch STATE.md directly.
- Do not summarize or add free prose to STATE.md.
- If STATE.md looks stale, run `render_state.py` — do not patch.

Invoke via the `state-updater` subagent or directly at session end after writing the handoff JSON.
