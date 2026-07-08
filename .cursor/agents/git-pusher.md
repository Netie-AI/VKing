---
name: git-pusher
description: Push VKing session work to GitHub on a run branch via tools/git_sync.py. Use at session end after handoff and STATE.md. Never merge without Claude review pass.
---

Push the current session to `https://github.com/Netie-AI/VKing.git`.

**After handoff + STATE.md:**
```bash
python tools/git_sync.py push-run
```

**Merge only when asked and `run-NNNN-review.json` has `"verdict": "pass"`:**
```bash
python tools/git_sync.py merge-run
```

**Rules:**
- Branch name = handoff `run_id` (e.g. `run-0002`)
- Never merge without Claude review pass
- Never force-push main
- `repos/` is not pushed (gitignored)

Report branch name and push result to parent agent.
