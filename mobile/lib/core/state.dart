import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'models.dart';

/// A photo grade kept for this session: the farmer can ask with it or sell the lot it certifies.
class GradeEntry {
  GradeEntry(this.result, this.photo, this.at);
  final GradeResult result;
  final Uint8List? photo; // null for a sample-lot scan
  final DateTime at;
}

/// App-wide state: the signed-in account, language, offline mode, consent and the latest grade.
class AppState extends ChangeNotifier {
  SharedPreferences? _prefs;

  User? user;
  String lang = 'bn';
  ThemeMode themeMode = ThemeMode.system;
  bool offline = false;
  bool consent = false;
  bool ready = false;

  final List<GradeEntry> grades = [];
  GradeEntry? get lastGrade => grades.firstOrNull;

  /// The tab the shell should show; other screens ask for a tab by its id ("ask", "scan", "market", ...).
  String tab = 'home';

  /// Prefill for the "List a lot" sheet, set when a grade or a decision says "sell this lot".
  Map<String, dynamic>? sellDraft;

  /// A certificate the next voice question should be graded by (set from a grade's "Ask with this grade").
  String? askWithCert;

  Future<void> load() async {
    try {
      _prefs = await SharedPreferences.getInstance();
    } catch (_) {
      _prefs = null; // storage unavailable (a private browser window): this visit only
    }
    final p = _prefs;
    if (p != null) {
      lang = p.getString('lang') ?? 'bn';
      offline = p.getBool('offline') ?? false;
      consent = p.getString('consent') != null;
      themeMode = ThemeMode.values.byName(p.getString('theme') ?? 'system');
      Api.base = p.getString('server') ?? Api.defaultBase;
      Api.token = p.getString('token');
      final saved = p.getString('user');
      if (Api.token != null && saved != null) user = User((jsonDecode(saved) as Map).cast<String, dynamic>());
    }
    Api.onUnauthorized = () => logout(expired: true);
    ready = true;
    notifyListeners();
    if (user != null) _refreshMe();
  }

  /// Re-reads the account (a disabled or deleted account signs out); keeps the cached one when offline.
  Future<void> _refreshMe() async {
    try {
      final me = await Api.get('/auth/me', timeout: const Duration(seconds: 8));
      user = User((me as Map).cast<String, dynamic>());
      await _prefs?.setString('user', jsonEncode(user!.j));
      notifyListeners();
    } on ApiError {
      // 401 already signed out through Api.onUnauthorized; unreachable keeps the cached account.
    }
  }

  bool sessionExpired = false;

  Future<void> signIn(Map<String, dynamic> session) async {
    Api.token = session['token'] as String;
    user = User((session['user'] as Map).cast<String, dynamic>());
    sessionExpired = false;
    tab = 'home';
    await _prefs?.setString('token', Api.token!);
    await _prefs?.setString('user', jsonEncode(user!.j));
    notifyListeners();
  }

  Future<void> logout({bool expired = false}) async {
    Api.token = null;
    user = null;
    sessionExpired = expired;
    grades.clear();
    sellDraft = null;
    askWithCert = null;
    await _prefs?.remove('token');
    await _prefs?.remove('user');
    notifyListeners();
  }

  void setLang(String value) {
    lang = value;
    _prefs?.setString('lang', value);
    notifyListeners();
  }

  void setTheme(ThemeMode mode) {
    themeMode = mode;
    _prefs?.setString('theme', mode.name);
    notifyListeners();
  }

  void setOffline(bool value) {
    offline = value;
    _prefs?.setBool('offline', value);
    notifyListeners();
  }

  void setServer(String value) {
    Api.base = value;
    _prefs?.setString('server', value);
    notifyListeners();
  }

  Future<void> giveConsent() async {
    consent = true;
    await _prefs?.setString('consent', DateTime.now().toIso8601String());
    notifyListeners();
  }

  Future<void> withdrawConsent() async {
    consent = false;
    await _prefs?.remove('consent');
    notifyListeners();
  }

  void addGrade(GradeResult result, Uint8List? photo) {
    grades.insert(0, GradeEntry(result, photo, DateTime.now()));
    if (grades.length > 8) grades.removeLast();
    notifyListeners();
  }

  void goTab(String id) {
    tab = id;
    notifyListeners();
  }

  void sellLot(Map<String, dynamic> draft) {
    sellDraft = draft;
    goTab('market');
  }

  void askWith(String certId) {
    askWithCert = certId;
    goTab('ask');
  }
}

final app = AppState();

/// Picks the string for the app's language: Bangla first, English for everyone else.
String t(String bn, String en) => app.lang == 'bn' ? bn : en;
