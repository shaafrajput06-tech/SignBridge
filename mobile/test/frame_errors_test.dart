// Not run in the Phase 1 workspace (no Flutter SDK there). Run with: flutter test (from mobile/).
import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:signbridge_mobile/frame_errors.dart';

void main() {
  test('only server problems are reported as server problems (F5)', () {
    final cases = <Object, FrameErrorKind>{
      TimeoutException('slow'): FrameErrorKind.timeout,
      const SocketException('refused'): FrameErrorKind.network,
      http.ClientException('closed'): FrameErrorKind.network,
      ServerStatusException(500): FrameErrorKind.serverStatus,
      const FormatException('bad json'): FrameErrorKind.badReply,
      RangeError.index(2, [0, 1]): FrameErrorKind.frameFormat,
      UnsupportedFrameFormatException('4 planes'): FrameErrorKind.frameFormat,
      StateError('other'): FrameErrorKind.unexpected,
      TypeError(): FrameErrorKind.unexpected,
    };
    cases.forEach((error, kind) {
      final described = describeFrameError(error);
      expect(described.kind, kind, reason: '$error');
      expect(described.serverProblem, kind == FrameErrorKind.timeout || kind == FrameErrorKind.network || kind == FrameErrorKind.serverStatus, reason: '$error');
    });
  });

  test('the status code reaches the message', () {
    expect(describeFrameError(ServerStatusException(415)).message, contains('415'));
  });
}
