import 'dart:math' as math;
import 'dart:ui' show FontFeature, PointMode;

import 'package:flutter/material.dart';

import '../../theme/cyberforge_theme.dart';

final class GammaSimstationDisplay extends StatefulWidget {
  const GammaSimstationDisplay({
    required this.coherence,
    required this.worlds,
    required this.active,
    super.key,
  });

  final double coherence;
  final int worlds;
  final bool active;

  @override
  State<GammaSimstationDisplay> createState() => _GammaSimstationDisplayState();
}

final class _GammaSimstationDisplayState extends State<GammaSimstationDisplay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 13),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 1.42,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: DecoratedBox(
          decoration: const BoxDecoration(
            gradient: RadialGradient(
              center: Alignment(0.1, -0.16),
              radius: 1.15,
              colors: <Color>[Color(0xFF17264B), Color(0xFF060A13)],
            ),
          ),
          child: Stack(
            children: <Widget>[
              Positioned.fill(
                child: AnimatedBuilder(
                  animation: _controller,
                  builder: (BuildContext context, Widget? child) => CustomPaint(
                    painter: _GammaPainter(
                      phase: _controller.value,
                      coherence: widget.coherence,
                      active: widget.active,
                    ),
                  ),
                ),
              ),
              Positioned(
                left: 18,
                top: 16,
                child: _StatusBadge(active: widget.active),
              ),
              Positioned(
                left: 20,
                right: 20,
                bottom: 18,
                child: Row(
                  children: <Widget>[
                    Expanded(
                      child: _TelemetryValue(
                        label: 'SIMULATED REGISTER',
                        value: '81,611,511',
                      ),
                    ),
                    Expanded(
                      child: _TelemetryValue(
                        label: 'COHERENCE',
                        value:
                            '${(widget.coherence * 100).toStringAsFixed(3)}%',
                      ),
                    ),
                    Expanded(
                      child: _TelemetryValue(
                        label: 'WORLDS',
                        value: _compact(widget.worlds),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _compact(int value) {
    if (value >= 1000000) return '${(value / 1000000).toStringAsFixed(1)}M';
    if (value >= 1000) return '${(value / 1000).toStringAsFixed(1)}K';
    return value.toString();
  }
}

final class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.active});
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
      decoration: BoxDecoration(
        color: const Color(0xC40A1020),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: active ? CyberForgeColors.green : CyberForgeColors.grid,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: active ? CyberForgeColors.green : CyberForgeColors.muted,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            active ? 'GAMMA FABRIC ACTIVE' : 'GAMMA FABRIC STANDBY',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              fontWeight: FontWeight.w900,
              letterSpacing: 1.1,
            ),
          ),
        ],
      ),
    );
  }
}

final class _TelemetryValue extends StatelessWidget {
  const _TelemetryValue({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: CyberForgeColors.muted,
            letterSpacing: 1,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          value,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            color: CyberForgeColors.cyan,
            fontWeight: FontWeight.w800,
            fontFeatures: const <FontFeature>[FontFeature.tabularFigures()],
          ),
        ),
      ],
    );
  }
}

final class _GammaPainter extends CustomPainter {
  const _GammaPainter({
    required this.phase,
    required this.coherence,
    required this.active,
  });

  final double phase;
  final double coherence;
  final bool active;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width * 0.53, size.height * 0.44);
    final baseRadius = math.min(size.width, size.height) * 0.18;
    final grid = Paint()
      ..color = CyberForgeColors.grid.withValues(alpha: 0.36)
      ..strokeWidth = 0.7;
    for (double x = 0; x < size.width; x += 27) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
    }
    for (double y = 0; y < size.height; y += 27) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }

    for (var ring = 0; ring < 5; ring++) {
      final radius = baseRadius * (1 + ring * 0.34);
      final paint = Paint()
        ..color =
            (ring.isEven ? CyberForgeColors.cyan : CyberForgeColors.violet)
                .withValues(alpha: active ? 0.26 : 0.10)
        ..style = PaintingStyle.stroke
        ..strokeWidth = ring == 0 ? 2.2 : 1.15;
      final rect = Rect.fromCenter(
        center: center,
        width: radius * 2.1,
        height: radius * (0.88 + ring * 0.035),
      );
      canvas.save();
      canvas.translate(center.dx, center.dy);
      canvas.rotate(phase * (2 * math.pi) * (ring.isEven ? 1 : -0.62) + ring);
      canvas.translate(-center.dx, -center.dy);
      canvas.drawOval(rect, paint);
      canvas.restore();
    }

    final core = Paint()
      ..shader =
          RadialGradient(
            colors: <Color>[
              CyberForgeColors.text.withValues(alpha: 0.96),
              CyberForgeColors.cyan.withValues(alpha: 0.68),
              CyberForgeColors.blue.withValues(alpha: 0.1),
              Colors.transparent,
            ],
          ).createShader(
            Rect.fromCircle(center: center, radius: baseRadius * 1.25),
          );
    canvas.drawCircle(center, baseRadius * 1.25, core);

    final particlePaint = Paint()..strokeCap = StrokeCap.round;
    for (var index = 0; index < 92; index++) {
      final seed = index * 0.6180339887 + phase;
      final angle = seed * (2 * math.pi);
      final radius = baseRadius * (1.1 + (index % 13) / 5.4);
      final wobble = math.sin(phase * (2 * math.pi) * 2 + index) * 4;
      final point = Offset(
        center.dx + math.cos(angle) * (radius + wobble),
        center.dy + math.sin(angle) * (radius * 0.48 + wobble),
      );
      particlePaint
        ..color =
            (index % 3 == 0 ? CyberForgeColors.violet : CyberForgeColors.cyan)
                .withValues(alpha: active ? 0.58 : 0.18)
        ..strokeWidth = index % 9 == 0 ? 2.4 : 1.1;
      canvas.drawPoints(PointMode.points, <Offset>[point], particlePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _GammaPainter oldDelegate) =>
      phase != oldDelegate.phase ||
      coherence != oldDelegate.coherence ||
      active != oldDelegate.active;
}
