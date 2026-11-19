import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// KrishiNexus colours, carried over from the website (frontend/design/DESIGN_PLAN.md §3 and §11).
class Brand {
  static const green = Color(0xFF047857); // emerald-700: brand, growth, recommended option
  static const greenDeep = Color(0xFF065F46);
  static const greenSoft = Color(0xFFD1FAE5);
  static const flag = Color(0xFF006A4E); // Bangladesh flag green (logo)
  static const mustard = Color(0xFFEDB723); // logo accent
  static const amber = Color(0xFFD97706); // action, farmer quota, warnings
  static const amberSoft = Color(0xFFFEF3C7);
  static const rose = Color(0xFFE11D48); // danger, blocked sale, syndicate
  static const roseSoft = Color(0xFFFFE4E6);
  static const sky = Color(0xFF0369A1); // cold chain, water
  static const skySoft = Color(0xFFE0F2FE);
  static const monsoon = Color(0xFF6FA8B5); // logo, flood radar
  static const violet = Color(0xFF6D28D9); // credit
  static const violetSoft = Color(0xFFEDE9FE);
  static const canvas = Color(0xFFF6F8F5); // warm alabaster
  static const ink = Color(0xFF0F172A);
  static const inkSoft = Color(0xFF475569);
  static const line = Color(0xFFE2E8F0);
  // Night paddy world (website Phase 7), used for the dark theme and the camera.
  static const night = Color(0xFF0E211A);
  static const delta = Color(0xFF17352A);
  static const deltaHigh = Color(0xFF1F4436);
  static const husk = Color(0xFFEFEBDD);
  static const silt = Color(0xFF9DB0A3);
  static const sunRed = Color(0xFFF2545B);
}

/// One tone family per meaning; resolves for light and dark themes.
enum Tone { green, amber, rose, sky, violet, slate }

extension ToneColors on Tone {
  Color fg(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return switch (this) {
      Tone.green => dark ? const Color(0xFF6EE7B7) : Brand.green,
      Tone.amber => dark ? Brand.mustard : const Color(0xFFB45309),
      Tone.rose => dark ? Brand.sunRed : Brand.rose,
      Tone.sky => dark ? const Color(0xFF7DD3FC) : Brand.sky,
      Tone.violet => dark ? const Color(0xFFC4B5FD) : Brand.violet,
      Tone.slate => dark ? Brand.silt : Brand.inkSoft,
    };
  }

  Color bg(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    if (dark) return fg(context).withValues(alpha: 0.14);
    return switch (this) {
      Tone.green => const Color(0xFFECFDF5),
      Tone.amber => Brand.amberSoft,
      Tone.rose => const Color(0xFFFFF1F2),
      Tone.sky => const Color(0xFFF0F9FF),
      Tone.violet => const Color(0xFFF5F3FF),
      Tone.slate => const Color(0xFFF1F5F9),
    };
  }
}

/// Motion tokens: exponential ease-out from a visible default; every duration collapses when the system says
/// "Remove animations".
class Motion {
  static const expo = Cubic(0.16, 1, 0.3, 1);
  static const short = Duration(milliseconds: 180);
  static const medium = Duration(milliseconds: 320);
  static const long = Duration(milliseconds: 620);

  static bool reduced(BuildContext context) => MediaQuery.maybeDisableAnimationsOf(context) ?? false;
  static Duration of(BuildContext context, Duration d) => reduced(context) ? Duration.zero : d;
}

/// The farmer's own words and the words read back to them (Tiro Bangla, the website's "voice" face).
TextStyle voiceStyle(BuildContext context, {double size = 19, Color? color, FontWeight weight = FontWeight.w400}) => TextStyle(
      fontFamily: 'TiroBangla',
      fontFamilyFallback: const ['TiroLatin', 'AnekLatin'],
      fontSize: size,
      height: 1.55,
      color: color ?? Theme.of(context).colorScheme.onSurface,
      fontWeight: weight,
    );

const tabular = [FontFeature.tabularFigures()];

ThemeData buildTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final scheme = ColorScheme.fromSeed(seedColor: Brand.green, brightness: brightness).copyWith(
    primary: dark ? const Color(0xFF6EE7B7) : Brand.green,
    onPrimary: dark ? const Color(0xFF053B2C) : Colors.white,
    primaryContainer: dark ? const Color(0xFF14533F) : Brand.greenSoft,
    onPrimaryContainer: dark ? const Color(0xFFD1FAE5) : const Color(0xFF064E3B),
    secondary: dark ? Brand.mustard : Brand.amber,
    onSecondary: dark ? const Color(0xFF3B2A00) : Colors.white,
    secondaryContainer: dark ? const Color(0xFF4A3A0A) : Brand.amberSoft,
    onSecondaryContainer: dark ? const Color(0xFFFDE68A) : const Color(0xFF78350F),
    tertiary: dark ? const Color(0xFF7DD3FC) : Brand.sky,
    tertiaryContainer: dark ? const Color(0xFF0C3A52) : Brand.skySoft,
    onTertiaryContainer: dark ? const Color(0xFFE0F2FE) : const Color(0xFF0C4A6E),
    error: dark ? Brand.sunRed : Brand.rose,
    errorContainer: dark ? const Color(0xFF5A1620) : Brand.roseSoft,
    onErrorContainer: dark ? const Color(0xFFFFE4E6) : const Color(0xFF881337),
    surface: dark ? Brand.night : Brand.canvas,
    onSurface: dark ? Brand.husk : Brand.ink,
    onSurfaceVariant: dark ? Brand.silt : Brand.inkSoft,
    surfaceContainerLowest: dark ? const Color(0xFF0A1913) : Colors.white,
    surfaceContainerLow: dark ? const Color(0xFF132B22) : Colors.white,
    surfaceContainer: dark ? Brand.delta : const Color(0xFFEFF3EE),
    surfaceContainerHigh: dark ? Brand.deltaHigh : const Color(0xFFE8EDE7),
    surfaceContainerHighest: dark ? const Color(0xFF285240) : const Color(0xFFE1E7E0),
    outline: dark ? const Color(0xFF5E7A6C) : const Color(0xFF94A3B8),
    outlineVariant: dark ? const Color(0xFF2B4A3D) : Brand.line,
  );

  final base = ThemeData(useMaterial3: true, colorScheme: scheme, brightness: brightness);
  // Bangla glyphs from Anek Bangla, Latin letters and digits from its Latin cut (bundled in assets/fonts).
  final ui = base.textTheme.apply(fontFamily: 'AnekBangla', fontFamilyFallback: const ['AnekLatin']);
  final text = ui.copyWith(
    displaySmall: ui.displaySmall?.copyWith(fontWeight: FontWeight.w600, height: 1.1),
    headlineMedium: ui.headlineMedium?.copyWith(fontWeight: FontWeight.w600, height: 1.2),
    headlineSmall: ui.headlineSmall?.copyWith(fontWeight: FontWeight.w600, height: 1.25),
    titleLarge: ui.titleLarge?.copyWith(fontWeight: FontWeight.w600, fontSize: 21),
    titleMedium: ui.titleMedium?.copyWith(fontWeight: FontWeight.w600, fontSize: 17),
    titleSmall: ui.titleSmall?.copyWith(fontWeight: FontWeight.w600, fontSize: 15),
    bodyLarge: ui.bodyLarge?.copyWith(fontSize: 17, height: 1.5),
    bodyMedium: ui.bodyMedium?.copyWith(fontSize: 15, height: 1.5),
    bodySmall: ui.bodySmall?.copyWith(fontSize: 13, height: 1.45),
    labelLarge: ui.labelLarge?.copyWith(fontSize: 15, fontWeight: FontWeight.w600),
    labelMedium: ui.labelMedium?.copyWith(fontSize: 13, fontWeight: FontWeight.w500),
  ).apply(bodyColor: scheme.onSurface, displayColor: scheme.onSurface);

  final shape16 = RoundedRectangleBorder(borderRadius: BorderRadius.circular(16));
  return base.copyWith(
    textTheme: text,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      surfaceTintColor: Colors.transparent,
      scrolledUnderElevation: 1,
      centerTitle: false,
      titleTextStyle: text.titleLarge,
      systemOverlayStyle: dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
    ),
    cardTheme: CardThemeData(
      color: scheme.surfaceContainerLowest,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16), side: BorderSide(color: scheme.outlineVariant)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: scheme.surfaceContainerLowest,
      indicatorColor: scheme.primaryContainer,
      surfaceTintColor: Colors.transparent,
      height: 72,
      labelTextStyle: WidgetStateProperty.resolveWith((s) => text.labelMedium?.copyWith(
          fontWeight: s.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: s.contains(WidgetState.selected) ? scheme.onSurface : scheme.onSurfaceVariant)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
          minimumSize: const Size(64, 52), shape: shape16, textStyle: text.labelLarge, padding: const EdgeInsets.symmetric(horizontal: 20)),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
          minimumSize: const Size(64, 52), shape: shape16, textStyle: text.labelLarge, side: BorderSide(color: scheme.outline)),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(minimumSize: const Size(48, 48), textStyle: text.labelLarge),
    ),
    chipTheme: base.chipTheme.copyWith(
      labelStyle: text.labelLarge?.copyWith(fontWeight: FontWeight.w500),
      side: BorderSide(color: scheme.outlineVariant),
      shape: const StadiumBorder(),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: scheme.surfaceContainerLowest,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: scheme.outline)),
      enabledBorder:
          OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: scheme.outlineVariant)),
      focusedBorder:
          OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: scheme.primary, width: 2)),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: scheme.surfaceContainerLow,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      contentTextStyle: text.bodyMedium?.copyWith(color: scheme.onInverseSurface),
    ),
    dividerTheme: DividerThemeData(color: scheme.outlineVariant, space: 1),
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: scheme.primary,
      selectionColor: scheme.primary.withValues(alpha: 0.25),
      selectionHandleColor: scheme.primary,
    ),
  );
}
