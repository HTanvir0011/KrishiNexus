import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// KrishiNexus colours: flag green is the brand, mustard the one accent (voice and money to receive).
class Brand {
  static const green = Color(
    0xFF006A4E,
  ); // Bangladesh flag green: brand, headers, primary buttons
  static const greenDeep = Color(0xFF004D39);
  static const greenSoft = Color(0xFFD5EBE2);
  static const flag = Color(0xFF006A4E); // Bangladesh flag green (logo)
  static const mustard = Color(0xFFEDB723); // logo accent
  static const voice = Color(
    0xFFEDB723,
  ); // voice and money to receive: nothing else uses it
  static const amber = Color(0xFFD97706); // action, farmer quota, warnings
  static const amberSoft = Color(0xFFFEF3C7);
  static const rose = Color(0xFFE11D48); // danger, blocked sale, syndicate
  static const roseSoft = Color(0xFFFFE4E6);
  static const sky = Color(0xFF0369A1); // cold chain, water
  static const skySoft = Color(0xFFE0F2FE);
  static const monsoon = Color(0xFF6FA8B5); // logo, flood radar
  static const violet = Color(0xFF6D28D9); // credit
  static const violetSoft = Color(0xFFEDE9FE);
  static const canvas = Color(0xFFF7F5EE); // warm paper
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
      Tone.green => const Color(0xFFE3F1EA),
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

  static bool reduced(BuildContext context) =>
      MediaQuery.maybeDisableAnimationsOf(context) ?? false;
  static Duration of(BuildContext context, Duration d) =>
      reduced(context) ? Duration.zero : d;
}

/// The farmer's own words and the words read back to them (Tiro Bangla, the website's "voice" face).
TextStyle voiceStyle(
  BuildContext context, {
  double size = 19,
  Color? color,
  FontWeight weight = FontWeight.w400,
}) => TextStyle(
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
  final scheme =
      ColorScheme.fromSeed(
        seedColor: Brand.green,
        brightness: brightness,
      ).copyWith(
        primary: dark ? const Color(0xFF6EE7B7) : Brand.green,
        onPrimary: dark ? const Color(0xFF053B2C) : Colors.white,
        primaryContainer: dark ? const Color(0xFF14533F) : Brand.greenSoft,
        onPrimaryContainer: dark ? const Color(0xFFD1FAE5) : Brand.greenDeep,
        secondary: dark ? Brand.mustard : Brand.amber,
        onSecondary: dark ? const Color(0xFF3B2A00) : Colors.white,
        secondaryContainer: dark ? const Color(0xFF4A3A0A) : Brand.amberSoft,
        onSecondaryContainer: dark
            ? const Color(0xFFFDE68A)
            : const Color(0xFF78350F),
        tertiary: dark ? const Color(0xFF7DD3FC) : Brand.sky,
        tertiaryContainer: dark ? const Color(0xFF0C3A52) : Brand.skySoft,
        onTertiaryContainer: dark
            ? const Color(0xFFE0F2FE)
            : const Color(0xFF0C4A6E),
        error: dark ? Brand.sunRed : Brand.rose,
        errorContainer: dark ? const Color(0xFF5A1620) : Brand.roseSoft,
        onErrorContainer: dark
            ? const Color(0xFFFFE4E6)
            : const Color(0xFF881337),
        surface: dark ? Brand.night : Brand.canvas,
        onSurface: dark ? Brand.husk : Brand.ink,
        onSurfaceVariant: dark ? Brand.silt : Brand.inkSoft,
        surfaceContainerLowest: dark ? const Color(0xFF0A1913) : Colors.white,
        surfaceContainerLow: dark ? const Color(0xFF132B22) : Colors.white,
        surfaceContainer: dark ? Brand.delta : const Color(0xFFEFEDE4),
        surfaceContainerHigh: dark ? Brand.deltaHigh : const Color(0xFFE8E5DA),
        surfaceContainerHighest: dark
            ? const Color(0xFF285240)
            : const Color(0xFFDFDCD0),
        outline: dark ? const Color(0xFF6F8E7E) : const Color(0xFF7C8796),
        outlineVariant: dark
            ? const Color(0xFF2B4A3D)
            : const Color(0xFFE4E1D6),
      );

  final base = ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    brightness: brightness,
  );
  // Bangla glyphs from Anek Bangla, Latin letters and digits from its Latin cut (bundled in assets/fonts).
  final ui = base.textTheme.apply(
    fontFamily: 'AnekBangla',
    fontFamilyFallback: const ['AnekLatin'],
  );
  final text = ui
      .copyWith(
        displaySmall: ui.displaySmall?.copyWith(
          fontWeight: FontWeight.w600,
          height: 1.15,
        ),
        headlineMedium: ui.headlineMedium?.copyWith(
          fontWeight: FontWeight.w600,
          height: 1.25,
        ),
        headlineSmall: ui.headlineSmall?.copyWith(
          fontWeight: FontWeight.w600,
          height: 1.3,
        ),
        titleLarge: ui.titleLarge?.copyWith(
          fontWeight: FontWeight.w600,
          fontSize: 22,
          height: 1.3,
        ),
        titleMedium: ui.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          fontSize: 18,
          height: 1.4,
        ),
        titleSmall: ui.titleSmall?.copyWith(
          fontWeight: FontWeight.w600,
          fontSize: 16,
          height: 1.45,
        ),
        bodyLarge: ui.bodyLarge?.copyWith(fontSize: 17, height: 1.5),
        bodyMedium: ui.bodyMedium?.copyWith(fontSize: 16, height: 1.5),
        bodySmall: ui.bodySmall?.copyWith(fontSize: 14, height: 1.5),
        labelLarge: ui.labelLarge?.copyWith(
          fontSize: 16,
          height: 1.4,
          fontWeight: FontWeight.w600,
        ),
        labelMedium: ui.labelMedium?.copyWith(
          fontSize: 14,
          height: 1.4,
          fontWeight: FontWeight.w500,
        ),
        labelSmall: ui.labelSmall?.copyWith(
          fontSize: 14,
          height: 1.4,
          fontWeight: FontWeight.w500,
        ),
      )
      .apply(bodyColor: scheme.onSurface, displayColor: scheme.onSurface);

  final pillShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(28),
  );
  return base.copyWith(
    textTheme: text,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      surfaceTintColor: Colors.transparent,
      scrolledUnderElevation: 1,
      centerTitle: false,
      titleTextStyle: text.titleLarge,
      systemOverlayStyle: dark
          ? SystemUiOverlayStyle.light
          : SystemUiOverlayStyle.dark,
    ),
    // The soft shadow is drawn by AppCard; a stock Card stays flat.
    cardTheme: CardThemeData(
      color: scheme.surfaceContainerLowest,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: scheme.surfaceContainerLowest,
      indicatorColor: scheme.primary,
      indicatorShape: const StadiumBorder(),
      surfaceTintColor: Colors.transparent,
      height: 64,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      iconTheme: WidgetStateProperty.resolveWith(
        (s) => IconThemeData(
          size: 26,
          color: s.contains(WidgetState.selected)
              ? scheme.onPrimary
              : scheme.onSurfaceVariant,
        ),
      ),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (s) => text.labelMedium?.copyWith(
          fontWeight: s.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w500,
          color: s.contains(WidgetState.selected)
              ? scheme.onSurface
              : scheme.onSurfaceVariant,
        ),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 56),
        shape: pillShape,
        textStyle: text.labelLarge,
        padding: const EdgeInsets.symmetric(horizontal: 24),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(64, 56),
        shape: pillShape,
        textStyle: text.labelLarge,
        side: BorderSide(color: scheme.outline),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(48, 48),
        textStyle: text.labelLarge,
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      labelStyle: text.labelLarge?.copyWith(fontWeight: FontWeight.w500),
      side: BorderSide(color: scheme.outlineVariant),
      shape: const StadiumBorder(),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: scheme.surfaceContainerLowest,
      constraints: const BoxConstraints(minHeight: 56),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: scheme.outline),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: scheme.outline.withValues(alpha: 0.6)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: scheme.primary, width: 2),
      ),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: scheme.surfaceContainerLow,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      contentTextStyle: text.bodyMedium?.copyWith(
        color: scheme.onInverseSurface,
      ),
    ),
    dividerTheme: DividerThemeData(color: scheme.outlineVariant, space: 1),
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: scheme.primary,
      selectionColor: scheme.primary.withValues(alpha: 0.25),
      selectionHandleColor: scheme.primary,
    ),
  );
}
