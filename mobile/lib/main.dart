import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'core/state.dart';
import 'core/theme.dart';
import 'screens/login.dart';
import 'screens/shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  await app.load();
  runApp(const KrishiNexusApp());
}

class KrishiNexusApp extends StatelessWidget {
  const KrishiNexusApp({super.key});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: app,
        builder: (context, _) => MaterialApp(
          title: 'KrishiNexus',
          debugShowCheckedModeBanner: false,
          theme: buildTheme(Brightness.light),
          darkTheme: buildTheme(Brightness.dark),
          themeMode: app.themeMode,
          locale: Locale(app.lang),
          supportedLocales: const [Locale('bn'), Locale('en')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: AnimatedSwitcher(
            duration: const Duration(milliseconds: 420),
            switchInCurve: Motion.expo,
            child: app.user == null ? const LoginScreen(key: ValueKey('login')) : Shell(key: ValueKey(app.user!.id)),
          ),
        ),
      );
}
