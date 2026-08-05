import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../domain/models.dart';
import '../../theme/cyberforge_theme.dart';

final class AttackSurfaceMap extends StatelessWidget {
  const AttackSurfaceMap({required this.scenario, super.key});

  final SimulationScenario scenario;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 1.8,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: CustomPaint(
          painter: _AttackSurfacePainter(scenario),
          child: const SizedBox.expand(),
        ),
      ),
    );
  }
}

final class _AttackSurfacePainter extends CustomPainter {
  _AttackSurfacePainter(this.scenario);
  final SimulationScenario scenario;

  @override
  void paint(Canvas canvas, Size size) {
    final background = Paint()..color = CyberForgeColors.background;
    canvas.drawRect(Offset.zero & size, background);
    final grid = Paint()
      ..color = CyberForgeColors.grid.withValues(alpha: 0.35)
      ..strokeWidth = 1;
    for (var x = 0.0; x <= size.width; x += 32) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
    }
    for (var y = 0.0; y <= size.height; y += 32) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }
    if (scenario.assets.isEmpty) return;
    final center = size.center(Offset.zero);
    final radius = math.min(size.width, size.height) * 0.34;
    final points = <String, Offset>{};
    for (var i = 0; i < scenario.assets.length; i += 1) {
      final angle = -math.pi / 2 + i * math.pi * 2 / scenario.assets.length;
      points[scenario.assets[i].id] = Offset(
        center.dx + math.cos(angle) * radius,
        center.dy + math.sin(angle) * radius,
      );
    }
    final edgePaint = Paint()
      ..color = CyberForgeColors.blue.withValues(alpha: 0.45)
      ..strokeWidth = 1.6;
    for (final edge in scenario.edges) {
      final from = points[edge.fromId];
      final to = points[edge.toId];
      if (from == null || to == null) continue;
      canvas.drawLine(from, to, edgePaint);
      final direction = to - from;
      final length = direction.distance;
      if (length > 0) {
        final unit = direction / length;
        final tip = to - unit * 17;
        final normal = Offset(-unit.dy, unit.dx);
        final path = Path()
          ..moveTo(tip.dx, tip.dy)
          ..lineTo((tip - unit * 8 + normal * 4).dx, (tip - unit * 8 + normal * 4).dy)
          ..lineTo((tip - unit * 8 - normal * 4).dx, (tip - unit * 8 - normal * 4).dy)
          ..close();
        canvas.drawPath(path, edgePaint);
      }
    }
    for (final asset in scenario.assets) {
      final point = points[asset.id]!;
      final nodeColor = _colorFor(asset.kind);
      final glow = Paint()..color = nodeColor.withValues(alpha: 0.15);
      canvas.drawCircle(point, 24, glow);
      final node = Paint()..color = nodeColor;
      canvas.drawCircle(point, 11, node);
      final ring = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = CyberForgeColors.text.withValues(alpha: 0.75);
      canvas.drawCircle(point, 15, ring);
      final text = TextPainter(
        text: TextSpan(
          text: asset.name,
          style: const TextStyle(
            color: CyberForgeColors.text,
            fontSize: 10,
            fontWeight: FontWeight.w600,
          ),
        ),
        maxLines: 2,
        ellipsis: '…',
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: 100);
      text.paint(canvas, point + const Offset(-50, 20));
    }
  }

  Color _colorFor(AssetKind kind) => switch (kind) {
        AssetKind.identity || AssetKind.credential => CyberForgeColors.violet,
        AssetKind.facility => CyberForgeColors.amber,
        AssetKind.supplier => CyberForgeColors.red,
        AssetKind.endpoint || AssetKind.server => CyberForgeColors.cyan,
        _ => CyberForgeColors.green,
      };

  @override
  bool shouldRepaint(covariant _AttackSurfacePainter oldDelegate) =>
      oldDelegate.scenario != scenario;
}
