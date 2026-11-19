# Gate A — Self-check (run by the building agent)

Before you report Phase N as done:
1. Run python tools/run_all_tests.py --smoke and every new test. Paste the summary.
2. For each acceptance criterion in docs/prompts/phase-N.md, write: criterion | measured value |
   command or report that produced it | PASS / FAIL. No criterion may be marked PASS without a number
   or a test name.
3. Run the licence checker and the vocabulary sync check.
4. List every number you mention anywhere (docs, UI strings, commits) and the file it comes from.
5. List what you did NOT do, what you could not test, and every [HUMAN] step still open.
6. If any criterion FAILS, stop. Report the failure plainly. Do not lower the target.

---

# Gate B — Independent reviewer (fresh session, read-only)

You are reviewing Phase N of SignBridge v2. You did not build it. Assume claims are wrong until the
repository proves them.

Read CLAUDE.md, docs/prompts/phase-N.md, docs/handoffs/phase-N.md (draft) and the diff from the
previous phase branch. Then:
1. Re-run the tests and the measurements yourself. Compare with the self-check table.
2. Hunt for data leakage: any signer, session or near-duplicate clip in both train and test; any
   threshold tuned on the test set; any augmentation applied before the split.
3. Hunt for honesty violations: numbers without a source, Tier A glosses that missed the gate,
   ASL labels used for PSL, assets missing from LICENSES.yaml, video stored without consent.
4. Hunt for regressions: Phase 0 behaviour, parity across Python / JS / Dart, offline operation.
5. Check the UI says which tier each output came from and never auto-speaks Tier B.

Output: PASS or FAIL, then a table of findings (severity, file:line, evidence, fix). FAIL on any
leakage, honesty or licence finding regardless of how good the metrics look.
