# Phase 4 — Tier B suggestions, Tier C personal signs, open-set behaviour

OBJECTIVE
Cover every licensed lexicon sign on first launch as a suggestion, let users add their own signs in
seconds without retraining, and handle signs the system has never seen gracefully.

INPUTS
Phase 3 encoder (embedding head), lexicon reference clips cleared for reference_clip use.

TASKS
1. Prototype index: embed every validated reference clip (all variants) into a compact on-device index
   (cosine similarity; brute force is fine up to ~10k prototypes). Ship it in the bundle.
2. Tier B flow: when no Tier A gloss passes threshold, show the top-3 lexicon matches with their reference
   clips; the user taps to confirm. Confirmed answers are spoken; nothing in Tier B auto-speaks.
3. Tier C flow ("Teach SignBridge a sign"): pick or type a phrase, record 3-5 examples, add a personal
   prototype on-device immediately. Personal prototypes stay local unless the user donates them.
4. Open set: if neither tier passes, say "Not sure — try again or fingerspell" and log nothing
   identifying. Measure open-set rejection on held-out glosses.
5. Data flywheel: with consent, confirmed Tier B selections and donated Tier C samples become
   candidate training data, queued for validator review before any training use.
6. Coverage screen: show per-tier counts and let users browse which signs are Recognised vs Suggested.

DELIVERABLES
Index builder, retrieval in Python/web/Flutter, teach-a-sign UI, coverage screen, flywheel queue,
reports/retrieval_vN.md.

ACCEPTANCE GATE
- Tier B: correct sign in top-3 for >= 70% of held-out-signer queries over the lexicon (report top-1/3/10).
- Tier C: after 5 examples, >= 90% top-1 for the enrolling user on a 10-sign personal set.
- Retrieval adds <= 10 ms per query at 5,000 prototypes on a mid-range laptop.

OUT OF SCOPE
Sentence translation.
