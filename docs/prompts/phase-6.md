# Phase 6 — Gloss to sentence, and text back to sign

OBJECTIVE
Turn gloss sequences into natural Urdu and English sentences, and turn the hearing person's reply
into something the Deaf person can read and see, so the device carries a real conversation.

TASKS
1. Gloss -> sentence, offline by default: a rule and template layer for common patterns (questions,
   negation, pronouns, time-first ordering), plus an optional small on-device language model behind
   a setting, constrained to the recognised glosses (it may reorder and inflect, never add content).
   Always show the raw glosses under the sentence so the signer can check it.
2. Use non-manual markers from the face subset (raised brows, head shake) as features for question
   and negation detection; validate with Deaf reviewers.
3. Reverse direction: speech-to-text for Urdu/English with an offline engine; the text is shown large
   and, where glosses exist, matching validated reference clips play in sequence. Mark clearly that
   this is a word-by-word aid, not signed translation.
4. Conversation view: split screen, one side per person, history in the local database, quick
   phrases, emergency phrase panel.
5. [HUMAN] Deaf and hearing reviewers rate 100 translated sentences for adequacy and fluency.

ACCEPTANCE GATE
- >= 80% of reviewed sentences rated "meaning preserved" by Deaf reviewers.
- The language model, when enabled, never outputs a content word that is not traceable to a
  recognised gloss (automated test on 1,000 lattices).
- The whole conversation loop works with networking disabled.
