// Not run in the Phase 1 workspace (no Flutter SDK there). Run with: flutter test (from mobile/).
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:signbridge_mobile/frame_convert.dart';
import 'package:signbridge_mobile/frame_errors.dart';

// A 3 x 2 image whose pixels are numbered by their red channel: 10 20 30 / 40 50 60.
img.Image numbered() {
  final image = img.Image(width: 3, height: 2);
  var value = 10;
  for (var y = 0; y < 2; y++) {
    for (var x = 0; x < 3; x++) {
      image.setPixelRgb(x, y, value, 0, 0);
      value += 10;
    }
  }
  return image;
}

List<List<int>> reds(img.Image image) => [
      for (var y = 0; y < image.height; y++) [for (var x = 0; x < image.width; x++) image.getPixel(x, y).r.toInt()]
    ];

void main() {
  test('rotateClockwise turns the image clockwise (same as numpy rot90 with k = -1)', () {
    expect(reds(rotateClockwise(numbered(), 0)), [[10, 20, 30], [40, 50, 60]]);
    expect(reds(rotateClockwise(numbered(), 90)), [[40, 10], [50, 20], [60, 30]]);
    expect(reds(rotateClockwise(numbered(), 180)), [[60, 50, 40], [30, 20, 10]]);
    expect(reds(rotateClockwise(numbered(), 270)), [[30, 60], [20, 50], [10, 40]]);
    expect(() => rotateClockwise(numbered(), 45), throwsArgumentError);
  });

  // 4 x 2 frame: luminance 16 + 10 * index, neutral chroma, so every pixel is grey.
  final luminance = Uint8List.fromList([for (var i = 0; i < 8; i++) 16 + 10 * i]);

  test('3-plane Android YUV420 converts', () {
    final planes = [FramePlane(luminance, 4, 1), FramePlane(Uint8List.fromList([128, 128]), 2, 1), FramePlane(Uint8List.fromList([128, 128]), 2, 1)];
    final image = imageFromPlanes(4, 2, planes);
    expect(image.getPixel(0, 0).r.toInt(), 0);
    expect(image.getPixel(3, 1).r, image.getPixel(3, 1).g);
  });

  test('2-plane iOS NV12 converts instead of throwing a RangeError (F5)', () {
    final planes = [FramePlane(luminance, 4, 1), FramePlane(Uint8List.fromList([128, 128, 128, 128]), 4, 2)];
    final image = imageFromPlanes(4, 2, planes);
    expect(image.width, 4);
    expect(image.getPixel(1, 0).r, image.getPixel(1, 0).b);
  });

  test('1-plane BGRA8888 converts', () {
    final bgra = Uint8List.fromList([1, 2, 3, 255, 4, 5, 6, 255]);
    final image = imageFromPlanes(2, 1, [FramePlane(bgra, 8, 4)]);
    expect([image.getPixel(0, 0).r.toInt(), image.getPixel(0, 0).g.toInt(), image.getPixel(0, 0).b.toInt()], [3, 2, 1]);
  });

  test('unknown layouts raise UnsupportedFrameFormatException', () {
    expect(() => imageFromPlanes(4, 2, []), throwsA(isA<UnsupportedFrameFormatException>()));
  });

  test('uprightJpeg rotates before encoding', () {
    final planes = [FramePlane(luminance, 4, 1), FramePlane(Uint8List.fromList([128, 128]), 2, 1), FramePlane(Uint8List.fromList([128, 128]), 2, 1)];
    final decoded = img.decodeJpg(uprightJpeg(4, 2, planes, 90))!;
    expect([decoded.width, decoded.height], [2, 4]);
  });
}
