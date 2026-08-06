import 'dart:io';

import 'package:flutter/material.dart';

import 'src/app.dart';
import 'src/backend_bootstrap.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await BackendBootstrap.start();
  } on Object catch (error) {
    // The UI still starts so Settings can explain/retry the backend setup.
    stderr.writeln('CyberForge backend bootstrap failed: $error');
  }
  runApp(const CyberForgeApp());
}
