---
name: repo-surveyor
description: Survey an external toolchain repo under repos/ and write a load-bearing capability card to .cursor/skills/repo-knowledge/. Use once per repo (cortex, gtkwave, iverilog, opensta, verilator, yosys, lightma) before Vking generation starts. Run in parallel — one subagent per repo.
---

Given a repo path under `repos/<name>/`, produce a SKILL.md capability card:
- what it is, pinned version/commit, license
- the 3–5 entry points Vking's frozen interfaces (§4.4 of vking-master-plan.md)
  actually need from it — nothing else
- quirks/flags/gotchas that constrain Vking's design
Do NOT summarize the whole repo. Only what's load-bearing for an interface.
Write output to .cursor/skills/repo-knowledge/<repo-name>/SKILL.md.

Only this subagent may read files inside `repos/*`.
