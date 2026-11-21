# What's new in SignBridge 3.0

The website's "What's new" page and the GitHub Release notes are made from this file (tools/site_pages.py).

## PSL from the camera
- The camera now suggests Pakistan Sign Language words. It learned them from a public PSL dataset of hand movements (SignSpeak).
- Every PSL answer is a suggestion (Tier B) that you confirm. Nothing is spoken until you tap "Yes".
- These signs are marked "Community dataset — not yet validated" until Deaf signers check them.
- Your confirmations tune the suggestions to your own signing. This is kept only in your browser, and "Forget them" removes it.
- A five-second camera check tells you if the light, distance or framing will cause problems.

## Talking both ways
- Confirmed signs build a sentence in English or Urdu, with the signs you made shown underneath.
- The hearing person can type a reply. It is shown in large text, and the words SignBridge knows play as PSL dictionary videos, word by word.
- Quick phrases and emergency phrases speak with one tap.

## Seeing how signs are made
- The dictionary videos are back for 31 vocabulary words.
- A new Dictionary page lists every sign of a community PSL dictionary, each with its video.

## ASL mode
- ASL mode runs in the background again. On the old site its model could not load in a Web Worker and ran on the main page instead.
- It speaks a word only when it is at least 70 % sure.

## Faster, offline and clearer
- The first visit loads less: the camera software and ASL mode load only when you use them.
- "Save for offline use" stores the whole site on your device, so it works with no internet.
- Text is larger and easier to read everywhere.
- New pages: "How well it works" (every measured number, with where and how it was measured), "Credits and licences" and this page.

## Still limited
- No sign is Tier A ("Recognised") yet. That needs a test on people the model has never seen, and a Deaf validator's sign-off.
- Finger-spelling is not included yet. The Urdu alphabet data (UAlpha40, CC BY 4.0) is licensed and its converter is written, but the letter model is not trained and tested yet.
- The PSL camera knows single words signed one at a time, with a pause between them, not full sentences signed without pauses.
