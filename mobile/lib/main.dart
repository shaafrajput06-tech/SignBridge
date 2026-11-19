import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';

import 'frame_convert.dart';
import 'frame_errors.dart';
import 'frame_rotation.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SignBridgeApp());
}

class SignBridgeApp extends StatefulWidget {
  const SignBridgeApp({super.key});

  @override
  State<SignBridgeApp> createState() => _SignBridgeAppState();
}

class _SignBridgeAppState extends State<SignBridgeApp> {
  bool _dark = true;

  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(
      seedColor: const Color(0xff55b993),
      brightness: _dark ? Brightness.dark : Brightness.light,
      surface: _dark ? const Color(0xff13221f) : Colors.white,
    );
    return MaterialApp(
      title: 'SignBridge',
      debugShowCheckedModeBanner: false,
      themeMode: _dark ? ThemeMode.dark : ThemeMode.light,
      theme: ThemeData(colorScheme: scheme, useMaterial3: true, scaffoldBackgroundColor: const Color(0xfff0f5f1)),
      darkTheme: ThemeData(colorScheme: scheme, useMaterial3: true, scaffoldBackgroundColor: const Color(0xff0d1917)),
      home: SignBridgeHome(onThemeChanged: (value) => setState(() => _dark = value)),
    );
  }
}

class SignBridgeHome extends StatefulWidget {
  const SignBridgeHome({super.key, required this.onThemeChanged});
  final ValueChanged<bool> onThemeChanged;

  @override
  State<SignBridgeHome> createState() => _SignBridgeHomeState();
}

class _SignBridgeHomeState extends State<SignBridgeHome> with WidgetsBindingObserver {
  final FlutterTts _tts = FlutterTts();
  final TextEditingController _search = TextEditingController();
  final TextEditingController _participant = TextEditingController();
  final TextEditingController _server = TextEditingController(text: 'http://127.0.0.1:8000');
  final List<String?> _recent = [];

  List<Map<String, dynamic>> _vocabulary = [];
  List<CameraDescription> _cameras = [];
  CameraController? _camera;
  Database? _localDb;
  Timer? _syncTimer;
  Map<String, dynamic>? _current;
  Map<String, dynamic>? _selected;
  List<double>? _lastFeatures;
  List<Offset> _landmarks = [];
  String _language = 'en';
  String _category = 'All categories';
  String _status = 'Show a sign to the camera';
  String _mode = 'AI Demo Mode';
  String _connection = 'Checking local server';
  String _message = '';
  int _tab = 0;
  int _lostFrames = 0;
  int _queuedSamples = 0;
  int _cameraIndex = -1;
  bool _voice = true;
  bool _romanUrdu = false;
  bool _cameraBusy = false;
  bool _cameraApproved = false;
  bool _voiceBusy = false;
  DateTime _lastFrame = DateTime.fromMillisecondsSinceEpoch(0);
  DateTime _lastSpoken = DateTime.fromMillisecondsSinceEpoch(0);
  String? _lastStableId;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initialize();
  }

  Future<void> _initialize() async {
    await _loadVocabulary();
    final preferences = await SharedPreferences.getInstance();
    _server.text = preferences.getString('server_url') ?? _server.text;
    _language = preferences.getString('language') ?? 'en';
    _romanUrdu = preferences.getBool('roman_urdu') ?? false;
    _voice = preferences.getBool('voice_enabled') ?? true;
    try {
      _localDb = await openDatabase(p.join(await getDatabasesPath(), 'signbridge-local.db'), version: 1, onCreate: (database, version) async {
        await database.execute('CREATE TABLE pending_landmarks(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)');
      });
      await _refreshQueueCount();
    } catch (error) {
      _message = 'Local sample queue could not open: $error';
    }
    await _checkServer();
    _syncTimer = Timer.periodic(const Duration(seconds: 20), (_) => unawaited(_checkServer()));
    try {
      _cameras = await availableCameras();
      final frontIndex = _cameras.indexWhere((camera) => camera.lensDirection == CameraLensDirection.front);
      _cameraIndex = frontIndex >= 0 ? frontIndex : (_cameras.isEmpty ? -1 : 0);
    } catch (error) {
      _message = 'Camera list is unavailable: $error';
    }
    if (mounted) setState(() {});
  }

  Future<void> _loadVocabulary() async {
    try {
      final raw = await rootBundle.loadString('assets/vocabulary.json');
      _vocabulary = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
    } catch (error) {
      _message = 'Bundled vocabulary could not be read: $error';
    }
    try {
      final response = await http.get(_uri('/api/vocabulary?page_size=128')).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _vocabulary = (data['items'] as List).cast<Map<String, dynamic>>();
      }
    } catch (_) {
      // The bundled vocabulary supports browsing while the backend is unavailable.
    }
    if (mounted) setState(() {});
  }

  Uri _uri(String path) => Uri.parse('${_server.text.trim().replaceAll(RegExp(r'/+$'), '')}$path');

  Future<void> _checkServer() async {
    try {
      final response = await http.get(_uri('/api/health')).timeout(const Duration(seconds: 3));
      if (response.statusCode != 200) throw StateError('Server returned ${response.statusCode}');
      final health = jsonDecode(response.body) as Map<String, dynamic>;
      final modelResponse = await http.get(_uri('/api/model-status')).timeout(const Duration(seconds: 3));
      final model = modelResponse.statusCode == 200 ? jsonDecode(modelResponse.body) as Map<String, dynamic> : <String, dynamic>{};
      if (!mounted) return;
      setState(() {
        _connection = 'Connected to local SignBridge server';
        _mode = model['available'] == true ? 'AI Trained Mode' : 'AI Demo Mode';
        if (health['model_available'] != model['available']) _status = 'Model status is updating';
      });
      await _syncPending();
    } catch (_) {
      if (mounted) setState(() => _connection = 'Local server unavailable · vocabulary remains offline');
    }
  }

  Future<void> _savePreferences() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString('server_url', _server.text.trim());
    await preferences.setString('language', _language);
    await preferences.setBool('roman_urdu', _romanUrdu);
    await preferences.setBool('voice_enabled', _voice);
  }

  Future<void> _editServer() async {
    final controller = TextEditingController(text: _server.text);
    final result = await showDialog<String>(context: context, builder: (context) => AlertDialog(
      title: const Text('Local SignBridge server'),
      content: TextField(controller: controller, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Server address', hintText: 'http://192.168.1.20:8000')),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Connect'))],
    ));
    if (result == null || result.isEmpty) return;
    setState(() { _server.text = result; _connection = 'Checking local server'; });
    await _savePreferences();
    await _checkServer();
    await _loadVocabulary();
  }

  Future<bool> _cameraNotice() async {
    if (_cameraApproved) return true;
    var allowed = false;
    final approved = await showDialog<bool>(context: context, builder: (context) => StatefulBuilder(builder: (context, refresh) => AlertDialog(
      title: const Text('Use the phone camera?'),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('When recognition starts, occasional single frames are sent over your Wi-Fi to the SignBridge server address shown in Settings.'),
        const SizedBox(height: 10),
        const Text('The server processes them in memory. It does not save camera images or video. MediaPipe Tasks may send aggregate performance and usage metrics from the server to Google while online.'),
        const SizedBox(height: 10),
        CheckboxListTile(value: allowed, onChanged: (value) => refresh(() => allowed = value ?? false), contentPadding: EdgeInsets.zero, title: const Text('I understand and want to start camera recognition with these metrics.'), controlAffinity: ListTileControlAffinity.leading),
      ]),
      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Not now')), FilledButton(onPressed: allowed ? () => Navigator.pop(context, true) : null, child: const Text('Continue'))],
    )));
    _cameraApproved = approved == true;
    return _cameraApproved;
  }

  Future<void> _startCamera() async {
    if (!await _cameraNotice()) return;
    if (_cameras.isEmpty) {
      setState(() => _status = 'No camera is available. Vocabulary browsing still works.');
      return;
    }
    final cameraInfo = _cameras[_cameraIndex < 0 ? 0 : _cameraIndex];
    final controller = CameraController(cameraInfo, ResolutionPreset.low, enableAudio: false, imageFormatGroup: ImageFormatGroup.yuv420);
    try {
      await controller.initialize();
      if (!mounted) { await controller.dispose(); return; }
      _camera = controller;
      await controller.startImageStream(_processFrame);
      setState(() { _status = 'Show a sign to the camera'; _message = ''; });
    } on CameraException catch (error) {
      await controller.dispose();
      setState(() => _status = error.code.contains('AccessDenied') ? 'Allow camera access in the phone settings, then try again.' : 'Camera could not start: ${error.description ?? error.code}');
    } catch (error) {
      await controller.dispose();
      setState(() => _status = 'Camera could not start: $error');
    }
  }

  // F4: rotate every frame to upright before the server landmarks it (see frame_rotation.dart).
  int _frameRotation(CameraController controller) {
    final description = controller.description;
    return correctionRotationDegrees(
      sensorOrientation: description.sensorOrientation,
      deviceOrientation: controller.value.deviceOrientation.name,
      lensDirection: description.lensDirection.name,
      platform: Platform.isIOS ? 'ios' : 'android',
    );
  }

  Uint8List _uprightJpeg(CameraImage cameraImage, int rotation) => uprightJpeg(
        cameraImage.width,
        cameraImage.height,
        [for (final plane in cameraImage.planes) FramePlane(plane.bytes, plane.bytesPerRow, plane.bytesPerPixel)],
        rotation,
      );

  // Reads /api/recognize-frame's reply. Any shape problem becomes a FormatException, so the frame loop
  // reports "unreadable reply" only for the reply and not for unrelated type errors (F5).
  ({String mode, List<Offset> landmarks, List<double>? features, String? id, String? status}) _parseRecognitionReply(String body) {
    try {
      final data = jsonDecode(body) as Map<String, dynamic>;
      return (
        mode: data['mode'] as String? ?? 'AI Demo Mode',
        landmarks: ((data['landmarks'] as List?) ?? []).map((point) => Offset(((point as List)[0] as num).toDouble(), (point[1] as num).toDouble())).toList(),
        features: data['features'] is List ? (data['features'] as List).map((value) => (value as num).toDouble()).toList() : null,
        id: data['hand_detected'] == true ? data['vocabulary_id'] as String? : null,
        status: data['status'] as String?,
      );
    } on TypeError catch (error) {
      throw FormatException('Unexpected recognition reply: $error');
    }
  }

  Future<void> _processFrame(CameraImage cameraImage) async {
    if (_cameraBusy || DateTime.now().difference(_lastFrame).inMilliseconds < 650) return;
    _cameraBusy = true;
    _lastFrame = DateTime.now();
    try {
      final controller = _camera;
      if (controller == null) return;
      final jpeg = _uprightJpeg(cameraImage, _frameRotation(controller));
      final response = await http.post(_uri('/api/recognize-frame'), headers: {'Content-Type': 'image/jpeg'}, body: jpeg).timeout(const Duration(seconds: 6));
      if (response.statusCode != 200) throw ServerStatusException(response.statusCode);
      final reply = _parseRecognitionReply(response.body);
      if (!mounted) return;
      setState(() {
        _connection = 'Connected to local SignBridge server';
        _mode = reply.mode;
        _landmarks = reply.landmarks;
        if (reply.features != null) _lastFeatures = reply.features;
        final id = reply.id;
        _recent.add(id);
        if (_recent.length > 8) _recent.removeAt(0);
        if (id == null) {
          _lostFrames++;
          _status = reply.status ?? 'Show a sign to the camera';
          if (_lostFrames >= 2) {
            _current = null;
            _lastStableId = null;
            _landmarks = [];
          }
        } else {
          _lostFrames = 0;
          final item = _vocabulary.cast<Map<String, dynamic>?>().firstWhere((value) => value?['id'] == id, orElse: () => null);
          _status = reply.status ?? 'Hold sign steady';
          if (_recent.length == 8 && _recent.every((value) => value == id) && item != null && _lastStableId != id) {
            _lastStableId = id;
            _current = item;
            _selected = item;
            _status = reply.status ?? 'Rule-based match';
            unawaited(_addHistory(id));
            unawaited(_speak(item));
          }
        }
      });
    } catch (error, stack) {
      // F5: report what actually failed instead of always blaming the server.
      final problem = describeFrameError(error);
      debugPrint('SignBridge frame loop error [${problem.kind.name}] ${error.runtimeType}: $error');
      debugPrintStack(stackTrace: stack, maxFrames: 6);
      if (mounted) {
        setState(() {
          if (problem.serverProblem) _connection = 'Local server unavailable';
          _status = problem.message;
        });
      }
    } finally {
      _cameraBusy = false;
    }
  }

  Future<void> _addHistory(String id) async {
    try {
      await http.post(_uri('/api/history'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'vocabulary_id': id, 'language': _language, 'source': 'mobile-camera'})).timeout(const Duration(seconds: 3));
    } catch (_) {}
  }

  Future<void> _speak(Map<String, dynamic> item) async {
    if (!_voice || _voiceBusy) return;
    _voiceBusy = true;
    try {
      await _tts.stop();
      await _tts.setLanguage(_language == 'ur' ? 'ur-PK' : 'en-US');
      await _tts.setSpeechRate(0.45);
      await _tts.speak(_language == 'ur' ? item['urdu'] as String : item['english'] as String);
    } catch (_) {
      if (mounted) setState(() => _message = 'This phone has no voice for the selected language. Text remains available.');
    } finally {
      _voiceBusy = false;
    }
  }

  Future<void> _stopCamera() async {
    final controller = _camera;
    _camera = null;
    if (controller != null) {
      try { if (controller.value.isStreamingImages) await controller.stopImageStream(); } catch (_) {}
      await controller.dispose();
    }
    if (mounted) setState(() { _landmarks = []; _status = 'Camera stopped'; });
  }

  Future<void> _switchCamera() async {
    if (_cameras.length < 2) return;
    final wasRunning = _camera != null;
    await _stopCamera();
    setState(() => _cameraIndex = (_cameraIndex + 1) % _cameras.length);
    if (wasRunning) await _startCamera();
  }

  Future<void> _selectItem(Map<String, dynamic> item) async {
    setState(() { _selected = item; _current = item; _status = item['demoAvailable'] == true ? 'Vocabulary selected · camera demo supported' : 'Vocabulary Mode — training data required for camera recognition'; });
    await _speak(item);
    await _addHistory(item['id'] as String);
  }

  Future<void> _saveCurrentSample() async {
    final features = _lastFeatures;
    final item = _selected ?? _current;
    if (features == null || item == null) {
      setState(() => _message = 'Start recognition, show a hand, and choose a vocabulary item first.');
      return;
    }
    var accepted = false;
    final participantController = TextEditingController(text: _participant.text);
    await showDialog<void>(context: context, builder: (context) => StatefulBuilder(builder: (context, refresh) => AlertDialog(
      title: const Text('Save training landmark?'),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        Text('This stores 63 landmark values for ${item['english']}. No camera image or video is stored.'),
        TextField(controller: participantController, decoration: const InputDecoration(labelText: 'Participant name (optional)')),
        CheckboxListTile(value: accepted, onChanged: (value) => refresh(() => accepted = value ?? false), contentPadding: EdgeInsets.zero, title: const Text('I agree to save this sample locally.'), controlAffinity: ListTileControlAffinity.leading),
      ]),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: accepted ? () => Navigator.pop(context, true) : null, child: const Text('Save sample'))],
    )));
    if (!accepted) return;
    _participant.text = participantController.text.trim();
    final payload = {
      'consent': true,
      'examples': [{'vocabulary_id': item['id'], 'participant': _participant.text.isEmpty ? 'anonymous' : _participant.text, 'session_id': 'mobile-${DateTime.now().millisecondsSinceEpoch}', 'features': features, 'frame_width': 0, 'frame_height': 0, 'handedness': 'Unknown'}],
    };
    try {
      final response = await http.post(_uri('/api/recordings'), headers: {'Content-Type': 'application/json'}, body: jsonEncode(payload)).timeout(const Duration(seconds: 5));
      if (response.statusCode != 200) throw StateError('Server returned ${response.statusCode}');
      setState(() => _message = 'Landmark sample saved on the local server.');
    } catch (_) {
      await _localDb?.insert('pending_landmarks', {'payload': jsonEncode(payload)});
      await _refreshQueueCount();
      setState(() => _message = 'No server connection. The consented landmark sample is queued on this phone and will sync when connected.');
    }
  }

  Future<void> _refreshQueueCount() async {
    final db = _localDb;
    if (db == null) return;
    final rows = await db.rawQuery('SELECT COUNT(*) AS total FROM pending_landmarks');
    if (mounted) setState(() => _queuedSamples = Sqflite.firstIntValue(rows) ?? 0);
  }

  Future<void> _syncPending() async {
    final db = _localDb;
    if (db == null) return;
    final rows = await db.query('pending_landmarks', orderBy: 'id');
    for (final row in rows) {
      try {
        final response = await http.post(_uri('/api/recordings'), headers: {'Content-Type': 'application/json'}, body: row['payload'] as String).timeout(const Duration(seconds: 4));
        if (response.statusCode != 200) break;
        await db.delete('pending_landmarks', where: 'id = ?', whereArgs: [row['id']]);
      } catch (_) { break; }
    }
    await _refreshQueueCount();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive || state == AppLifecycleState.paused) unawaited(_stopCamera());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _syncTimer?.cancel();
    unawaited(_stopCamera());
    unawaited(_tts.stop());
    _search.dispose();
    _participant.dispose();
    _server.dispose();
    super.dispose();
  }

  String _primaryText(Map<String, dynamic>? item) {
    if (item == null) return 'Show a sign to the camera';
    if (_language == 'ur') return _romanUrdu ? item['romanUrdu'] as String : item['urdu'] as String;
    return item['english'] as String;
  }

  Widget _cameraCard() {
    final camera = _camera;
    return Card(clipBehavior: Clip.antiAlias, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      AspectRatio(aspectRatio: camera?.value.isInitialized == true ? camera!.value.aspectRatio : 4 / 3, child: camera?.value.isInitialized == true ? Stack(fit: StackFit.expand, children: [
        CameraPreview(camera!),
        CustomPaint(painter: LandmarkPainter(_landmarks, mirror: camera!.description.lensDirection == CameraLensDirection.front)),
        Positioned(left: 12, top: 12, child: Chip(avatar: const Icon(Icons.circle, size: 8, color: Colors.greenAccent), label: const Text('LOCAL CAMERA'))),
      ]) : Container(color: Theme.of(context).colorScheme.surfaceContainerHighest, child: Center(child: Padding(padding: const EdgeInsets.all(25), child: Column(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.back_hand_outlined, size: 42), const SizedBox(height: 10), Text(_cameras.isEmpty ? 'No camera found' : 'Camera is off'), const SizedBox(height: 8), Text(_connection, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall)]))))),
      Padding(padding: const EdgeInsets.all(12), child: Wrap(spacing: 8, runSpacing: 8, children: [
        FilledButton.icon(onPressed: camera == null ? _startCamera : _stopCamera, icon: Icon(camera == null ? Icons.videocam : Icons.videocam_off), label: Text(camera == null ? 'Start recognition' : 'Stop camera')),
        OutlinedButton.icon(onPressed: _editServer, icon: const Icon(Icons.settings_ethernet), label: const Text('Server')),
        if (_cameras.length > 1) OutlinedButton.icon(onPressed: _switchCamera, icon: const Icon(Icons.flip_camera_android), label: const Text('Switch camera')),
      ])),
    ]));
  }

  Widget _translationCard() {
    final item = _current;
    final other = item == null ? 'Your result appears here' : _language == 'ur' ? item['english'] as String : _romanUrdu ? item['romanUrdu'] as String : item['urdu'] as String;
    return Card(child: Padding(padding: const EdgeInsets.all(18), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [Expanded(child: Text('Recognized phrase', style: Theme.of(context).textTheme.titleMedium)), Chip(label: Text(_mode, style: const TextStyle(fontSize: 10)))]),
      SegmentedButton<String>(segments: const [ButtonSegment(value: 'en', label: Text('English')), ButtonSegment(value: 'ur', label: Text('اردو'))], selected: {_language}, onSelectionChanged: (value) { setState(() => _language = value.first); _savePreferences(); }),
      const SizedBox(height: 17),
      Center(child: Directionality(textDirection: _language == 'ur' && !_romanUrdu ? TextDirection.rtl : TextDirection.ltr, child: Text(_primaryText(item), textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800, color: item == null ? null : const Color(0xffe7c06f))))),
      const SizedBox(height: 8),
      Center(child: Directionality(textDirection: _language == 'en' && !_romanUrdu && item != null ? TextDirection.rtl : TextDirection.ltr, child: Text(other, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)))),
      const SizedBox(height: 13),
      Text(_status, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xff64c99a))),
      const SizedBox(height: 14),
      Wrap(alignment: WrapAlignment.center, spacing: 8, children: [
        FilledButton.icon(onPressed: item == null ? null : () => _speak(item), icon: const Icon(Icons.volume_up), label: const Text('Speak')),
        OutlinedButton(onPressed: () { setState(() => _voice = !_voice); _savePreferences(); }, child: Text(_voice ? 'Voice on' : 'Voice off')),
        OutlinedButton(onPressed: () { setState(() => _romanUrdu = !_romanUrdu); _savePreferences(); }, child: const Text('Roman Urdu')),
      ]),
    ])));
  }

  List<String> get _categories {
    final values = {for (final item in _vocabulary) item['category'] as String}.toList()..sort();
    return ['All categories', ...values];
  }

  Widget _translatePage() => ListView(padding: const EdgeInsets.fromLTRB(14, 10, 14, 24), children: [
    Text('SignBridge', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
    const Text('Words that connect · local-first prototype'),
    const SizedBox(height: 14),
    _cameraCard(),
    const SizedBox(height: 12),
    _translationCard(),
    Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('How to demonstrate', style: Theme.of(context).textTheme.titleSmall), const SizedBox(height: 6), const Text('Frame one hand, hold a supported pose steady, then switch language or browse the vocabulary. Camera frames travel only to the local server for recognition and are not saved.')]))),
  ]);

  Widget _vocabularyPage() {
    final query = _search.text.toLowerCase().trim();
    final items = _vocabulary.where((item) => (_category == 'All categories' || item['category'] == _category) && (!query.isNotEmpty || '${item['english']} ${item['urdu']} ${item['romanUrdu']} ${item['category']}'.toLowerCase().contains(query))).toList();
    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(14, 14, 14, 7), child: TextField(controller: _search, onChanged: (_) => setState(() {}), decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search English, Urdu, Roman Urdu')),
      Padding(padding: const EdgeInsets.symmetric(horizontal: 14), child: DropdownButtonFormField<String>(value: _category, items: _categories.map((name) => DropdownMenuItem(value: name, child: Text(name))).toList(), onChanged: (value) => setState(() => _category = value ?? 'All categories'), decoration: const InputDecoration(labelText: 'Category'))),
      Expanded(child: ListView.builder(itemCount: items.length, itemBuilder: (context, index) {
        final item = items[index];
        return Card(margin: const EdgeInsets.fromLTRB(14, 5, 14, 5), child: ListTile(onTap: () => _selectItem(item), title: Text(item['english'] as String, style: const TextStyle(fontWeight: FontWeight.w700)), subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(item['romanUrdu'] as String), Text(item['category'] as String, style: Theme.of(context).textTheme.labelSmall)]), trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [Text(item['urdu'] as String, textDirection: TextDirection.rtl, style: const TextStyle(fontSize: 17)), Icon(item['demoAvailable'] == true ? Icons.check_circle_outline : Icons.school_outlined, size: 16, color: item['demoAvailable'] == true ? Colors.green : Colors.orange)])));
      })),
    ]);
  }

  Widget _trainingPage() => ListView(padding: const EdgeInsets.all(14), children: [
    Text('Collect real examples', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
    const SizedBox(height: 7),
    const Text('Choose a vocabulary phrase, start camera recognition, and explicitly save a landmark sample. Only 63 normalized coordinates and the optional participant label are kept.'),
    const SizedBox(height: 14),
    Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      DropdownButtonFormField<Map<String, dynamic>>(value: _selected, isExpanded: true, items: _vocabulary.map((item) => DropdownMenuItem(value: item, child: Text(item['english'] as String, overflow: TextOverflow.ellipsis))).toList(), onChanged: (value) => setState(() => _selected = value), decoration: const InputDecoration(labelText: 'Vocabulary item')),
      const SizedBox(height: 10),
      TextField(controller: _participant, decoration: const InputDecoration(labelText: 'Participant (optional)')),
      const SizedBox(height: 12),
      FilledButton.icon(onPressed: _saveCurrentSample, icon: const Icon(Icons.save_alt), label: const Text('Save the current hand sample')),
      const SizedBox(height: 9),
      Text('Pending offline samples: $_queuedSamples'),
      if (_message.isNotEmpty) Text(_message, style: TextStyle(color: Theme.of(context).colorScheme.primary)),
    ]))),
    Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Current recognition mode: $_mode', style: Theme.of(context).textTheme.titleSmall), const SizedBox(height: 6), const Text('Demo poses are geometry rules. AI Trained Mode only becomes available after real examples are collected and the model is trained on the local server.')]))),
  ]);

  Widget _statusPage() => ListView(padding: const EdgeInsets.all(14), children: [
    Text('Connection & privacy', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
    Card(child: ListTile(leading: Icon(_connection.startsWith('Connected') ? Icons.cloud_done : Icons.cloud_off), title: Text(_connection), subtitle: Text(_server.text), trailing: IconButton(onPressed: _editServer, icon: const Icon(Icons.edit)))),
    Card(child: ListTile(leading: const Icon(Icons.memory), title: Text(_mode), subtitle: const Text('MediaPipe hand tracking and rule geometry run on the local SignBridge computer for the mobile app.'))),
    Card(child: const Padding(padding: EdgeInsets.all(16), child: Text('Privacy: phone camera recognition starts only after you confirm. Individual frames are sent to the local server address for transient processing; the server does not save them. Landmark training samples require a separate consent step.'))),
    SwitchListTile(title: const Text('Dark appearance'), value: Theme.of(context).brightness == Brightness.dark, onChanged: widget.onThemeChanged),
    const SizedBox(height: 12),
    FilledButton.icon(onPressed: _checkServer, icon: const Icon(Icons.refresh), label: const Text('Check connection')),
  ]);

  @override
  Widget build(BuildContext context) {
    final pages = [_translatePage(), _vocabularyPage(), _trainingPage(), _statusPage()];
    return Scaffold(
      appBar: AppBar(title: const Text('SignBridge', style: TextStyle(fontWeight: FontWeight.w800)), actions: [Padding(padding: const EdgeInsets.symmetric(horizontal: 8), child: Center(child: Text(_connection.startsWith('Connected') ? '● Online' : '● Offline', style: const TextStyle(fontSize: 11)))), IconButton(tooltip: 'Connect to local server', onPressed: _editServer, icon: const Icon(Icons.settings_ethernet))]),
      body: SafeArea(child: pages[_tab]),
      bottomNavigationBar: NavigationBar(selectedIndex: _tab, onDestinationSelected: (value) => setState(() => _tab = value), destinations: const [NavigationDestination(icon: Icon(Icons.sign_language), label: 'Translate'), NavigationDestination(icon: Icon(Icons.menu_book), label: 'Vocabulary'), NavigationDestination(icon: Icon(Icons.school_outlined), label: 'Training'), NavigationDestination(icon: Icon(Icons.shield_outlined), label: 'Privacy')]),
    );
  }
}

class LandmarkPainter extends CustomPainter {
  // Landmarks come from the upright, unmirrored frame. The front-camera preview is shown mirrored,
  // so the overlay is mirrored only for the front camera.
  LandmarkPainter(this.points, {this.mirror = true});
  final List<Offset> points;
  final bool mirror;
  static const links = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length != 21) return;
    final line = Paint()..color = const Color(0xff69d9b5)..strokeWidth = 2..style = PaintingStyle.stroke;
    final dot = Paint()..color = const Color(0xfff2c66f)..style = PaintingStyle.fill;
    Offset map(Offset point) => Offset((mirror ? 1 - point.dx : point.dx) * size.width, point.dy * size.height);
    for (final link in links) canvas.drawLine(map(points[link[0]]), map(points[link[1]]), line);
    for (final point in points) canvas.drawCircle(map(point), 3.2, dot);
  }

  @override
  bool shouldRepaint(covariant LandmarkPainter oldDelegate) => oldDelegate.points != points || oldDelegate.mirror != mirror;
}
