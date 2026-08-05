import 'dart:math' as math;

final class GammaFabricConfig {
  const GammaFabricConfig({
    this.simulatedQubitRegister = 3923929,
    this.parallelWorlds = 4096,
    this.coherenceEpochs = 64,
    this.targetCoherence = 0.992,
  });

  final int simulatedQubitRegister;
  final int parallelWorlds;
  final int coherenceEpochs;
  final double targetCoherence;
}

final class GammaComputeFabric {
  const GammaComputeFabric({this.config = const GammaFabricConfig()});

  final GammaFabricConfig config;

  /// Quantum-inspired Monte Carlo scheduler. This is conventional software
  /// running on ordinary CPUs/GPUs; the large register value is a simulation
  /// label and scaling metaphor, not a claim of physical qubit access.
  GammaFabricSession open({required int seed, required int iterations}) {
    return GammaFabricSession(
      config: config,
      random: math.Random(seed),
      seed: seed,
      iterations: iterations,
    );
  }
}

final class GammaFabricSession {
  GammaFabricSession({
    required this.config,
    required this.random,
    required this.seed,
    required this.iterations,
  });

  final GammaFabricConfig config;
  final math.Random random;
  final int seed;
  final int iterations;
  var _samples = 0;
  var _agreement = 0.0;

  double sample(double probability) {
    _samples += 1;
    final bounded = probability.clamp(0.0001, 0.9999).toDouble();
    final observation = random.nextDouble() < bounded ? 1.0 : 0.0;
    _agreement += 1 - (observation - bounded).abs();
    return observation;
  }

  double jitter({double magnitude = 0.04}) =>
      (random.nextDouble() - 0.5) * 2 * magnitude;

  double get coherence {
    if (_samples == 0) return config.targetCoherence;
    final empirical = _agreement / _samples;
    return (0.65 * config.targetCoherence + 0.35 * empirical)
        .clamp(0.0, 1.0)
        .toDouble();
  }
}
