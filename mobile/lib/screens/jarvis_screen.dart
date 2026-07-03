import 'package:flutter/material.dart';
import '../services/jarvis_connection.dart';
import '../widgets/state_orb.dart';
import '../widgets/chat_feed.dart';
import '../widgets/ptt_button.dart';

class JarvisScreen extends StatefulWidget {
  final JarvisConnection connection;
  final Color stateColor;

  const JarvisScreen({
    super.key,
    required this.connection,
    required this.stateColor,
  });

  @override
  State<JarvisScreen> createState() => _JarvisScreenState();
}

class _JarvisScreenState extends State<JarvisScreen> {
  final _textCtrl = TextEditingController();
  final _focusNode = FocusNode();
  bool _typing = false;

  JarvisConnection get _c => widget.connection;

  @override
  void dispose() {
    _textCtrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _send() {
    final text = _textCtrl.text.trim();
    if (text.isEmpty) return;
    _c.sendTextCommand(text);
    _textCtrl.clear();
    _focusNode.unfocus();
    setState(() => _typing = false);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // State orb — collapses when keyboard is up
        AnimatedSize(
          duration: const Duration(milliseconds: 200),
          child: _typing
              ? const SizedBox.shrink()
              : Padding(
                  padding: const EdgeInsets.fromLTRB(0, 20, 0, 4),
                  child: StateOrb(
                    state: _c.state,
                    color: widget.stateColor,
                  ),
                ),
        ),

        // Chat feed
        Expanded(
          child: ChatFeed(
            connection: _c,
            accentColor: widget.stateColor,
          ),
        ),

        // Input area
        _InputBar(
          controller: _textCtrl,
          focusNode: _focusNode,
          connection: _c,
          accentColor: widget.stateColor,
          onTyping: (v) => setState(() => _typing = v),
          onSend: _send,
        ),
      ],
    );
  }
}

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final JarvisConnection connection;
  final Color accentColor;
  final ValueChanged<bool> onTyping;
  final VoidCallback onSend;

  const _InputBar({
    required this.controller,
    required this.focusNode,
    required this.connection,
    required this.accentColor,
    required this.onTyping,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.fromLTRB(
        16,
        8,
        16,
        MediaQuery.of(context).padding.bottom + 12,
      ),
      decoration: const BoxDecoration(
        color: Color(0xFF0A0F1A),
        border: Border(top: BorderSide(color: Color(0xFF1A2535))),
      ),
      child: Row(
        children: [
          // PTT button
          PttButton(
            connection: connection,
            accentColor: accentColor,
            compact: true,
          ),

          const SizedBox(width: 10),

          // Text field
          Expanded(
            child: Container(
              height: 44,
              decoration: BoxDecoration(
                color: const Color(0xFF0D1520),
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: const Color(0xFF1A2535)),
              ),
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontFamily: 'monospace',
                ),
                decoration: InputDecoration(
                  hintText: connection.isConnected
                      ? 'Type a command...'
                      : 'Connecting...',
                  hintStyle: const TextStyle(
                    color: Colors.white24,
                    fontSize: 13,
                    fontFamily: 'monospace',
                  ),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                ),
                onChanged: (v) => onTyping(v.isNotEmpty),
                onSubmitted: (_) => onSend(),
                textInputAction: TextInputAction.send,
                enabled: connection.isConnected,
              ),
            ),
          ),

          const SizedBox(width: 8),

          // Send button
          GestureDetector(
            onTap: onSend,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: accentColor.withOpacity(0.15),
                border: Border.all(color: accentColor.withOpacity(0.4)),
              ),
              child: Icon(
                Icons.send_rounded,
                color: accentColor,
                size: 18,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
