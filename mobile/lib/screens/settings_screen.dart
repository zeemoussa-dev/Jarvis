import 'package:flutter/material.dart';
import '../services/jarvis_connection.dart';

class SettingsScreen extends StatefulWidget {
  final JarvisConnection connection;
  const SettingsScreen({super.key, required this.connection});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _localCtrl;
  late final TextEditingController _remoteCtrl;
  late final TextEditingController _tokenCtrl;

  @override
  void initState() {
    super.initState();
    _localCtrl  = TextEditingController(text: widget.connection.localHost);
    _remoteCtrl = TextEditingController(text: widget.connection.remoteHost);
    _tokenCtrl  = TextEditingController(text: widget.connection.wsToken);
  }

  @override
  void dispose() {
    _localCtrl.dispose();
    _remoteCtrl.dispose();
    _tokenCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await widget.connection.saveSettings(
      local:  _localCtrl.text.trim(),
      remote: _remoteCtrl.text.trim(),
      token:  _tokenCtrl.text.trim(),
    );
    await widget.connection.connect();
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    const accent = Color(0xFF00B4FF);
    const bg     = Color(0xFF080C14);
    const card   = Color(0xFF0D1520);

    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: const Text(
          'SETTINGS',
          style: TextStyle(
            fontFamily: 'monospace',
            letterSpacing: 4,
            fontSize: 14,
            color: accent,
          ),
        ),
        iconTheme: const IconThemeData(color: Colors.white38),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _section('CONNECTION'),
          _field(
            controller: _localCtrl,
            label: 'Local IP (home WiFi)',
            hint: '10.0.0.150',
            icon: Icons.home_outlined,
          ),
          const SizedBox(height: 12),
          _field(
            controller: _remoteCtrl,
            label: 'Remote IP (away)',
            hint: '94.203.143.82',
            icon: Icons.public_outlined,
          ),
          const SizedBox(height: 12),
          _field(
            controller: _tokenCtrl,
            label: 'Auth Token',
            hint: 'WS_TOKEN from .env',
            icon: Icons.key_outlined,
            obscure: true,
          ),
          const SizedBox(height: 8),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 4),
            child: Text(
              'The app tries local first, falls back to remote automatically.',
              style: TextStyle(color: Colors.white24, fontSize: 11, fontFamily: 'monospace'),
            ),
          ),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: accent,
                foregroundColor: bg,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: _save,
              child: const Text(
                'SAVE & RECONNECT',
                style: TextStyle(fontFamily: 'monospace', letterSpacing: 2, fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _section(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16, top: 8),
      child: Text(
        title,
        style: const TextStyle(
          color: Color(0xFF00B4FF),
          fontFamily: 'monospace',
          letterSpacing: 3,
          fontSize: 11,
        ),
      ),
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    bool obscure = false,
  }) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      style: const TextStyle(color: Colors.white70, fontFamily: 'monospace', fontSize: 13),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, color: Colors.white24, size: 18),
        labelStyle: const TextStyle(color: Colors.white38, fontSize: 12, fontFamily: 'monospace'),
        hintStyle: const TextStyle(color: Colors.white12, fontSize: 12),
        filled: true,
        fillColor: const Color(0xFF0D1520),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Colors.white12),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Colors.white12),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFF00B4FF), width: 1.5),
        ),
      ),
    );
  }
}
