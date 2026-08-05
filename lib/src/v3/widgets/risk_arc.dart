import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../theme/cyberforge_theme.dart';

final class RiskArc extends StatelessWidget {
  const RiskArc({
    required this.value,
    this.size = 178,
    this.label = 'MODELED RISK',
    super.key,
  });

  final double value;
  final double size;
  final String label;

  @override
  Widget build(BuildContext context) {
    final normalized = value.clamp(0.0, 1.0).toDouble();
    return SizedBox.square(
      dimension: size,
      child: CustomPaint(
        painter: _RiskArcPainter(normalized),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                '${(normalized * 100).round()}',
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                  color: CyberForgeColors.text,
                  fontWeight: FontWeight.w900,
                  letterSpacing: -2,
                ),
              ),
              Text(
                label,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: CyberForgeColors.muted,
                  letterSpacing: 1.4,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

final class _RiskArcPainter extends CustomPainter {
  const _RiskArcPainter(this.value);
  final double value;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 13;
    final rect = Rect.fromCircle(center: center, radius: radius);
    const start = math.pi * 0.76;
    const sweep = math.pi * 1.48;
    final background = Paint()
      ..color = CyberForgeColors.grid
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, start, sweep, false, background);
    final foreground = Paint()
      ..shader = const SweepGradient(
        colors: <Color>[
          CyberForgeColors.green,
          CyberForgeColors.cyan,
          CyberForgeColors.amber,
          CyberForgeColors.red,
        ],
        stops: <double>[0, 0.44, 0.72, 1],
        transform: GradientRotation(start),
      ).createShader(rect)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, start, sweep * value, false, foreground);
    final glow = Paint()
      ..color = CyberForgeColors.cyan.withValues(alpha: 0.13)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 22
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 14);
    canvas.drawArc(rect, start, sweep * value, false, glow);
  }

  @override
  bool shouldRepaint(covariant _RiskArcPainter oldDelegate) => oldDelegate.value != value;
}
