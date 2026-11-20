# PSL v3 training run (2026-11-20)

Data: https://huggingface.co/datasets/mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset @ 1ba8b9fc58ad01431e50031fe3fe31e4d01f689d; 6830 samples, 71 classes ({'laptop': 3309, 'phone': 2308, 'webcam': 1213}). Licence ids: psl-signspeak-words. Commit 25e3eda5bd56.

## Device held out (weaker: no signer ids, the same people may be in both parts)

Trained on the computer-camera folders (desktop, laptop, webcam), tested on the phone folders (never seen in training).

| Model | Test signs | Top-1 | Top-5 | One-handed top-1 | Two-handed top-1 | Calibration error |
|---|---|---|---|---|---|---|
| islr_lite (shipped recipe) | 2308 | 91.7 % | 92.9 % | 90.4 % (1504) | 94.8 % (795) | 0.060 |
| islr_lite + mirror averaging | 2308 | 91.7 % | 93.0 % | 90.4 % (1504) | 95.0 % (795) | 0.059 |
| GRU baseline | 2308 | 88.2 % | 92.9 % | 85.7 % (1504) | 93.5 % (795) | 0.076 |

Left- vs right-dominant (test signs mirrored = as a left-handed signer makes them): right 91.7 %, left 91.6 %, gap 0.0 points without mirror averaging; 0 by construction with mirror averaging (shipped).

Wrong answers among confident ones (phone test, shipped recipe):

| Shown when top-1 ≥ | Share answered | Wrong among answered |
|---|---|---|
| 0.5 | 99.3 % | 7.8 % |
| 0.6 | 98.6 % | 7.5 % |
| 0.7 | 97.5 % | 6.9 % |
| 0.8 | 96.5 % | 6.6 % |
| 0.9 | 93.7 % | 5.8 % |

Most frequent confusions: toothpaste → toothbrush (32); want → we (31); give → beard (30); toothbrush → toothpaste (29); come → elephant (25); where → bring (10); come → airplane (8); help → excuseme (5); bench → bring (3); _unknown → bench (2)

## Independent signer (shipped model)

Not measured in this run (no web-learned SLT landmarks given).

## Shipped model

Trained on both folders except a 10 % calibration part (676 signs; same people and sessions, so weaker). Calibration part top-1 99.9 %, top-5 100.0 %. Temperature 0.9 (fitted on the held-out device's predictions of the same recipe), mirror averaging on.

| Export | Bytes | Top-1 | Same top-1 as Keras | ms per sign (Python, CPU) |
|---|---|---|---|---|
| float32 | 6,633,584 | 99.9 % | 100.0 % | 1.64 |
| float16 | 3,357,728 | 99.9 % | 100.0 % | 1.61 |
| int8 (chosen) | 1,854,456 | 99.9 % | 100.0 % | 0.92 |

Tiers: 0 Tier A, 70 Tier B. Tier A needs a signer-independent test (CLAUDE.md 1, 8.3). SignSpeak publishes no signer ids, so no sign can pass that test with this data: every sign is Tier B ("Suggested — please confirm").

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
| Beard | one | 91 | 31 | 100.0 % | 100.0 % |
| Bed | two | 90 | 30 | 100.0 % | 100.0 % |
| Bench | one | 94 | 34 | 91.2 % | 100.0 % |
| Bicycle | two | 90 | 30 | 100.0 % | 100.0 % |
| Both | one | 92 | 32 | 100.0 % | 100.0 % |
| Bridge | two | 91 | 31 | 100.0 % | 100.0 % |
| Bring | one | 110 | 52 | 100.0 % | 100.0 % |
| Light bulb | one | 91 | 31 | 100.0 % | 100.0 % |
| Cartoon | two | 90 | 30 | 100.0 % | 100.0 % |
| Chimpanzee | two | 92 | 32 | 100.0 % | 100.0 % |
| Coloured pencils | one | 90 | 30 | 100.0 % | 100.0 % |
| Come | one | 30 | 33 | 0.0 % | 0.0 % |
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
| Fan | one | 91 | 31 | 100.0 % | 100.0 % |
| Garden | one | 91 | 31 | 100.0 % | 100.0 % |
| Generator | two | 91 | 31 | 100.0 % | 100.0 % |
| Give | one | 27 | 30 | 0.0 % | 0.0 % |
| Goodbye | one | 109 | 51 | 100.0 % | 100.0 % |
| Good morning | one | 91 | 31 | 100.0 % | 100.0 % |
| Have a good day | one | 92 | 32 | 100.0 % | 100.0 % |
| Hello | one | 109 | 51 | 100.0 % | 100.0 % |
| Help | two | 72 | 30 | 83.3 % | 100.0 % |
| Hungry | one | 72 | 30 | 96.7 % | 100.0 % |
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
| Test2 | one | 11 | 0 | — | — |
| Thank you | one | 108 | 50 | 90.0 % | 100.0 % |
| Tissue paper | one | 90 | 30 | 100.0 % | 100.0 % |
| Toothbrush | one | 91 | 31 | 0.0 % | 0.0 % |
| Toothpaste | two | 92 | 32 | 0.0 % | 0.0 % |
| Umbrella | two | 90 | 30 | 100.0 % | 100.0 % |
| Want | one | 28 | 31 | 0.0 % | 0.0 % |
| Water | one | 108 | 50 | 100.0 % | 100.0 % |
| We | one | 92 | 32 | 96.9 % | 100.0 % |
| Well done | one | 92 | 32 | 100.0 % | 100.0 % |
| Where | one | 91 | 51 | 80.4 % | 98.0 % |
| Who | one | 72 | 30 | 100.0 % | 100.0 % |
| You | one | 92 | 32 | 100.0 % | 100.0 % |
| Not a sign | one | 19 | 9 | 33.3 % | 77.8 % |

Training runs: islr_lite 4070 samples 100 epochs 1049.3 s; gru 4070 samples 100 epochs 394.7 s; islr_lite 6154 samples 100 epochs 1587.3 s
