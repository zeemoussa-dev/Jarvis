import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'services/jarvis_connection.dart';
import 'screens/jarvis_screen.dart';
import 'screens/media_screen.dart';
import 'screens/home_dash_screen.dart';
import 'screens/settings_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));
  final prefs = await SharedPreferences.getInstance();
  runApp(JarvisApp(prefs: prefs));
}

class JarvisApp extends StatelessWidget {
  final SharedPreferences prefs;
  const JarvisApp({super.key, required this.prefs});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'JARVIS',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00B4FF),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF080C14),
        fontFamily: 'monospace',
        useMaterial3: true,
      ),
      home: AppShell(prefs: prefs),
    );
  }
}

class AppShell extends StatefulWidget {
  final SharedPreferences prefs;
  const AppShell({super.key, required this.prefs});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late final JarvisConnection _connection;
  int _tab = 0;

  static const _accent = Color(0xFF00B4FF);

  @override
  void initState() {
    super.initState();
    _connection = JarvisConnection(prefs: widget.prefs);
    _connection.addListener(_rebuild);
    _connection.connect();
  }

  @override
  void dispose() {
    _connection.removeListener(_rebuild);
    _connection.dispose();
    super.dispose();
  }

  void _rebuild() => setState(() {});

  Color get _stateColor => switch (_connection.state) {
    JarvisState.idle         => _accent,
    JarvisState.listening    => const Color(0xFF00FF88),
    JarvisState.thinking     => const Color(0xFFFFAA00),
    JarvisState.speaking     => const Color(0xFF7B5BFB),
    JarvisState.disconnected => const Color(0xFF444444),
  };

  @override
  Widget build(BuildContext context) {
    final screens = [
      JarvisScreen(connection: _connection, stateColor: _stateColor),
      MediaScreen(connection: _connection),
      HomeDashScreen(connection: _connection),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF080C14),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0F1A),
        elevation: 0,
        title: Row(
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: 7,
              height: 7,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _connection.isConnected
                    ? const Color(0xFF00FF88)
                    : const Color(0xFFFF4444),
                boxShadow: _connection.isConnected
                    ? [BoxShadow(
                        color: const Color(0xFF00FF88).withOpacity(0.7),
                        blurRadius: 6,
                      )]
                    : null,
              ),
            ),
            const SizedBox(width: 10),
            Text(
              'J.A.R.V.I.S.',
              style: TextStyle(
                color: _stateColor,
                fontFamily: 'monospace',
                fontSize: 15,
                fontWeight: FontWeight.w700,
                letterSpacing: 4,
              ),
            ),
            const SizedBox(width: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                border: Border.all(color: _stateColor.withOpacity(0.3)),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                _connection.mood.toUpperCase(),
                style: TextStyle(
                  color: _stateColor.withOpacity(0.7),
                  fontSize: 9,
                  letterSpacing: 2,
                ),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined, size: 18),
            color: Colors.white38,
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => SettingsScreen(connection: _connection),
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_connection.apiVersionMismatch)
            Container(
              width: double.infinity,
              color: const Color(0xFFFF6600),
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
              child: const Text(
                'APP UPDATE REQUIRED — API version mismatch',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontFamily: 'monospace',
                  letterSpacing: 1,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          Expanded(
            child: IndexedStack(
              index: _tab,
              children: screens,
            ),
          ),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Color(0xFF0A0F1A),
          border: Border(top: BorderSide(color: Color(0xFF1A2535), width: 1)),
        ),
        child: NavigationBar(
          backgroundColor: Colors.transparent,
          indicatorColor: _accent.withOpacity(0.15),
          selectedIndex: _tab,
          onDestinationSelected: (i) => setState(() => _tab = i),
          labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
          destinations: [
            NavigationDestination(
              icon: Icon(Icons.hub_outlined,
                  color: _tab == 0 ? _accent : Colors.white24),
              selectedIcon: Icon(Icons.hub, color: _accent),
              label: 'JARVIS',
            ),
            NavigationDestination(
              icon: _MediaTabIcon(
                selected: _tab == 1,
                accent: _accent,
                connection: _connection,
              ),
              selectedIcon: Icon(Icons.movie, color: _accent),
              label: 'MEDIA',
            ),
            NavigationDestination(
              icon: Icon(Icons.home_outlined,
                  color: _tab == 2 ? _accent : Colors.white24),
              selectedIcon: Icon(Icons.home, color: _accent),
              label: 'HOME',
            ),
          ],
        ),
      ),
    );
  }
}

// Media tab icon — shows a pulsing dot when something is playing
class _MediaTabIcon extends StatelessWidget {
  final bool selected;
  final Color accent;
  final JarvisConnection connection;

  const _MediaTabIcon({
    required this.selected,
    required this.accent,
    required this.connection,
  });

  @override
  Widget build(BuildContext context) {
    final sessions = (connection.mediaData['plex']?['sessions'] as List?) ?? [];
    final isPlaying = sessions.isNotEmpty;

    return Stack(
      clipBehavior: Clip.none,
      children: [
        Icon(Icons.movie_outlined, color: selected ? accent : Colors.white24),
        if (isPlaying)
          Positioned(
            top: -2,
            right: -4,
            child: Container(
              width: 7,
              height: 7,
              decoration: BoxDecoration(
                color: const Color(0xFF00FF88),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF00FF88).withOpacity(0.6),
                    blurRadius: 4,
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
