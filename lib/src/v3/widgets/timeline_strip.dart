import 'package:flutter/material.dart';

import '../../theme/cyberforge_theme.dart';

final class TimelineStrip extends StatelessWidget {
  const TimelineStrip({required this.timeline, super.key});
  final List<Map<String, dynamic>> timeline;

  @override
  Widget build(BuildContext context) {
    final values = List<double>.generate(24, (int index) {
      final match = timeline.where(
        (Map<String, dynamic> item) => (item['hour'] as num?)?.toInt() == index,
      );
      if (match.isEmpty) return 0;
      final value = match.first['pressure'];
      return value is num ? value.toDouble().clamp(0.0, 1.0).toDouble() : 0.0;
    });
    return SizedBox(
      height: 148,
      child: CustomPaint(
        painter: _TimelinePainter(values),
        child: const SizedBox.expand(),
      ),
    );
  }
}

final class _TimelinePainter extends CustomPainter {
  const _TimelinePainter(this.values);
  final List<double> values;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 30.0;
    const bottom = 26.0;
    const top = 12.0;
    final height = size.height - bottom - top;
    final width = size.width - left - 8;
    final axis = Paint()
      ..color = CyberForgeColors.grid
      ..strokeWidth = 1;
    for (var row = 0; row <= 3; row++) {
      final y = top + height * row / 3;
      canvas.drawLine(Offset(left, y), Offset(size.width - 8, y), axis);
    }
    final barWidth = width / 24;
    for (var index = 0; index < 24; index++) {
      final value = values[index];
      final rect = RRect.fromRectAndRadius(
        Rect.fromLTWH(
          left + index * barWidth + 2,
          top + height * (1 - value),
          barWidth - 4,
          height * value,
        ),
        const Radius.circular(3),
      );
      final paint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.bottomCenter,
          end: Alignment.topCenter,
          colors: <Color>[
            CyberForgeColors.blue.withValues(alpha: .55),
            value > .76 ? CyberForgeColors.red : CyberForgeColors.cyan,
          ],
        ).createShader(rect.outerRect);
      canvas.drawRRect(rect, paint);
      if (index % 3 == 0) {
        final text = TextPainter(
          text: TextSpan(
            text: index.toString().padLeft(2, '0'),
            style: const TextStyle(
              color: CyberForgeColors.muted,
              fontSize: 9,
              fontWeight: FontWeight.w600,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        text.paint(canvas, Offset(left + index * barWidth, size.height - 17));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _TimelinePainter oldDelegate) => oldDelegate.values != values;
}
