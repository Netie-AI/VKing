---
name: state-updater
description: Regenerate STATE.md from the latest handoff JSON by running tools/render_state.py. Use after writing a handoff or when STATE.md looks stale. Never hand-edit STATE.md.
---

Your only job is to regenerate STATE.md deterministically.

**Process:**
1. Run `python tools/render_state.py` from the repo root.
2. If exit code is nonzero, report the error — do not hand-write STATE.md.
3. Confirm the file was written.

**Rules:**
- Never edit STATE.md yourself.
- Never summarize or add free prose.
- STATE.md may only assert what the cited handoff JSON already contains.
