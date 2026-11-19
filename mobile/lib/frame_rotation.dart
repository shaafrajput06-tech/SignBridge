// Rotation correction for phone camera frames (Phase 1, finding F4).
//
// Raw camera frames arrive in the sensor's orientation. Before a frame is landmarked it must be
// rotated clockwise by correctionRotationDegrees(...) so the hand is upright, otherwise the same
// sign gives different landmarks (Phase 0 showed Wait reading as Help).
//
// Same rule as ml_engine/capture_v2.py correction_rotation_degrees; both are checked against
// tests/golden/rotation_cases.json (test/frame_rotation_test.dart here).
// Pure Dart: no Flutter imports, so it can be unit-tested anywhere.

/// Clockwise degrees for Flutter's DeviceOrientation names.
const Map<String, int> deviceOrientationDegrees = {
  'portraitUp': 0,
  'landscapeLeft': 90,
  'portraitDown': 180,
  'landscapeRight': 270,
};

/// Clockwise rotation (0, 90, 180 or 270) that makes a raw camera frame upright.
///
/// Android follows the Camera2 SENSOR_ORIENTATION rule: front cameras add the device rotation,
/// back and external cameras subtract it. iOS uses the sensor orientation the camera plugin reports,
/// as Google's ML Kit Flutter example does; that branch has not been tested on an iPhone yet.
int correctionRotationDegrees({
  required int sensorOrientation,
  required String deviceOrientation,
  required String lensDirection,
  required String platform,
}) {
  if (sensorOrientation % 90 != 0 || sensorOrientation < 0 || sensorOrientation >= 360) {
    throw ArgumentError.value(sensorOrientation, 'sensorOrientation', 'must be 0, 90, 180 or 270');
  }
  if (platform == 'ios') return sensorOrientation;
  if (platform != 'android') throw ArgumentError.value(platform, 'platform', 'must be android or ios');
  final device = deviceOrientationDegrees[deviceOrientation];
  if (device == null) throw ArgumentError.value(deviceOrientation, 'deviceOrientation', 'unknown orientation');
  if (lensDirection == 'front') return (sensorOrientation + device) % 360;
  if (lensDirection == 'back' || lensDirection == 'external') return (sensorOrientation - device + 360) % 360;
  throw ArgumentError.value(lensDirection, 'lensDirection', 'must be front, back or external');
}
