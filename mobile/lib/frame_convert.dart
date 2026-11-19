// Camera frame to upright JPEG for the local server (Phase 1, findings F4 and F5).
//
// Handles the three layouts the camera plugin delivers: Android YUV420 (3 planes), iOS YUV420
// (2 planes, NV12: interleaved U and V in plane 1) and BGRA8888 (1 plane). Phase 0 always read
// planes[2], which throws on the 2-plane iOS layout. The frame is rotated clockwise by the
// correction from frame_rotation.dart before encoding, so the server landmarks an upright hand.
// The JPEG exists only in memory and is sent to the local server; nothing is written to disk.

import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'frame_errors.dart';

class FramePlane {
  const FramePlane(this.bytes, this.bytesPerRow, this.bytesPerPixel);
  final Uint8List bytes;
  final int bytesPerRow;
  final int? bytesPerPixel;
}

int _clamp(int value) => value < 0 ? 0 : (value > 255 ? 255 : value);

void _setYuv(img.Image output, int x, int y, int luminance, int u, int v) {
  final c = luminance - 16 < 0 ? 0 : luminance - 16;
  final d = u - 128;
  final e = v - 128;
  output.setPixelRgb(x, y, _clamp((298 * c + 409 * e + 128) >> 8), _clamp((298 * c - 100 * d - 208 * e + 128) >> 8), _clamp((298 * c + 516 * d + 128) >> 8));
}

/// Convert raw camera planes to an RGB image in the sensor's orientation.
img.Image imageFromPlanes(int width, int height, List<FramePlane> planes) {
  if (width <= 0 || height <= 0) throw UnsupportedFrameFormatException('frame size ${width}x$height');
  final output = img.Image(width: width, height: height);
  if (planes.length == 3) {
    final yPlane = planes[0], uPlane = planes[1], vPlane = planes[2];
    final uvStride = uPlane.bytesPerPixel ?? 1;
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        final uvIndex = (y >> 1) * uPlane.bytesPerRow + (x >> 1) * uvStride;
        _setYuv(output, x, y, yPlane.bytes[y * yPlane.bytesPerRow + x], uPlane.bytes[uvIndex], vPlane.bytes[uvIndex]);
      }
    }
  } else if (planes.length == 2) {
    final yPlane = planes[0], uvPlane = planes[1];
    final uvStride = uvPlane.bytesPerPixel ?? 2;
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        final uvIndex = (y >> 1) * uvPlane.bytesPerRow + (x >> 1) * uvStride;
        _setYuv(output, x, y, yPlane.bytes[y * yPlane.bytesPerRow + x], uvPlane.bytes[uvIndex], uvPlane.bytes[uvIndex + 1]);
      }
    }
  } else if (planes.length == 1 && (planes[0].bytesPerPixel ?? 4) == 4) {
    final plane = planes[0];
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        final index = y * plane.bytesPerRow + x * 4;
        output.setPixelRgb(x, y, plane.bytes[index + 2], plane.bytes[index + 1], plane.bytes[index]);
      }
    }
  } else {
    throw UnsupportedFrameFormatException('${planes.length} planes, ${planes.isEmpty ? '-' : planes[0].bytesPerPixel} bytes per pixel');
  }
  return output;
}

/// Rotate clockwise by 0, 90, 180 or 270 degrees.
img.Image rotateClockwise(img.Image image, int degrees) {
  final normalised = degrees % 360;
  if (normalised % 90 != 0) throw ArgumentError.value(degrees, 'degrees', 'must be a multiple of 90');
  return normalised == 0 ? image : img.copyRotate(image, angle: normalised);
}

/// Upright JPEG bytes for the local server, at most 640 pixels wide.
Uint8List uprightJpeg(int width, int height, List<FramePlane> planes, int rotationDegrees, {int quality = 58}) {
  final upright = rotateClockwise(imageFromPlanes(width, height, planes), rotationDegrees);
  final resized = upright.width > 640 ? img.copyResize(upright, width: 640) : upright;
  return Uint8List.fromList(img.encodeJpg(resized, quality: quality));
}
