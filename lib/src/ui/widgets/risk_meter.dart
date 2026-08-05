import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../theme/cyberforge_theme.dart';

final class RiskMeter extends StatelessWidget {
  const RiskMeter({
    required this.value,
    required this.label,
    super.key,
    this.size = 156,
  });

  final double value;
  final String label;
  final double size;

  @override
  Widget build(BuildContext context) {
    final percent = (value.clamp(0.0, 1.0).toDouble() * 100).round();
    return SizedBox.square(
      dimension: size,
      child: Stack(
        alignment: Alignment.center,
        children: <Widget>[
          CustomPaint(
            size: Size.square(size),
            painter: _RiskMeterPainter(value: value),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                '$percent',
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                      fontSize: 38,
                      color: CyberForgeColors.text,
                    ),
              ),
              Text(
                label.toUpperCase(),
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: CyberForgeColors.muted,
                      letterSpacing: 1.4,
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

final class _RiskMeterPainter extends CustomPainter {
  const _RiskMeterPainter({required this.value});
  final double value;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = math.min(size.width, size.height) / 2 - 10;
    final rect = Rect.fromCircle(center: center, radius: radius);
    const start = math.pi * 0.75;
    const sweep = math.pi * 1.5;
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..strokeCap = StrokeCap.round
      ..color = CyberForgeColors.grid;
    canvas.drawArc(rect, start, sweep, false, track);
    final gradient = SweepGradient(
      startAngle: start,
      endAngle: start + sweep,
      colors: const <Color>[
        CyberForgeColors.green,
        CyberForgeColors.amber,
        CyberForgeColors.red,
      ],
      stops: const <double>[0, 0.58, 1],
      transform: const GradientRotation(start),
    );
    final active = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..strokeCap = StrokeCap.round
      ..shader = gradient.createShader(rect);
    canvas.drawArc(
      rect,
      start,
      sweep * value.clamp(0.0, 1.0).toDouble(),
      false,
      active,
    );
  }

  @override
  bool shouldRepaint(covariant _RiskMeterPainter oldDelegate) =>
      oldDelegate.value != value;
}
