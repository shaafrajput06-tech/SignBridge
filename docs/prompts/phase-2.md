# Phase 2 — Data engine, licence ledger, vocabulary v2, recording studio

OBJECTIVE
Build the machinery that turns licensed sources and consenting Deaf signers into clean, versioned,
signer-split PSL training data, and expand the vocabulary from 64 entries to a gloss lexicon.

INPUTS
Phase 1 handoff, CONTEXT.md ledger candidates, vocabulary.json, collect_data.py, backend/.

TASKS
1. Licence ledger: create data/LICENSES.yaml with a JSON schema and a checker. Allowed uses:
   pretrain_encoder | train_labels | reference_clip | redistribute_weights. CI fails if any asset
   in data/ or models/ lacks an entry allowing its use.
2. Vocabulary v2 schema (keep every v1 field and ID):
   gloss_id, english, urdu, roman_urdu, category, variants[] (region, reference clip),
   handedness (one/two), has_movement, non_manual_markers, tier (A/B/C/D), sources[],
   validated_by, validated_on. Migrate the 64 entries; tiers start at D except demo poses.
   Extend tools/sync_vocabulary.py to the new schema.
3. Ingestion adapters `data_engine/adapters/` for each ledger candidate. Each converts to recording
   format v2 (re-extracting landmarks from video where needed), maps labels to gloss IDs through a
   reviewed mapping CSV, and never runs unless the ledger allows the use.
4. Recording studio: upgrade collect_data.py and add a web route `/studio` that prompts a gloss,
   shows its reference clip, records 2-4 s sequences with countdown, auto-trims idle frames, and
   lets the signer re-take. Consent screen first; video saved only on explicit opt-in.
5. Quality checks: hand presence %, frame rate, duration, outlier detection, near-duplicate detection,
   label-consistency check (embedding distance to other instances of the same gloss).
6. Splits: deterministic signer-level train/val/test (test signers never seen in training), stored as
   manifests. A dataset card per release (`data/cards/psl-vN.md`): glosses, signers, instances, sources.
7. Validator workflow: a review page where a Deaf validator approves or rejects each reference clip,
   variant and hint text; approvals are written into vocabulary v2.
8. Fix F10: authentication on training-data export; names never leave the server unauthenticated.
9. [HUMAN] Request FESF and/or NISE licences; recruit Deaf signers. Target for v2.0: 300 glosses x
   >= 15 signers x 3-5 repetitions, recorded on webcams AND phones, varied lighting and backgrounds.

DELIVERABLES
LICENSES.yaml + checker, vocabulary v2 + migration, adapters, studio, QC reports, split manifests,
dataset card, validator page, F10 fix.

ACCEPTANCE GATE
- Ledger checker blocks a deliberately unlicensed test asset.
- Re-running ingestion produces byte-identical manifests (deterministic).
- No signer appears in more than one split (test it).
- 64 v1 entries survive migration with identical IDs; all three vocabulary copies in sync.

OUT OF SCOPE
Training the recogniser (Phase 3).
