SignBridge - shared copy
========================

SignBridge turns hand signs into words. It runs entirely on your computer: the camera picture never
leaves it, and nothing is recorded.

HOW TO START (Windows)
1. Right-click the zip file and choose "Extract All...", then open the extracted folder.
   (Do not run it from inside the zip.)
2. Double-click "Start SignBridge.bat".
   - If Windows says "Windows protected your PC", click "More info", then "Run anyway".
     This appears because the file came from the internet.
3. Your browser opens SignBridge at http://localhost:8765 . Use Chrome or Edge.
4. Click "Enable camera" and allow the camera. Keep both hands, your shoulders and your face in view.
5. To stop SignBridge, close the black window that opened in step 2.

WHAT TO TRY
- Translate > Test signs: tap a card and copy the hand in its picture.
- Vocabulary: tap a word to see a video of a real person signing it (31 words have one).
- The ASL button at the top switches to American Sign Language mode (250 words).
- Settings (gear button): 10 colour themes and larger text.

GOOD TO KNOW
- PSL camera recognition here covers 13 simple demo hand shapes. They are demo shapes, not verified
  Pakistan Sign Language signs.
- ASL mode is a separate language and is never shown as PSL.
- The PSL videos come from a community dictionary and have not yet been validated by Deaf signers.
- Needs Windows 10 or 11 with a webcam. On a Mac or phone, ask for the website link instead.

CREDITS AND LICENCES
- PSL "How to sign" videos: Pakistan Sign Language dictionary clips from Sign Language Datasets by
  Mudassar Iqbal (2023), github.com/sign-language-translator/sign-language-datasets, CC BY 4.0.
- ASL model: 1st place of Google's Isolated Sign Language Recognition competition by Hoyeol Sohn
  (MIT licence), trained on signs by Deaf signers from the Deaf Professional Arts Network and
  Georgia Tech (CC BY 4.0).
- Hand, pose and face tracking: Google MediaPipe models and runtime (Apache 2.0).
- Browser model runtime: Google LiteRT.js (Apache 2.0).
- Icons: Lucide (ISC). Interface: React (MIT).
