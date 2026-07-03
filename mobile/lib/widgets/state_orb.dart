import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../services/jarvis_connection.dart';

class StateOrb extends StatelessWidget {
  final JarvisState state;
  final Color color;

  const StateOrb({super.key, required this.state, required this.color});

  String get _label => switch (state) {
    JarvisState.idle         => 'READY',
    JarvisState.listening    => 'LISTENING',
    JarvisState.thinking     => 'THINKING',
    JarvisState.speaking     => 'SPEAKING',
    JarvisState.disconnected => 'OFFLINE',
  };

  @override
  Widget build(BuildContext context) {
    final bool pulse =
        state == JarvisState.listening || state == JarvisState.speaking;
    final bool spin = state == JarvisState.thinking;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 120,
          height: 120,
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Outer glow ring
              Container(
                width: 120,
                height: 120,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: color.withOpacity(0.15),
                      blurRadius: 40,
                      spreadRadius: 10,
                    ),
                  ],
                ),
              )
              .animate(onPlay: (c) => c.repeat())
              .scaleXY(
                begin: 1.0,
                end: pulse ? 1.15 : 1.0,
                duration: 900.ms,
                curve: Curves.easeInOut,
              )
              .then()
              .scaleXY(
                begin: 1.15,
                end: 1.0,
                duration: 900.ms,
                curve: Curves.easeInOut,
              ),

              // Rotating ring (thinking)
              if (spin)
                _SpinningRing(color: color),

              // Core orb
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      color.withOpacity(0.9),
                      color.withOpacity(0.3),
                      Colors.transparent,
                    ],
                    stops: const [0.0, 0.5, 1.0],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: color.withOpacity(0.5),
                      blurRadius: 20,
                      spreadRadius: 2,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Text(
          _label,
          style: TextStyle(
            color: color,
            fontFamily: 'monospace',
            fontSize: 11,
            letterSpacing: 4,
          ),
        ),
      ],
    );
  }
}

class _SpinningRing extends StatefulWidget {
  final Color color;
  const _SpinningRing({required this.color});

  @override
  State<_SpinningRing> createState() => _SpinningRingState();
}

class _SpinningRingState extends State<_SpinningRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();
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
      builder: (_, __) => Transform.rotate(
        angle: _ctrl.value * 2 * pi,
        child: CustomPaint(
          size: const Size(110, 110),
          painter: _ArcPainter(color: widget.color),
        ),
      ),
    );
  }
}

class _ArcPainter extends CustomPainter {
  final Color color;
  const _ArcPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withOpacity(0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;

    final rect = Rect.fromLTWH(0, 0, size.width, size.height);
    canvas.drawArc(rect, 0, pi * 1.2, false, paint);
  }

  @override
  bool shouldRepaint(_ArcPainter old) => old.color != color;
}
