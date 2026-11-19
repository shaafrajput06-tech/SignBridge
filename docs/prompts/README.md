# How to run the SignBridge v2 prompts

Source: "SignBridge v2 — Master Prompt Architecture" (17 Nov 2026).

| Layer | File | Loaded |
|---|---|---|
| 1 · Constitution | `CLAUDE.md` | every session |
| 2 · Context pack | `docs/CONTEXT.md` (regenerated at the end of each phase) | every session |
| 3 · Phase prompt | `docs/prompts/phase-N.md` | start of that phase |
| 4 · Gate prompts | `docs/prompts/gate.md` (Gate A self-check, Gate B independent reviewer) | end of each phase |
| 5 · Handoff | `docs/handoffs/phase-N.md`, from `docs/handoffs/TEMPLATE.md` | end of each phase |

1. Each phase runs on its own branch `v2/phase-N`, branched from `v2/main`. (Git cannot hold a branch called `v2` next to `v2/phase-N`, so the base branch is `v2/main`.)
2. Start a session and paste: *"Read CLAUDE.md and docs/CONTEXT.md, then execute docs/prompts/phase-N.md. Stop at the gate."*
3. When the agent reports the gate, start a **fresh** session with Gate B from `docs/prompts/gate.md`. Merge into `v2/main` only if the reviewer passes the phase.
4. Ask the agent to write the handoff and regenerate `docs/CONTEXT.md`. Then move to the next phase.
5. Steps marked **[HUMAN]** need a person (licences, Deaf signers, recordings, GPU time, measurements on real devices). The agent prepares the tooling and stops at them.

The Phase 0 test suite (`python tools/run_all_tests.py`) must pass on every merge.
