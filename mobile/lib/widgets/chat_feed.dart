import 'package:flutter/material.dart';
import '../services/jarvis_connection.dart';

class ChatFeed extends StatefulWidget {
  final JarvisConnection connection;
  final Color accentColor;

  const ChatFeed({
    super.key,
    required this.connection,
    required this.accentColor,
  });

  @override
  State<ChatFeed> createState() => _ChatFeedState();
}

class _ChatFeedState extends State<ChatFeed> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    widget.connection.addListener(_onUpdate);
  }

  @override
  void dispose() {
    widget.connection.removeListener(_onUpdate);
    _scroll.dispose();
    super.dispose();
  }

  void _onUpdate() {
    setState(() {});
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.connection;
    final msgs = c.messages;
    final streaming = c.state == JarvisState.speaking && c.streamBuffer.isNotEmpty;
    final thinking = c.isSendingCommand;
    final extras = (streaming ? 1 : 0) + (thinking && !streaming ? 1 : 0);

    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: msgs.length + extras,
      itemBuilder: (_, i) {
        // Live streaming bubble at the bottom
        if (streaming && i == msgs.length) {
          return _Bubble(
            role: 'jarvis',
            text: c.streamBuffer,
            accentColor: widget.accentColor,
            isStreaming: true,
          );
        }
        // Thinking indicator while waiting for response
        if (thinking && !streaming && i == msgs.length) {
          return _ThinkingBubble(accentColor: widget.accentColor);
        }
        final m = msgs[i];
        return _Bubble(
          role: m.role,
          text: m.text,
          accentColor: widget.accentColor,
        );
      },
    );
  }
}

class _Bubble extends StatelessWidget {
  final String role;
  final String text;
  final Color accentColor;
  final bool isStreaming;

  const _Bubble({
    required this.role,
    required this.text,
    required this.accentColor,
    this.isStreaming = false,
  });

  bool get _isUser => role == 'user';

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisAlignment:
            _isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!_isUser) ...[
            CircleAvatar(
              radius: 12,
              backgroundColor: accentColor.withOpacity(0.15),
              child: Text(
                'J',
                style: TextStyle(
                  color: accentColor,
                  fontSize: 10,
                  fontFamily: 'monospace',
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: _isUser
                    ? accentColor.withOpacity(0.12)
                    : const Color(0xFF0D1520),
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(_isUser ? 16 : 4),
                  topRight: Radius.circular(_isUser ? 4 : 16),
                  bottomLeft: const Radius.circular(16),
                  bottomRight: const Radius.circular(16),
                ),
                border: Border.all(
                  color: _isUser
                      ? accentColor.withOpacity(0.3)
                      : Colors.white.withOpacity(0.06),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Flexible(
                    child: Text(
                      text,
                      style: TextStyle(
                        color: _isUser ? Colors.white70 : Colors.white,
                        fontSize: 13,
                        height: 1.5,
                        fontFamily: _isUser ? null : 'monospace',
                      ),
                    ),
                  ),
                  if (isStreaming) ...[
                    const SizedBox(width: 6),
                    _BlinkingCursor(color: accentColor),
                  ],
                ],
              ),
            ),
          ),
          if (_isUser) ...[
            const SizedBox(width: 8),
            const CircleAvatar(
              radius: 12,
              backgroundColor: Color(0xFF1A2030),
              child: Text(
                'S',
                style: TextStyle(
                  color: Colors.white38,
                  fontSize: 10,
                  fontFamily: 'monospace',
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _ThinkingBubble extends StatefulWidget {
  final Color accentColor;
  const _ThinkingBubble({required this.accentColor});
  @override
  State<_ThinkingBubble> createState() => _ThinkingBubbleState();
}

class _ThinkingBubbleState extends State<_ThinkingBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 12,
            backgroundColor: widget.accentColor.withOpacity(0.15),
            child: Text('J', style: TextStyle(color: widget.accentColor, fontSize: 10, fontFamily: 'monospace', fontWeight: FontWeight.bold)),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF0D1520),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4), topRight: Radius.circular(16),
                bottomLeft: Radius.circular(16), bottomRight: Radius.circular(16),
              ),
              border: Border.all(color: Colors.white.withOpacity(0.06)),
            ),
            child: AnimatedBuilder(
              animation: _ctrl,
              builder: (_, __) => Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(3, (i) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Opacity(
                    opacity: (_ctrl.value - i * 0.2).clamp(0.2, 1.0),
                    child: Container(width: 5, height: 5,
                      decoration: BoxDecoration(color: widget.accentColor, shape: BoxShape.circle)),
                  ),
                )),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BlinkingCursor extends StatefulWidget {
  final Color color;
  const _BlinkingCursor({required this.color});

  @override
  State<_BlinkingCursor> createState() => _BlinkingCursorState();
}

class _BlinkingCursorState extends State<_BlinkingCursor>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => Opacity(
        opacity: _ctrl.value,
        child: Container(
          width: 2,
          height: 14,
          color: widget.color,
        ),
      ),
    );
  }
}
