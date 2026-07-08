#!/usr/bin/env python3
"""Git sync for VKing: push run branches, merge after Claude review pass.

Subcommands:
  push-run    Create/push branch named after latest handoff run_id
  merge-run   Merge approved run branch into main (requires -review.json verdict pass)

Remote: https://github.com/Netie-AI/VKing.git
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFFS_DIR = ROOT / "docs" / "handoffs"
REMOTE = "https://github.com/Netie-AI/VKing.git"
MAIN_BRANCH = "main"


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def _run_out(cmd: list[str]) -> str:
    result = _run(cmd)
    return (result.stdout or "").strip()


def _ensure_git_repo() -> None:
    if not (ROOT / ".git").exists():
        _run(["git", "init", "-b", MAIN_BRANCH])
        _run(["git", "remote", "add", "origin", REMOTE])


def _ensure_remote() -> None:
    try:
        url = _run_out(["git", "remote", "get-url", "origin"])
    except subprocess.CalledProcessError:
        _run(["git", "remote", "add", "origin", REMOTE])
        return
    if url != REMOTE:
        _run(["git", "remote", "set-url", "origin", REMOTE])


def _latest_handoff() -> tuple[Path, dict]:
    runs = sorted(
        HANDOFFS_DIR.glob("run-*.json"),
        key=lambda p: int(re.search(r"run-(\d+)\.json$", p.name).group(1)),  # type: ignore[union-attr]
    )
    runs = [p for p in runs if not p.name.endswith("-review.json")]
    if not runs:
        print("error: no handoff JSON found", file=sys.stderr)
        sys.exit(1)
    path = runs[-1]
    with path.open(encoding="utf-8") as f:
        return path, json.load(f)


def _review_for(run_id: str) -> dict | None:
    path = HANDOFFS_DIR / f"{run_id}-review.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _has_changes() -> bool:
    status = _run_out(["git", "status", "--porcelain"])
    return bool(status)


def push_run() -> None:
    _ensure_git_repo()
    _ensure_remote()

    _, handoff = _latest_handoff()
    run_id = handoff["run_id"]
    target = handoff.get("target", run_id)
    branch = run_id

    current = _run_out(["git", "branch", "--show-current"])
    if current != branch:
        # Create or switch to run branch from main if new
        branches = _run_out(["git", "branch", "--list", branch])
        if branches:
            _run(["git", "checkout", branch])
        else:
            try:
                _run_out(["git", "rev-parse", MAIN_BRANCH])
                base = MAIN_BRANCH
            except subprocess.CalledProcessError:
                base = None
            if base:
                _run(["git", "checkout", "-b", branch, base])
            else:
                _run(["git", "checkout", "-b", branch])

    if _has_changes():
        _run(["git", "add", "-A"])
        _run(["git", "commit", "-m", f"{run_id}: {target}"])
    else:
        print(f"no changes to commit on {branch}")

    _run(["git", "push", "-u", "origin", branch])
    print(f"pushed {branch} -> origin ({REMOTE})")


def _branch_exists(branch: str) -> bool:
    local = _run_out(["git", "branch", "--list", branch])
    if local:
        return True
    remote = _run_out(["git", "branch", "-r", "--list", f"origin/{branch}"])
    return bool(remote)


def _checkout_main() -> None:
    if _run(["git", "checkout", MAIN_BRANCH], check=False).returncode == 0:
        return
    remote_main = _run(["git", "ls-remote", "--heads", "origin", MAIN_BRANCH], check=False)
    if remote_main.returncode == 0 and (remote_main.stdout or "").strip():
        _run(["git", "fetch", "origin", MAIN_BRANCH])
        _run(["git", "checkout", "-b", MAIN_BRANCH, f"origin/{MAIN_BRANCH}"])
        return
    print(f"note: {MAIN_BRANCH} does not exist yet — will be created on first merge")


def _promote_branch_to_main(branch: str) -> None:
    """First merge: push run branch directly to main (no orphan checkout)."""
    _run(["git", "push", "origin", f"{branch}:refs/heads/{MAIN_BRANCH}"])
    _run(["git", "fetch", "origin", MAIN_BRANCH])
    _run(["git", "checkout", "-b", MAIN_BRANCH, f"origin/{MAIN_BRANCH}"])
    print(f"promoted {branch} -> origin/{MAIN_BRANCH}")


def merge_run(run_id: str | None = None) -> None:
    _ensure_git_repo()
    _ensure_remote()

    if run_id is None:
        _, handoff = _latest_handoff()
        run_id = handoff["run_id"]

    review = _review_for(run_id)
    if review is None:
        print(f"error: {run_id}-review.json not found — Claude review required", file=sys.stderr)
        sys.exit(1)

    verdict = review.get("verdict")
    if verdict != "pass":
        print(f"error: review verdict is '{verdict}', not 'pass' — merge blocked", file=sys.stderr)
        sys.exit(1)

    branch = run_id
    if not _branch_exists(branch):
        print(
            f"note: no git branch '{branch}' — review recorded (verdict: pass), "
            f"nothing to merge (work may live on a later run branch)"
        )
        return

    _run(["git", "fetch", "origin"])
    on_main = _run(["git", "ls-remote", "--heads", "origin", MAIN_BRANCH], check=False)
    main_exists = on_main.returncode == 0 and (on_main.stdout or "").strip()

    if not main_exists:
        _promote_branch_to_main(branch)
        return

    _checkout_main()
    pull = _run(["git", "pull", "origin", MAIN_BRANCH], check=False)
    if pull.returncode != 0:
        print(f"warning: could not pull {MAIN_BRANCH}", file=sys.stderr)
    _run(["git", "merge", branch, "--no-ff", "-m", f"Merge {branch} (Claude review: pass)"])
    _run(["git", "push", "origin", MAIN_BRANCH])
    print(f"merged {branch} -> {MAIN_BRANCH} and pushed")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: git_sync.py {push-run|merge-run} [run_id]", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "push-run":
        push_run()
    elif cmd == "merge-run":
        merge_run(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print(f"error: unknown command '{cmd}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
