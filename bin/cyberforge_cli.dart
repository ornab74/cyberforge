import 'dart:io';

import 'package:cyberforge/cyberforge.dart';

Future<void> main(List<String> args) async {
  try {
    final options = _CliOptions.parse(args);
    if (options.showHelp) {
      stdout.writeln(_usage);
      return;
    }

    final repository = const ScenarioRepository();
    final scenario = options.scenarioPath == null
        ? repository.demo()
        : await repository.loadFile(options.scenarioPath!);
    final report = await const SimulationEngine().run(
      scenario,
      iterations: options.iterations,
    );
    final output = report.prettyJson();

    if (options.outputPath == null) {
      stdout.writeln(output);
    } else {
      await File(options.outputPath!).writeAsString('$output\n');
      stderr.writeln('CyberForge report written to ${options.outputPath}.');
    }
  } on FormatException catch (error) {
    stderr.writeln('Argument error: ${error.message}\n');
    stderr.writeln(_usage);
    exitCode = 64;
  } on Object catch (error, stackTrace) {
    stderr.writeln('CyberForge failed: $error');
    if (Platform.environment['CYBERFORGE_DEBUG'] == '1') {
      stderr.writeln(stackTrace);
    }
    exitCode = 1;
  }
}

final class _CliOptions {
  const _CliOptions({
    required this.iterations,
    required this.showHelp,
    this.scenarioPath,
    this.outputPath,
  });

  final String? scenarioPath;
  final String? outputPath;
  final int iterations;
  final bool showHelp;

  factory _CliOptions.parse(List<String> args) {
    String? scenarioPath;
    String? outputPath;
    var iterations = 6000;
    var showHelp = false;

    for (var index = 0; index < args.length; index += 1) {
      final argument = args[index];
      switch (argument) {
        case '-h' || '--help':
          showHelp = true;
        case '--demo':
          scenarioPath = null;
        case '--scenario':
          scenarioPath = _nextValue(args, ++index, '--scenario');
        case '--iterations':
          final raw = _nextValue(args, ++index, '--iterations');
          iterations = int.tryParse(raw) ??
              (throw FormatException('Invalid iteration count: $raw'));
        case '--output':
          outputPath = _nextValue(args, ++index, '--output');
        default:
          if (argument.startsWith('-')) {
            throw FormatException('Unknown option: $argument');
          }
          if (scenarioPath != null) {
            throw const FormatException('Only one scenario file is allowed.');
          }
          scenarioPath = argument;
      }
    }

    return _CliOptions(
      scenarioPath: scenarioPath,
      outputPath: outputPath,
      iterations: iterations,
      showHelp: showHelp,
    );
  }

  static String _nextValue(List<String> args, int index, String option) {
    if (index >= args.length) {
      throw FormatException('$option requires a value.');
    }
    return args[index];
  }
}

const _usage = '''
CyberForge defensive simulation CLI

Usage:
  dart run bin/cyberforge_cli.dart [scenario.json]
  dart run bin/cyberforge_cli.dart --scenario scenario.json [options]

Options:
  --demo                 Use the built-in synthetic scenario.
  --scenario <path>      Load a synthetic scenario JSON file.
  --iterations <number>  Monte Carlo worlds, 500 to 100000. Default: 6000.
  --output <path>        Write the JSON report to a file.
  -h, --help             Show this help.
''';
