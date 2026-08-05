import 'package:flutter/material.dart';

abstract final class CyberForgeColors {
  static const background = Color(0xFF05070D);
  static const surface = Color(0xFF0A1020);
  static const surfaceRaised = Color(0xFF111B31);
  static const grid = Color(0xFF1D2C49);
  static const cyan = Color(0xFF62E8FF);
  static const blue = Color(0xFF4B7BFF);
  static const violet = Color(0xFFA27BFF);
  static const green = Color(0xFF6CFFB2);
  static const amber = Color(0xFFFFD166);
  static const red = Color(0xFFFF6B7A);
  static const text = Color(0xFFF5F8FF);
  static const muted = Color(0xFF9AA9C1);
}

abstract final class CyberForgeTheme {
  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: CyberForgeColors.cyan,
      brightness: Brightness.dark,
      surface: CyberForgeColors.surface,
      error: CyberForgeColors.red,
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: CyberForgeColors.background,
      cardColor: CyberForgeColors.surface,
      dividerColor: CyberForgeColors.grid,
      textTheme: const TextTheme(
        headlineLarge: TextStyle(
          color: CyberForgeColors.text,
          fontWeight: FontWeight.w800,
          letterSpacing: -1.2,
        ),
        headlineSmall: TextStyle(
          color: CyberForgeColors.text,
          fontWeight: FontWeight.w700,
        ),
        titleLarge: TextStyle(
          color: CyberForgeColors.text,
          fontWeight: FontWeight.w700,
        ),
        bodyLarge: TextStyle(color: CyberForgeColors.text, height: 1.45),
        bodyMedium: TextStyle(color: CyberForgeColors.muted, height: 1.42),
        labelLarge: TextStyle(fontWeight: FontWeight.w700),
      ),
      cardTheme: CardThemeData(
        color: CyberForgeColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: const BorderSide(color: CyberForgeColors.grid),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: CyberForgeColors.surfaceRaised,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: CyberForgeColors.grid),
        ),
      ),
      navigationRailTheme: const NavigationRailThemeData(
        backgroundColor: CyberForgeColors.surface,
        indicatorColor: Color(0x334B7BFF),
        selectedIconTheme: IconThemeData(color: CyberForgeColors.cyan),
        unselectedIconTheme: IconThemeData(color: CyberForgeColors.muted),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: CyberForgeColors.blue,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: CyberForgeColors.surfaceRaised,
      ),
    );
  }
}
