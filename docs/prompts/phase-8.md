# Phase 8 — Field evaluation, hardening and release

OBJECTIVE
Prove the system works for real Deaf users in real places, harden it, and release v2.0 with a
public model card and dataset card.

TASKS
1. [HUMAN] Field study with >= 20 Deaf PSL signers not in any training data, in homes, classrooms and
   a clinic or office: task success, errors, perceived usefulness, and what they want next.
2. Fairness: accuracy by signer group, region, age, gender, skin tone and device; any group > 5 points
   below average becomes a data-collection priority before release.
3. Security: threat model, dependency audit, authentication on every write and export route, signed
   model bundles verified at load, no PII in logs.
4. Release: model card, dataset card, licence attributions screen in the app, changelog, a reproducible
   training recipe, and versioned bundle download for updates.
5. Flywheel: a monthly cycle of validator review -> retrain -> eval gate -> promote B to A.

ACCEPTANCE GATE
- Field accuracy within 5 points of the lab test set, or the gap is explained and published.
- Zero critical or high findings open in the security review.
- Model and dataset cards published with every number traceable to a committed report.
