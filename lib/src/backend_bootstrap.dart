import 'dart:async';
import 'dart:io';

/// Launches CyberForge's loopback backend for desktop development.
///
/// The native Dart control plane is preferred. During endpoint migration the
/// legacy Python sidecar remains an explicit compatibility fallback. Python is
/// also retained as an optional llama.cpp inference worker.
final class BackendBootstrap {
  static Future<Process?> start() async {
    if (!Platform.isLinux && !Platform.isMacOS && !Platform.isWindows) {
      return null;
    }
    if (Platform.environment['FLUTTER_TEST'] == 'true' ||
        Platform.environment['CYBERFORGE_AUTO_BACKEND'] == 'false') {
      return null;
    }
    final root = _findRoot();
    if (root == null) return null;
    if (await _isListening()) return null;

    final mode = Platform.environment['CYBERFORGE_BACKEND_MODE'] ?? 'dart';
    if (mode != 'python') {
      final dart = await _findExecutable(
        Platform.isWindows ? const ['dart.exe', 'dart'] : const ['dart'],
      );
      if (dart != null) {
        final process = await Process.start(
          dart,
          ['run', 'bin/cyberforge_backend.dart'],
          workingDirectory: root.path,
          environment: <String, String>{
            ...Platform.environment,
            'CYBERFORGE_BACKEND_PORT': '8788',
          },
        );
        _drain(process);
        if (await _waitForHealth()) return process;
        process.kill();
      }
      if (mode == 'dart-only') {
        throw StateError('The Dart backend could not be started.');
      }
    }

    return _startLegacyPython(root);
  }

  static Future<Process> _startLegacyPython(Directory root) async {
    final venv = Directory('${root.path}/.venv');
    final python = Platform.isWindows
        ? '${venv.path}\\Scripts\\python.exe'
        : '${venv.path}/bin/python';
    if (!File(python).existsSync()) {
      final hostPython = await _findExecutable(
        Platform.isWindows ? const ['py', 'python'] : const ['python3', 'python'],
      );
      if (hostPython == null) {
        throw StateError('Python 3 is unavailable for compatibility fallback.');
      }
      final result = await Process.run(
        hostPython,
        ['-m', 'venv', venv.path],
        workingDirectory: root.path,
      );
      if (result.exitCode != 0) {
        throw StateError('Could not create CyberForge .venv: ${result.stderr}');
      }
    }
    final pip = Platform.isWindows
        ? '${venv.path}\\Scripts\\pip.exe'
        : '${venv.path}/bin/pip';
    final result = await Process.run(
      pip,
      ['install', '-r', 'sidecar/requirements.txt'],
      workingDirectory: root.path,
    );
    if (result.exitCode != 0) {
      throw StateError('Could not install compatibility sidecar: ${result.stderr}');
    }
    final process = await Process.start(
      python,
      ['-m', 'cyberforge_sidecar'],
      workingDirectory: root.path,
      environment: <String, String>{
        ...Platform.environment,
        'PYTHONPATH':
            '${root.path}/sidecar${Platform.pathSeparator}${Platform.environment['PYTHONPATH'] ?? ''}',
      },
    );
    _drain(process);
    return process;
  }

  static Future<bool> _isListening() async {
    try {
      final socket = await Socket.connect(
        '127.0.0.1',
        8788,
        timeout: const Duration(milliseconds: 250),
      );
      socket.destroy();
      return true;
    } on Object {
      return false;
    }
  }

  static Future<bool> _waitForHealth() async {
    for (var attempt = 0; attempt < 20; attempt++) {
      if (await _isListening()) return true;
      await Future<void>.delayed(const Duration(milliseconds: 150));
    }
    return false;
  }

  static Future<String?> _findExecutable(List<String> candidates) async {
    for (final candidate in candidates) {
      try {
        final result = await Process.run(candidate, ['--version']);
        if (result.exitCode == 0) return candidate;
      } on ProcessException {
        // Continue to the next candidate.
      }
    }
    return null;
  }

  static void _drain(Process process) {
    unawaited(process.stdout.transform(SystemEncoding().decoder).forEach((_) {}));
    unawaited(process.stderr.transform(SystemEncoding().decoder).forEach((_) {}));
  }

  static Directory? _findRoot() {
    var directory = Directory.current;
    for (var index = 0; index < 6; index++) {
      if (File('${directory.path}/pubspec.yaml').existsSync() &&
          File('${directory.path}/bin/cyberforge_backend.dart').existsSync()) {
        return directory;
      }
      final parent = directory.parent;
      if (parent.path == directory.path) break;
      directory = parent;
    }
    return null;
  }
}
