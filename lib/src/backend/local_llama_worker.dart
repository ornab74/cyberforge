import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Supervises the optional Python llama-cpp worker beneath the Dart backend.
///
/// Python is deliberately isolated to inference only. It never receives cloud
/// provider keys or the vault recovery key. Installation is explicit, pinned,
/// project-local, and can be disabled with CYBERFORGE_ALLOW_RUNTIME_INSTALL=false.
final class LocalLlamaWorker {
  LocalLlamaWorker({required this.repositoryRoot});

  final Directory repositoryRoot;
  Process? _process;
  final _events = StreamController<String>.broadcast();

  Stream<String> get events => _events.stream;
  bool get isRunning => _process != null;

  Directory get runtimeDirectory =>
      Directory('${repositoryRoot.path}${Platform.pathSeparator}.runtime');
  Directory get venvDirectory =>
      Directory('${runtimeDirectory.path}${Platform.pathSeparator}llama-python');

  String get pythonPath => Platform.isWindows
      ? '${venvDirectory.path}\\Scripts\\python.exe'
      : '${venvDirectory.path}/bin/python';

  Future<void> install({bool force = false}) async {
    if (Platform.environment['CYBERFORGE_ALLOW_RUNTIME_INSTALL'] == 'false') {
      throw StateError('Runtime installation is disabled by policy.');
    }
    await runtimeDirectory.create(recursive: true);
    if (!File(pythonPath).existsSync() || force) {
      final python = await _findPython();
      await _run(python, ['-m', 'venv', venvDirectory.path]);
    }
    await _run(pythonPath, ['-m', 'pip', 'install', '--upgrade', 'pip', 'wheel']);
    await _run(pythonPath, [
      '-m',
      'pip',
      'install',
      '--only-binary=:all:',
      'llama-cpp-python>=0.3.16,<0.4',
    ]);
  }

  Future<void> start({required String modelPath, int port = 8791}) async {
    if (_process != null) return;
    if (!File(pythonPath).existsSync()) {
      throw StateError('Install the local llama runtime first.');
    }
    final model = File(modelPath);
    if (!model.existsSync()) throw StateError('Model file does not exist.');
    _process = await Process.start(
      pythonPath,
      [
        '-m',
        'llama_cpp.server',
        '--host',
        '127.0.0.1',
        '--port',
        '$port',
        '--model',
        model.absolute.path,
      ],
      workingDirectory: repositoryRoot.path,
      environment: <String, String>{
        ...Platform.environment,
        'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
      },
    );
    _pipe(_process!.stdout, 'llama');
    _pipe(_process!.stderr, 'llama:error');
    unawaited(_process!.exitCode.then((code) {
      _events.add('llama worker exited with code $code');
      _process = null;
    }));
  }

  Future<void> stop() async {
    final process = _process;
    _process = null;
    if (process == null) return;
    process.kill(ProcessSignal.sigterm);
    try {
      await process.exitCode.timeout(const Duration(seconds: 5));
    } on TimeoutException {
      process.kill(ProcessSignal.sigkill);
    }
  }

  Future<String> _findPython() async {
    for (final candidate in Platform.isWindows
        ? const ['py', 'python']
        : const ['python3', 'python']) {
      final result = await Process.run(candidate, ['--version']);
      if (result.exitCode == 0) return candidate;
    }
    throw StateError('Python 3 is required for the optional llama.cpp worker.');
  }

  Future<void> _run(String executable, List<String> arguments) async {
    _events.add('running ${[executable, ...arguments].join(' ')}');
    final result = await Process.run(
      executable,
      arguments,
      workingDirectory: repositoryRoot.path,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    if (result.stdout.toString().trim().isNotEmpty) {
      _events.add(result.stdout.toString().trim());
    }
    if (result.exitCode != 0) {
      throw StateError(result.stderr.toString().trim());
    }
  }

  void _pipe(Stream<List<int>> stream, String label) {
    stream.transform(utf8.decoder).transform(const LineSplitter()).listen(
          (line) => _events.add('$label: $line'),
        );
  }
}
