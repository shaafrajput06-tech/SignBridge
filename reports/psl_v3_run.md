# PSL v3 training run (2026-11-21)

Data: https://huggingface.co/datasets/mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset @ 1ba8b9fc58ad01431e50031fe3fe31e4d01f689d; 6818 samples, 70 classes ({'laptop': 3309, 'phone': 2308, 'webcam': 1201}). Licence ids: psl-signspeak-words. Commit c34d8ada666b.

## Device held out (weaker: no signer ids, the same people may be in both parts)

Trained on the computer-camera folders (desktop, laptop, webcam), tested on the phone folders (never seen in training). Fair test: 2151 phone signs that have computer-camera training recordings and no label conflict.

| Model | Test signs | Top-1 | Top-5 | One-handed top-1 | Two-handed top-1 | Calibration error |
|---|---|---|---|---|---|---|
| islr_lite (shipped recipe) | 2151 | 98.6 % | 99.7 % | 98.7 % (1379) | 99.0 % (763) | 0.004 |
| islr_lite + mirror averaging | 2151 | 98.6 % | 99.7 % | 98.8 % (1379) | 99.0 % (763) | 0.004 |
| GRU baseline | 2151 | 94.0 % | 99.3 % | 92.5 % (1379) | 97.6 % (763) | 0.036 |

All 2308 phone signs, including those this protocol cannot learn: top-1 91.8 %.
Signs with only phone recordings (no training data in this protocol, not measured): come, give, want.
Label conflicts (phone recordings labelled the other way round; left out of the shipped model and the fair test): toothbrush ↔ toothpaste.

Left- vs right-dominant (test signs mirrored = as a left-handed signer makes them): right 98.6 %, left 98.7 %, gap 0.1 points without mirror averaging; 0 by construction with mirror averaging (shipped).

Wrong answers among confident ones (phone test, shipped recipe):

| Shown when top-1 ≥ | Share answered | Wrong among answered |
|---|---|---|
| 0.5 | 99.5 % | 1.1 % |
| 0.6 | 99.0 % | 0.9 % |
| 0.7 | 98.7 % | 0.8 % |
| 0.8 | 98.0 % | 0.6 % |
| 0.9 | 97.2 % | 0.5 % |

Most frequent confusions: where → bring (10); help → excuseme (5); _unknown → welldone (2); peacock → hello (2); thankyou → garden (2); beard → goodmorning (1); bench → bring (1); excuseme → bring (1); fan → you (1); _unknown → have_a_good_day (1)

## Personal adaptation (Stage 4)

A simulated person confirms 20 of their own signs (phone recordings, one person per phone folder, 10 random repeats); top-1 on their other signs: 98.6 % before, 98.6 % after (+0.00 points; worst repeat +0.00).

## Independent signer (shipped model)

SLT PSL dictionary clips of the same words: one performer who is not a SignSpeak signer, one clip per sign (14 clips). Top-1 35.7 %, top-5 71.4 %. A different dictionary: a miss can also mean a regional variant of the sign, not only a model error.

| Sign | Answer | Probability | In top-5 |
|---|---|---|---|
| airplane | also | 0.35 | yes |
| all | doctor | 0.36 | no |
| cartoon | cartoon | 0.98 | yes |
| cow | deer | 0.23 | no |
| crow | crow | 0.99 | yes |
| doctor | beard | 0.24 | yes |
| dog | excuseme | 0.19 | yes |
| elephant | shower | 0.98 | yes |
| garden | bear | 0.27 | yes |
| give | give | 0.99 | yes |
| help | help | 1.00 | yes |
| peacock | garden | 0.10 | no |
| we | we | 0.94 | yes |
| who | garden | 0.43 | no |

## Shipped model

Trained on both folders except a 10 % calibration part (669 signs; same people and sessions, so weaker). Calibration part top-1 99.6 %, top-5 100.0 %. Temperature 0.55 (fitted on the held-out device's predictions of the same recipe), mirror averaging on.

| Export | Bytes | Top-1 | Same top-1 as Keras | ms per sign (Python, CPU) |
|---|---|---|---|---|
| float32 | 6,632,044 | 99.6 % | 100.0 % | 2.25 |
| float16 | 3,356,956 | 99.6 % | 100.0 % | 2.2 |
| int8 (chosen) | 1,854,048 | 99.6 % | 100.0 % | 1.39 |

Tiers: 0 Tier A, 69 Tier B. Tier A needs a signer-independent test (CLAUDE.md 1, 8.3). SignSpeak publishes no signer ids, so no sign can pass that test with this data: every sign is Tier B ("Suggested — please confirm").

## Per sign (device held out, shipped recipe)

| Sign | Hands | Train | Test | Top-1 | Top-5 |
|---|---|---|---|---|---|
| Absolutely | one | 91 | 31 | 100.0 % | 100.0 % |
| Air crash | two | 91 | 31 | 100.0 % | 100.0 % |
| Airplane | one | 93 | 33 | 100.0 % | 100.0 % |
| All | two | 93 | 33 | 100.0 % | 100.0 % |
| Also | one | 91 | 31 | 100.0 % | 100.0 % |
| Arrival | one | 90 | 30 | 100.0 % | 100.0 % |
| Assalam-o-alaikum | one | 108 | 51 | 100.0 % | 100.0 % |
| ATM | one | 90 | 30 | 100.0 % | 100.0 % |
| Bald | one | 90 | 30 | 100.0 % | 100.0 % |
| Beach | two | 90 | 30 | 100.0 % | 100.0 % |
| Beak | one | 90 | 30 | 100.0 % | 100.0 % |
| Bear | two | 90 | 30 | 100.0 % | 100.0 % |
| Beard | one | 91 | 31 | 96.8 % | 100.0 % |
| Bed | two | 90 | 30 | 100.0 % | 100.0 % |
| Bench | one | 94 | 34 | 97.1 % | 100.0 % |
| Bicycle | two | 90 | 30 | 100.0 % | 100.0 % |
| Both | one | 92 | 32 | 100.0 % | 100.0 % |
| Bridge | two | 91 | 31 | 100.0 % | 100.0 % |
| Bring | one | 110 | 52 | 100.0 % | 100.0 % |
| Light bulb | one | 91 | 31 | 100.0 % | 100.0 % |
| Cartoon | two | 90 | 30 | 100.0 % | 100.0 % |
| Chimpanzee | two | 92 | 32 | 100.0 % | 100.0 % |
| Coloured pencils | one | 90 | 30 | 100.0 % | 100.0 % |
| Come | one | 30 | 0 | — | — |
| Cow | one | 91 | 31 | 100.0 % | 100.0 % |
| Crow | one | 91 | 31 | 100.0 % | 100.0 % |
| Cupboard | two | 91 | 31 | 100.0 % | 100.0 % |
| Deer | two | 90 | 30 | 100.0 % | 100.0 % |
| Doctor | one | 71 | 30 | 100.0 % | 100.0 % |
| Dog | two | 93 | 33 | 100.0 % | 100.0 % |
| Don't touch | one | 92 | 32 | 100.0 % | 100.0 % |
| Door | two | 94 | 34 | 100.0 % | 100.0 % |
| Elephant | one | 90 | 30 | 100.0 % | 100.0 % |
| Excuse me | two | 108 | 50 | 98.0 % | 100.0 % |
| Face lotion | one | 90 | 30 | 100.0 % | 100.0 % |
| Fan | one | 91 | 31 | 96.8 % | 100.0 % |
| Garden | one | 91 | 31 | 100.0 % | 100.0 % |
| Generator | two | 91 | 31 | 100.0 % | 100.0 % |
| Give | one | 27 | 0 | — | — |
| Goodbye | one | 109 | 51 | 100.0 % | 100.0 % |
| Good morning | one | 91 | 31 | 100.0 % | 100.0 % |
| Have a good day | one | 92 | 32 | 100.0 % | 100.0 % |
| Hello | one | 109 | 51 | 100.0 % | 100.0 % |
| Help | two | 72 | 30 | 83.3 % | 100.0 % |
| Hungry | one | 72 | 30 | 100.0 % | 100.0 % |
| I have a complaint | one | 93 | 33 | 100.0 % | 100.0 % |
| Life jacket | two | 90 | 30 | 100.0 % | 100.0 % |
| Mine | one | 91 | 31 | 100.0 % | 100.0 % |
| Mobile phone | two | 92 | 32 | 100.0 % | 100.0 % |
| Nail cutter | two | 90 | 30 | 100.0 % | 100.0 % |
| Need | two | 74 | 32 | 100.0 % | 100.0 % |
| Peacock | two | 90 | 30 | 93.3 % | 93.3 % |
| Police car | one | 90 | 30 | 100.0 % | 100.0 % |
| Razor | one | 90 | 30 | 100.0 % | 100.0 % |
| Shampoo | two | 92 | 32 | 100.0 % | 100.0 % |
| Shower | one | 91 | 31 | 100.0 % | 100.0 % |
| Sunglasses | two | 91 | 31 | 100.0 % | 100.0 % |
| Thank you | one | 108 | 50 | 94.0 % | 100.0 % |
| Tissue paper | one | 90 | 30 | 100.0 % | 100.0 % |
| Toothbrush | one | 63 | 0 | — | — |
| Toothpaste | two | 63 | 0 | — | — |
| Umbrella | two | 90 | 30 | 100.0 % | 100.0 % |
| Want | one | 28 | 0 | — | — |
| Water | one | 108 | 50 | 100.0 % | 100.0 % |
| We | one | 92 | 32 | 96.9 % | 100.0 % |
| Well done | one | 92 | 32 | 100.0 % | 100.0 % |
| Where | one | 91 | 51 | 80.4 % | 100.0 % |
| Who | one | 72 | 30 | 100.0 % | 100.0 % |
| You | one | 92 | 32 | 100.0 % | 100.0 % |
| Not a sign | one | 19 | 9 | 44.4 % | 55.6 % |

Training runs: islr_lite 4059 samples 100 epochs 1388.8 s; gru 4059 samples 100 epochs 558.8 s; islr_lite 6086 samples 100 epochs 2074.6 s
