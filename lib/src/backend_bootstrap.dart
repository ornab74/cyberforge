import 'dart:async';
import 'dart:io';

/// Prepares and launches the local sidecar for desktop development/builds.
/// Set CYBERFORGE_AUTO_BACKEND=false to manage the sidecar manually.
final class BackendBootstrap {
  static Future<Process?> start() async {
    if (!Platform.isLinux && !Platform.isMacOS && !Platform.isWindows)
      return null;
    if (Platform.environment['FLUTTER_TEST'] == 'true' ||
        Platform.environment['CYBERFORGE_AUTO_BACKEND'] == 'false') {
      return null;
    }
    final root = _findRoot();
    if (root == null) return null;
    try {
      final socket = await Socket.connect(
        '127.0.0.1',
        8788,
        timeout: const Duration(milliseconds: 250),
      );
      socket.destroy();
      return null;
    } on Object {
      // No sidecar is listening; continue with local bootstrap.
    }
    final venv = Directory('${root.path}/.venv');
    final python = Platform.isWindows
        ? '${venv.path}\\Scripts\\python.exe'
        : '${venv.path}/bin/python';
    if (!File(python).existsSync()) {
      final result = await Process.run('python3', [
        '-m',
        'venv',
        venv.path,
      ], workingDirectory: root.path);
      if (result.exitCode != 0)
        throw StateError('Could not create CyberForge .venv: ${result.stderr}');
    }
    final pip = Platform.isWindows
        ? '${venv.path}\\Scripts\\pip.exe'
        : '${venv.path}/bin/pip';
    final requirements = <String>[
      'sidecar/requirements.txt',
      'sidecar/requirements-local.txt',
    ];
    for (final requirement in requirements) {
      final result = await Process.run(pip, [
        'install',
        '-r',
        requirement,
      ], workingDirectory: root.path);
      if (result.exitCode != 0)
        throw StateError('Could not install $requirement: ${result.stderr}');
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
    unawaited(
      process.stdout.transform(SystemEncoding().decoder).forEach((_) {}),
    );
    unawaited(
      process.stderr.transform(SystemEncoding().decoder).forEach((_) {}),
    );
    return process;
  }

  static Directory? _findRoot() {
    var directory = Directory.current;
    for (var index = 0; index < 6; index++) {
      if (File('${directory.path}/sidecar/pyproject.toml').existsSync())
        return directory;
      final parent = directory.parent;
      if (parent.path == directory.path) break;
      directory = parent;
    }
    return null;
  }
}
