import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

enum JarvisState { idle, listening, thinking, speaking, disconnected }

class JarvisMessage {
  final String role;
  final String text;
  JarvisMessage({required this.role, required this.text});
}

// The API version this mobile build expects — must match backend config.API_VERSION
const int _kExpectedApiVersion = 1;

class JarvisConnection extends ChangeNotifier {
  final SharedPreferences prefs;
  JarvisConnection({required this.prefs});

  // ── Core state ────────────────────────────────────────────────────────────
  JarvisState state    = JarvisState.disconnected;
  String mood          = 'personal';
  String activeUrl     = '';
  String activeHost    = '';
  String backendVersion = '';
  bool apiVersionMismatch = false;
  bool get isConnected => state != JarvisState.disconnected;

  // ── Chat ──────────────────────────────────────────────────────────────────
  final List<JarvisMessage> messages = [];
  String streamBuffer = '';
  bool isSendingCommand = false;

  // ── Media data ────────────────────────────────────────────────────────────
  Map<String, dynamic> mediaData = {};
  bool mediaLoading = false;

  // ── Home data ─────────────────────────────────────────────────────────────
  Map<String, dynamic> homeData = {};
  Map<String, dynamic> envData  = {};
  bool homeLoading = false;

  // ── Settings ──────────────────────────────────────────────────────────────
  static const _kLocalHost  = 'local_host';
  static const _kRemoteHost = 'remote_host';
  static const _kToken      = 'ws_token';

  String get localHost  => prefs.getString(_kLocalHost)  ?? '10.0.0.150';
  String get remoteHost => prefs.getString(_kRemoteHost) ?? '94.203.143.82';
  String get wsToken    => prefs.getString(_kToken)       ?? '';

  Future<void> saveSettings({
    required String local,
    required String remote,
    required String token,
  }) async {
    await prefs.setString(_kLocalHost,  local);
    await prefs.setString(_kRemoteHost, remote);
    await prefs.setString(_kToken,      token);
  }

  // ── Audio ─────────────────────────────────────────────────────────────────
  final AudioPlayer _audioPlayer = AudioPlayer();

  Future<void> _playAudioBytes(String base64Mp3) async {
    try {
      final bytes = base64Decode(base64Mp3);
      await _audioPlayer.stop();
      await _audioPlayer.play(BytesSource(bytes));
    } catch (e) {
      debugPrint('[JARVIS] Audio playback error: $e');
    }
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────
  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _reconnectTimer;
  Timer? _mediaTimer;
  Timer? _homeTimer;
  bool _disposed = false;

  Future<void> connect() async {
    _reconnectTimer?.cancel();
    await _sub?.cancel();
    _channel?.sink.close();

    final resolved = await _resolveHost();
    if (resolved == null) {
      _scheduleReconnect();
      return;
    }

    activeHost = resolved;
    final token = wsToken.isEmpty ? '' : '?token=$wsToken';
    activeUrl = 'ws://$resolved/ws$token';

    try {
      _channel = WebSocketChannel.connect(Uri.parse(activeUrl));
      _sub = _channel!.stream.listen(
        _onMessage,
        onError: (_) => _onDisconnect(),
        onDone: _onDisconnect,
      );
      debugPrint('[JARVIS] Connected to $activeUrl');

      // Check API version compatibility
      _checkApiVersion();

      // Start polling REST APIs
      _startPolling();
    } catch (e) {
      debugPrint('[JARVIS] WS connect failed: $e');
      _onDisconnect();
    }
  }

  Future<void> _checkApiVersion() async {
    try {
      final r = await http.get(Uri.parse('http://$activeHost/version'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final data = jsonDecode(r.body);
        backendVersion = data['version'] as String? ?? '';
        final apiVer = data['api_version'] as int? ?? 0;
        apiVersionMismatch = apiVer != _kExpectedApiVersion;
        if (apiVersionMismatch) {
          debugPrint('[JARVIS] API version mismatch: backend=$apiVer, expected=$_kExpectedApiVersion');
        }
        notifyListeners();
      }
    } catch (e) {
      debugPrint('[JARVIS] Version check error: $e');
    }
  }

  Future<String?> _resolveHost() async {
    final connectivity = await Connectivity().checkConnectivity();
    final isMobileData = connectivity.contains(ConnectivityResult.mobile) &&
        !connectivity.contains(ConnectivityResult.wifi);

    if (!isMobileData) {
      if (await _canReach(localHost, 8765)) return '$localHost:8765';
      debugPrint('[JARVIS] Local unreachable, trying remote...');
    }
    if (await _canReach(remoteHost, 8765)) return '$remoteHost:8765';
    debugPrint('[JARVIS] Both endpoints unreachable.');
    return null;
  }

  Future<bool> _canReach(String host, int port) async {
    try {
      final s = await Socket.connect(host, port, timeout: const Duration(seconds: 2));
      s.destroy();
      return true;
    } catch (_) {
      return false;
    }
  }

  void _onDisconnect() {
    if (_disposed) return;
    state = JarvisState.disconnected;
    activeUrl = '';
    activeHost = '';
    backendVersion = '';
    apiVersionMismatch = false;
    _mediaTimer?.cancel();
    _homeTimer?.cancel();
    notifyListeners();
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), connect);
  }

  // ── WebSocket message handler ─────────────────────────────────────────────
  void _onMessage(dynamic raw) {
    final Map<String, dynamic> msg;
    try { msg = jsonDecode(raw as String); } catch (_) { return; }

    final type = msg['type'] as String? ?? '';
    switch (type) {
      case 'state':
        final s = msg['state'] as String? ?? 'idle';
        state = switch (s) {
          'LISTENING' => JarvisState.listening,
          'THINKING'  => JarvisState.thinking,
          'SPEAKING'  => JarvisState.speaking,
          _           => JarvisState.idle,
        };

      case 'mood':
        mood = (msg['mood'] as String? ?? 'personal').toLowerCase();

      case 'sysinfo':
        final v = msg['version'] as String?;
        if (v != null) backendVersion = v;
        final apiVer = msg['api_version'] as int?;
        if (apiVer != null) {
          apiVersionMismatch = apiVer != _kExpectedApiVersion;
        }

      case 'text':
        final role = msg['role'] as String? ?? 'jarvis';
        final text = msg['text'] as String? ?? '';
        if (text.isNotEmpty) {
          if (streamBuffer.isNotEmpty) _commitStream();
          messages.add(JarvisMessage(role: role, text: text));
          if (messages.length > 100) messages.removeAt(0);
        }

      case 'stream_token':
        streamBuffer += (msg['text'] as String? ?? '');
    }

    notifyListeners();
  }

  void _commitStream() {
    if (streamBuffer.trim().isEmpty) return;
    messages.add(JarvisMessage(role: 'jarvis', text: streamBuffer.trim()));
    if (messages.length > 100) messages.removeAt(0);
    streamBuffer = '';
  }

  // ── REST polling ──────────────────────────────────────────────────────────
  void _startPolling() {
    fetchMedia();
    fetchHome();

    _mediaTimer?.cancel();
    _homeTimer?.cancel();

    _mediaTimer = Timer.periodic(const Duration(seconds: 20), (_) => fetchMedia());
    _homeTimer  = Timer.periodic(const Duration(seconds: 10), (_) => fetchHome());
  }

  String _url(String path) {
    final base = 'http://$activeHost$path';
    return wsToken.isEmpty ? base : '$base?token=$wsToken';
  }

  Future<void> fetchMedia() async {
    if (activeHost.isEmpty) return;
    mediaLoading = true;
    notifyListeners();
    try {
      final r = await http.get(Uri.parse(_url('/api/media')))
          .timeout(const Duration(seconds: 15));
      if (r.statusCode == 200) {
        mediaData = jsonDecode(r.body);
      }
    } catch (e) {
      debugPrint('[JARVIS] fetchMedia error: $e');
    }
    mediaLoading = false;
    notifyListeners();
  }

  Future<void> fetchHome() async {
    if (activeHost.isEmpty) return;
    homeLoading = true;
    notifyListeners();
    try {
      final homeR = await http.get(Uri.parse(_url('/api/home')))
          .timeout(const Duration(seconds: 10));
      final envR  = await http.get(Uri.parse(_url('/api/environment')))
          .timeout(const Duration(seconds: 15));

      if (homeR.statusCode == 200) homeData = jsonDecode(homeR.body);
      if (envR.statusCode  == 200) envData  = jsonDecode(envR.body);
    } catch (e) {
      debugPrint('[JARVIS] fetchHome error: $e');
    }
    homeLoading = false;
    notifyListeners();
  }

  // ── Send text command ─────────────────────────────────────────────────────
  Future<void> sendTextCommand(String text) async {
    if (text.trim().isEmpty || activeHost.isEmpty) return;

    messages.add(JarvisMessage(role: 'user', text: text.trim()));
    isSendingCommand = true;
    notifyListeners();

    try {
      final r = await http.post(
        Uri.parse(_url('/api/command')),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'text': text.trim()}),
      ).timeout(const Duration(seconds: 60));

      if (r.statusCode == 200) {
        final data = jsonDecode(r.body);
        // Add JARVIS response to chat immediately (WebSocket may lag)
        final responseText = data['response'] as String? ?? '';
        if (responseText.isNotEmpty) {
          // Only add if not already received via WebSocket broadcast
          final alreadyAdded = messages.isNotEmpty &&
              messages.last.role == 'jarvis' &&
              messages.last.text == responseText;
          if (!alreadyAdded) {
            messages.add(JarvisMessage(role: 'jarvis', text: responseText));
            if (messages.length > 100) messages.removeAt(0);
          }
        }
        final audioB64 = data['audio_b64'] as String? ?? '';
        if (audioB64.isNotEmpty) {
          await _playAudioBytes(audioB64);
        }
      }
    } catch (e) {
      debugPrint('[JARVIS] sendTextCommand error: $e');
    }

    isSendingCommand = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _mediaTimer?.cancel();
    _homeTimer?.cancel();
    _sub?.cancel();
    _channel?.sink.close();
    _audioPlayer.dispose();
    super.dispose();
  }
}
