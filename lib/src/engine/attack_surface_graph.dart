import '../domain/models.dart';

final class AttackSurfaceGraph {
  AttackSurfaceGraph(SimulationScenario scenario)
      : assets = <String, CyberAsset>{
          for (final asset in scenario.assets) asset.id: asset,
        },
        outgoing = <String, List<AttackSurfaceEdge>>{} {
    for (final edge in scenario.edges) {
      outgoing.putIfAbsent(edge.fromId, () => <AttackSurfaceEdge>[]).add(edge);
    }
  }

  final Map<String, CyberAsset> assets;
  final Map<String, List<AttackSurfaceEdge>> outgoing;

  Iterable<AttackSurfaceEdge> edgesFrom(String assetId) =>
      outgoing[assetId] ?? const <AttackSurfaceEdge>[];

  List<String> reachable(String startId, {int maxDepth = 4}) {
    final visited = <String>{startId};
    var frontier = <String>{startId};
    for (var depth = 0; depth < maxDepth && frontier.isNotEmpty; depth += 1) {
      final next = <String>{};
      for (final id in frontier) {
        for (final edge in edgesFrom(id)) {
          if (visited.add(edge.toId)) next.add(edge.toId);
        }
      }
      frontier = next;
    }
    visited.remove(startId);
    return visited.toList(growable: false);
  }

  double blastRadius(String assetId, {int maxDepth = 4}) {
    final reachableAssets = reachable(assetId, maxDepth: maxDepth);
    if (reachableAssets.isEmpty) return 0;
    final weighted = reachableAssets.fold<double>(0, (sum, id) {
      return sum + (assets[id]?.criticality ?? 0.5);
    });
    return (weighted / reachableAssets.length).clamp(0.0, 1.0).toDouble();
  }
}
