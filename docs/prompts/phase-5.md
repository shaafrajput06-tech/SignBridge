# Phase 5 — Continuous signing and fingerspelling

OBJECTIVE
Let a signer sign naturally, several signs in a row, without holding still between them, and spell
names and words that are not in the lexicon.

INPUTS
Phase 3-4 models, recording format v2, Urdu alphabet sources from the ledger.

TASKS
1. Sign spotting: a streaming segmenter over the landmark stream (start with hand-speed and
   presence energy; then a small learned boundary model on recorded continuous clips). Replace the
   fixed 8-frame hold.
2. Streaming inference: sliding windows with overlap, de-duplication of repeated outputs, and a
   gloss lattice (top-k per segment with confidences) passed to Phase 6.
3. Fingerspelling: PSL Urdu alphabet recogniser (static + dynamic letters) as a separate head; a
   "spelling mode" entered automatically when the segmenter sees fingerspelling motion, or by a
   button. Output assembled into Urdu script.
4. [HUMAN] Record continuous sentences: >= 200 short sentences x >= 10 signers, gloss-annotated by
   Deaf annotators (the studio gets a sentence mode and an annotation timeline).
5. Later option, documented not built: CTC-based continuous recogniser once sentence data exists.

ACCEPTANCE GATE (held-out signers)
- Segment boundary F1 >= 0.85 at +/-200 ms on continuous test clips.
- Gloss error rate on continuous Tier A sentences <= 20% (report WER-style substitutions,
  deletions, insertions).
- Fingerspelling letter accuracy >= 90% on held-out signers.
- End-to-end latency, end of sign to text on screen: <= 300 ms on a mid-range laptop.

OUT OF SCOPE
Full PSL grammar translation (Phase 6).
