# SignBridge mobile app

The Flutter app shares the bundled vocabulary and local API with the web and desktop clients. Vocabulary browsing, English/Urdu output, saved settings, and queued training samples remain on the phone.

## Prepare and run

Install Flutter 3.41 or newer, then from this folder run:

```bat
prepare_mobile.bat
flutter run
```

Connect a phone or start an Android/iOS simulator. For a physical phone, run the Windows project on the same Wi-Fi and enter the computer's local address in **Server**, such as `http://192.168.1.20:8000`. The address must be reachable from that phone. Allow the local firewall to accept the SignBridge API port.

Camera recognition stays off until you confirm the app's privacy notice. While it is active, individual JPEG frames travel over Wi-Fi to the configured local server for MediaPipe processing. The server processes each frame in memory and never writes the image to disk or sends the images to Google. MediaPipe Tasks may send aggregate performance and usage metrics from the server to Google while online; see [MediaPipe's privacy notice](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/web/vision/README.md#privacy-notice).

## Offline behavior and data

- All 64 vocabulary entries are bundled for offline browsing.
- English and Urdu speech use voices installed on the phone.
- The desktop and web clients can run demo recognition without a network connection.
- Mobile camera recognition works without internet when the local computer and phone share a network and the SignBridge server is running.
- Consented landmark samples are saved in the local SQLite dataset. Samples that cannot be sent immediately are queued in the phone's SQLite database and sent when the local server becomes available.
- Camera images are never added to a training set.

The camera plugin supports Android and iOS. The project starter requires Flutter 3.41 or newer. Local HTTP is enabled for a private exhibition LAN; use a trusted HTTPS endpoint outside that setting.

## Tests

`flutter test` (from this folder) runs the unit tests in `test/`: camera rotation (shared cases in `../tests/golden/rotation_cases.json`), frame conversion for 3-plane Android, 2-plane iOS and BGRA frames, and frame-loop error reporting. They were written in Phase 1 in a workspace without the Flutter SDK, so they have not been run yet.

## Phase 1 changes

- Frames are rotated upright before they are sent (`lib/frame_rotation.dart`, `lib/frame_convert.dart`), using the camera's sensor orientation and the phone's orientation.
- iOS 2-plane frames and BGRA frames are converted instead of failing.
- Frame-loop errors now say what failed (timeout, network, server error, unreadable reply, unsupported frame) and are logged with their type and stack trace, instead of always showing "Local server unavailable".
- The landmark overlay is mirrored only for the front camera.

Until these changes have been run on a real phone, keep collecting training samples on the desktop or website.
