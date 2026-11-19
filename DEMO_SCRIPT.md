# SignBridge demonstration script

## Introduction

“SignBridge shows how hand landmarks can connect a small set of still poses with English and Urdu text and speech. MediaPipe provides AI hand tracking. The exhibition words below use visible landmark geometry rules. A custom classifier is used only after real examples have been collected and trained.”

## Live demonstration

1. Start `start_signbridge.bat`, then open the browser or start `python main.py` for the desktop window.
2. Enable the camera and allow camera permission. Keep one hand in view and pause briefly after each pose.
3. Show a spread open palm for **Hello**.
4. Show a close, flat palm for **Stop**.
5. Show a fist for **No**, then thumbs up for **Yes** and thumbs down for **Bad**.
6. Show a V sign for **Please**, index finger upright for **Wait**, and the OK circle for **Good**.
7. Show the call-me hand for **Phone**, three raised fingers for **Thank you**, four fingers with the thumb folded for **Water**, and five close fingers for **Emergency**.
8. Point horizontally to demonstrate **Help**.
9. Switch English/Urdu and press Speak. Open Vocabulary to browse phrases without mapped demo poses.
10. Explain that “Vocabulary Mode — training data required for camera recognition” means the phrase can be displayed and spoken, but no demo geometry is assigned to it.

## Closing

“This prototype recognizes only a limited set of static poses. A high score is not assumed: model results come from recorded data and are labeled with the validation method. Natural sign languages also use motion, facial expression, body posture, and two-handed signs, which this prototype does not yet translate.”
