import 'package:flutter/material.dart';

import '../../theme/cyberforge_theme.dart';

final class SurfaceMatrix extends StatelessWidget {
  const SurfaceMatrix({required this.dimensions, super.key});
  final Map<String, dynamic> dimensions;

  static const _icons = <String, IconData>{
    'credential': Icons.key,
    'phishing': Icons.mark_email_unread,
    'endpoint': Icons.devices,
    'api': Icons.api,
    'cloud': Icons.cloud,
    'physical': Icons.badge,
    'vendor': Icons.handshake,
    'availability': Icons.monitor_heart,
    'data': Icons.storage,
  };

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final width = constraints.maxWidth;
        final columns = width >= 760
            ? 3
            : width >= 440
            ? 2
            : 1;
        final entries = _icons.entries.toList(growable: false);
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: entries.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            mainAxisExtent: 82,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
          ),
          itemBuilder: (BuildContext context, int index) {
            final entry = entries[index];
            final value = _asDouble(dimensions[entry.key]);
            return _SurfaceCell(
              label: entry.key,
              icon: entry.value,
              value: value,
            );
          },
        );
      },
    );
  }
}

final class _SurfaceCell extends StatelessWidget {
  const _SurfaceCell({
    required this.label,
    required this.icon,
    required this.value,
  });

  final String label;
  final IconData icon;
  final double value;

  @override
  Widget build(BuildContext context) {
    final severity = value > .74
        ? CyberForgeColors.red
        : value > .48
        ? CyberForgeColors.amber
        : CyberForgeColors.green;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: CyberForgeColors.surfaceRaised.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: CyberForgeColors.grid),
      ),
      child: Row(
        children: <Widget>[
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: severity.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: severity, size: 21),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        label.toUpperCase(),
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: CyberForgeColors.muted,
                          letterSpacing: .8,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    Text(
                      '${(value * 100).round()}',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: severity,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(99),
                  child: LinearProgressIndicator(
                    value: value,
                    minHeight: 5,
                    backgroundColor: CyberForgeColors.grid,
                    valueColor: AlwaysStoppedAnimation<Color>(severity),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

double _asDouble(Object? value) => value is num
    ? value.toDouble().clamp(0.0, 1.0).toDouble()
    : (double.tryParse(value?.toString() ?? '') ?? 0)
          .clamp(0.0, 1.0)
          .toDouble();
