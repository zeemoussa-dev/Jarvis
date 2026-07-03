import 'package:flutter/material.dart';

import '../services/jarvis_connection.dart';
import '../widgets/state_orb.dart';
import '../widgets/chat_feed.dart';
import '../widgets/ptt_button.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  final JarvisConnection connection;
  const HomeScreen({super.key, required this.connection});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  JarvisConnection get _c => widget.connection;

  @override
  void initState() {
    super.initState();
    _c.addListener(_rebuild);
  }

  @override
  void dispose() {
    _c.removeListener(_rebuild);
    super.dispose();
  }

  void _rebuild() => setState(() {});

  Color get _accentColor {
    return switch (_c.state) {
      JarvisState.idle        => const Color(0xFF00B4FF),
      JarvisState.listening   => const Color(0xFF00FF88),
      JarvisState.thinking    => const Color(0xFFFFAA00),
      JarvisState.speaking    => const Color(0xFF7B5BFB),
      JarvisState.disconnected => const Color(0xFF444444),
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF080C14),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: Row(
          children: [
            // Connection indicator dot
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _c.isConnected ? const Color(0xFF00FF88) : const Color(0xFFFF4444),
                boxShadow: _c.isConnected
                    ? [BoxShadow(color: const Color(0xFF00FF88).withOpacity(0.6), blurRadius: 6)]
                    : null,
              ),
            ),
            const SizedBox(width: 10),
            Text(
              'J.A.R.V.I.S.',
              style: TextStyle(
                color: _accentColor,
                fontFamily: 'monospace',
                fontSize: 16,
                fontWeight: FontWeight.w700,
                letterSpacing: 4,
              ),
            ),
          ],
        ),
        actions: [
          // Mood badge
          Container(
            margin: const EdgeInsets.only(right: 8),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              border: Border.all(color: _accentColor.withOpacity(0.4)),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              _c.mood.toUpperCase(),
              style: TextStyle(
                color: _accentColor.withOpacity(0.8),
                fontSize: 10,
                letterSpacing: 2,
                fontFamily: 'monospace',
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined, size: 20),
            color: Colors.white38,
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => SettingsScreen(connection: _c),
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // State orb
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: StateOrb(state: _c.state, color: _accentColor),
          ),

          // Connection URL hint
          if (!_c.isConnected)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(
                'Connecting...',
                style: TextStyle(
                  color: Colors.white24,
                  fontSize: 11,
                  fontFamily: 'monospace',
                  letterSpacing: 1,
                ),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                _c.activeUrl.replaceAll(RegExp(r'\?token=.*'), ''),
                style: const TextStyle(
                  color: Colors.white24,
                  fontSize: 10,
                  fontFamily: 'monospace',
                ),
              ),
            ),

          // Chat feed
          Expanded(
            child: ChatFeed(
              connection: _c,
              accentColor: _accentColor,
            ),
          ),

          // Push-to-talk button
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 40),
            child: PttButton(
              connection: _c,
              accentColor: _accentColor,
            ),
          ),
        ],
      ),
    );
  }
}
