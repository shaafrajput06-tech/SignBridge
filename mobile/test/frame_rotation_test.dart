// Not run in the Phase 1 workspace (no Flutter SDK there). Run with: flutter test (from mobile/).
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:signbridge_mobile/frame_rotation.dart';

void main() {
  final cases = jsonDecode(File('../tests/golden/rotation_cases.json').readAsStringSync()) as Map<String, dynamic>;

  test('shared rotation cases match the Python rule', () {
    for (final item in (cases['cases'] as List).cast<Map<String, dynamic>>()) {
      expect(
        correctionRotationDegrees(
          sensorOrientation: item['sensor'] as int,
          deviceOrientation: item['device'] as String,
          lensDirection: item['lens'] as String,
          platform: item['platform'] as String,
        ),
        item['expected'],
        reason: '$item',
      );
    }
  });

  test('device orientation table matches the shared fixture', () {
    expect(deviceOrientationDegrees, (cases['device_orientation_degrees'] as Map).cast<String, int>());
  });

  test('invalid values are rejected', () {
    expect(() => correctionRotationDegrees(sensorOrientation: 45, deviceOrientation: 'portraitUp', lensDirection: 'back', platform: 'android'), throwsArgumentError);
    expect(() => correctionRotationDegrees(sensorOrientation: 90, deviceOrientation: 'sideways', lensDirection: 'back', platform: 'android'), throwsArgumentError);
    expect(() => correctionRotationDegrees(sensorOrientation: 90, deviceOrientation: 'portraitUp', lensDirection: 'periscope', platform: 'android'), throwsArgumentError);
  });
}
