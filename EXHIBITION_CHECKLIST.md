# SignBridge exhibition checklist

1. Test the webcam.
2. Run demo mode.
3. Test English voice.
4. Test Urdu text and Urdu voice.
5. Run audio pre-cache while internet is available.
6. Keep the model and vocabulary files in the project folder.
7. Test the program on the exhibition computer.
8. Keep a fallback camera index ready.
9. Do not claim all vocabulary words have been ML-trained unless data was actually collected.

Before opening the doors, run `run_tests.bat`, check `http://localhost:8000/api/health` (or the API docs at `http://localhost:8000/docs`) if the connected system is used, confirm the exhibition computer's Wi-Fi address, and test the phone connection while on the same network.
