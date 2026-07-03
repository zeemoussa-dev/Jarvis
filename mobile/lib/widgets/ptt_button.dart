import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../services/jarvis_connection.dart';

class PttButton extends StatefulWidget {
  final JarvisConnection connection;
  final Color accentColor;
  final bool compact;

  const PttButton({
    super.key,
    required this.connection,
    required this.accentColor,
    this.compact = false,
  });

  @override
  State<PttButton> createState() => _PttButtonState();
}

class _PttButtonState extends State<PttButton> with SingleTickerProviderStateMixin {
  final SpeechToText _stt = SpeechToText();
  bool _initialized = false;
  bool _listening = false;
  bool _sending = false;
  String _partial = '';
  late AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    )..repeat(reverse: true);
    _init();
  }

  Future<void> _init() async {
    _initialized = await _stt.initialize(onError: (e) => debugPrint('[PTT] STT error: $e'));
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _pulse.dispose();
    _stt.cancel();
    super.dispose();
  }

  Future<void> _startListening() async {
    if (!_initialized || _sending) return;
    await _stt.listen(
      onResult: (result) {
        setState(() => _partial = result.recognizedWords);
        if (result.finalResult && result.recognizedWords.trim().isNotEmpty) {
          _sendResult(result.recognizedWords.trim());
        }
      },
      listenMode: ListenMode.dictation,
      pauseFor: const Duration(seconds: 2),
      localeId: 'en_US',
      onSoundLevelChange: null,
    );
    setState(() { _listening = true; _partial = ''; });
  }

  Future<void> _stopListening() async {
    await _stt.stop();
    setState(() => _listening = false);
  }

  Future<void> _sendResult(String text) async {
    await _stt.stop();
    setState(() { _listening = false; _sending = true; _partial = ''; });
    await widget.connection.sendTextCommand(text);
    if (mounted) setState(() => _sending = false);
  }

  void _toggleListening() {
    if (_sending) return;
    if (_listening) {
      _stopListening();
    } else {
      _startListening();
    }
  }

  @override
  Widget build(BuildContext context) {
    final ready = _initialized && !_sending;

    if (widget.compact) {
      return GestureDetector(
        onTap: ready ? _toggleListening : null,
        child: AnimatedBuilder(
          animation: _pulse,
          builder: (_, __) => Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _listening
                  ? Color.lerp(
                      widget.accentColor.withOpacity(0.35),
                      widget.accentColor.withOpacity(0.15),
                      _pulse.value,
                    )
                  : Colors.white.withAlpha(12),
              border: Border.all(
                color: _listening ? widget.accentColor : Colors.white12,
                width: _listening ? 1.5 : 1,
              ),
            ),
            child: _sending
                ? Padding(
                    padding: const EdgeInsets.all(12),
                    child: CircularProgressIndicator(
                        strokeWidth: 1.5, color: widget.accentColor),
                  )
                : Icon(
                    _listening ? Icons.stop_rounded : Icons.mic_outlined,
                    color: _listening ? widget.accentColor : Colors.white38,
                    size: 20,
                  ),
          ),
        ),
      );
    }

    // Full-size push-to-talk
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (_listening && _partial.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              _partial,
              style: const TextStyle(color: Colors.white54, fontSize: 13, fontFamily: 'monospace'),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        GestureDetector(
          onTap: ready ? _toggleListening : null,
          child: AnimatedBuilder(
            animation: _pulse,
            builder: (_, __) => Container(
              width: double.infinity,
              height: 56,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(28),
                border: Border.all(
                  color: _listening ? widget.accentColor : Colors.white12,
                  width: _listening ? 1.5 : 1,
                ),
                color: _listening
                    ? Color.lerp(
                        widget.accentColor.withOpacity(0.25),
                        widget.accentColor.withOpacity(0.08),
                        _pulse.value,
                      )
                    : Colors.white.withAlpha(8),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (_sending)
                    SizedBox(
                      width: 16, height: 16,
                      child: CircularProgressIndicator(
                          strokeWidth: 1.5, color: widget.accentColor),
                    )
                  else
                    Icon(
                      _listening ? Icons.stop_rounded : Icons.mic_outlined,
                      color: _listening ? widget.accentColor : Colors.white38,
                      size: 20,
                    ),
                  const SizedBox(width: 10),
                  Text(
                    _sending
                        ? 'PROCESSING...'
                        : !_initialized
                            ? 'MICROPHONE UNAVAILABLE'
                            : _listening
                                ? 'LISTENING...'
                                : 'TAP TO SPEAK',
                    style: TextStyle(
                      color: _listening ? widget.accentColor : Colors.white38,
                      fontFamily: 'monospace',
                      fontSize: 11,
                      letterSpacing: 2,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
