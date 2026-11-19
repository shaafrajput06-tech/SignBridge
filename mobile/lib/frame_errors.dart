// Honest error reporting for the phone's camera frame loop (Phase 1, finding F5).
//
// Phase 0 showed every failure as "Local server unavailable", including errors in the phone's own
// frame conversion. describeFrameError says what actually went wrong, and the app logs the error
// type and stack trace.

import 'dart:async';
import 'dart:io';

import 'package:http/http.dart' as http;

enum FrameErrorKind { timeout, network, serverStatus, badReply, frameFormat, unexpected }

/// The server answered with a status other than 200.
class ServerStatusException implements Exception {
  ServerStatusException(this.statusCode);
  final int statusCode;
  @override
  String toString() => 'ServerStatusException: recognition server returned $statusCode';
}

/// The camera delivered a frame layout the converter does not handle.
class UnsupportedFrameFormatException implements Exception {
  UnsupportedFrameFormatException(this.detail);
  final String detail;
  @override
  String toString() => 'UnsupportedFrameFormatException: $detail';
}

class FrameError {
  const FrameError(this.kind, this.message, {required this.serverProblem});
  final FrameErrorKind kind;
  final String message;

  /// True only when the local server is the likely cause (unreachable, slow or failing).
  final bool serverProblem;
}

FrameError describeFrameError(Object error) {
  if (error is TimeoutException) {
    return const FrameError(FrameErrorKind.timeout, 'The local server took too long to answer. Check that it is running and on the same Wi-Fi.', serverProblem: true);
  }
  if (error is SocketException || error is http.ClientException) {
    return const FrameError(FrameErrorKind.network, 'Local server unavailable. Check the server address in Settings and that both devices share the Wi-Fi.', serverProblem: true);
  }
  if (error is ServerStatusException) {
    return FrameError(FrameErrorKind.serverStatus, 'The local server returned an error (${error.statusCode}). Check the server window for details.', serverProblem: true);
  }
  if (error is FormatException) {
    return const FrameError(FrameErrorKind.badReply, 'The server reply could not be read. The phone app and the server may be different versions.', serverProblem: false);
  }
  if (error is UnsupportedFrameFormatException || error is RangeError) {
    return FrameError(FrameErrorKind.frameFormat, 'This phone camera sent a frame format SignBridge cannot read yet ($error).', serverProblem: false);
  }
  return FrameError(FrameErrorKind.unexpected, 'Recognition stopped because of an unexpected error: $error', serverProblem: false);
}
