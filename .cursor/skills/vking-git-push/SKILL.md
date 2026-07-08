---
name: vking-git-push
description: Push VKing work to https://github.com/jian-hong/Vking.git on a run branch; auto-merge to main only after Claude review verdict pass. Use at session end after handoff and STATE.md, or when user asks to push/sync GitHub.
---

# VKing Git Push

Remote: `https://github.com/jian-hong/Vking.git` (jian-hong account).

`repos/` is gitignored — only Vking orchestration artifacts are pushed.

## End-of-session push (every run)

After `vking-handoff` + `render_state.py`:

```bash
python tools/git_sync.py push-run
```

This:
1. Reads the latest `docs/handoffs/run-NNNN.json`
2. Creates/checks out branch `run-NNNN`
3. Commits all tracked changes (if any)
4. Pushes to `origin` with `-u`

No PR, no manual verification — direct push to your branch on GitHub.

## Auto-merge (only after Claude approves)

Claude must write `docs/handoffs/run-NNNN-review.json` with:

```json
{ "verdict": "pass", ... }
```

Then merge — **never merge without this file and verdict `pass`**:

```bash
python tools/git_sync.py merge-run
# or explicit: python tools/git_sync.py merge-run run-0002
```

This merges `run-NNNN` → `main` and pushes. Blocked if verdict is missing or not `pass`.

## Rules

- Cursor pushes branches; Cursor does **not** merge without Claude `pass`.
- Never force-push `main`.
- Never commit `repos/` (vendored toolchains stay local).
- First run may need `git` credentials configured for `github.com` (HTTPS or SSH).

## Review JSON shape (Claude writes)

```json
{
  "run_id": "run-0002",
  "verdict": "pass",
  "reviewer": "claude",
  "timestamp": "...",
  "notes": ["..."]
}
```

Verdict values: `pass` | `changes-requested`
