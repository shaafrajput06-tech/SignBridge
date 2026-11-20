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

GOOD TO KNOW
- PSL (Pakistan Sign Language) is the main language of SignBridge. The app always shows which sign
  language is active and how sure it is. What PSL recognition covers in this copy is shown on the
  PSL screen and on the "How well it works" page when that page is included.
- The ASL button at the top switches to American Sign Language mode (250 words). ASL is a separate
  language and is never shown as PSL.
- Signs learned from public datasets are marked "Community dataset - not yet validated" until Deaf
  signers have checked them.
- Needs Windows 10 or 11 with a webcam. On a Mac or a phone, use the website instead:
  https://signbridge-pk.github.io/

CREDITS AND LICENCES
- ASL model: 1st place of Google's Isolated Sign Language Recognition competition by Hoyeol Sohn
  (MIT licence), trained on signs by Deaf signers from the Deaf Professional Arts Network and
  Georgia Tech (CC BY 4.0).
- Hand, pose and face tracking: Google MediaPipe models and runtime (Apache 2.0).
- Browser model runtime: Google LiteRT.js (Apache 2.0).
- Interface: React (MIT).
- Any PSL reference clips included come from Sign Language Datasets by Mudassar Iqbal (2023),
  github.com/sign-language-translator/sign-language-datasets, CC BY 4.0.
