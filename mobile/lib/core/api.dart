import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

/// A failed call. [status] 0 means the server could not be reached at all.
class ApiError implements Exception {
  ApiError(this.status, this.message);

  final int status;
  final String message;

  bool get unreachable => status == 0;

  @override
  String toString() => message;
}

/// The KrishiNexus node's HTTP API (backend/main.py). The hosted node is the default; `--dart-define=API_BASE=...`
/// or the Me tab points the app at a village kiosk or a laptop instead.
class Api {
  static const defaultBase = String.fromEnvironment('API_BASE', defaultValue: 'https://tanvir.health');
  static String base = defaultBase;
  static String? token;

  /// Called when the server rejects the session (expired or revoked), so the app can sign out.
  static void Function()? onUnauthorized;

  static final _client = http.Client();

  static Map<String, String> _headers({bool json = true}) => {
        if (json) 'Content-Type': 'application/json',
        'Accept': json ? 'application/json' : '*/*',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  static Uri _uri(String path) => Uri.parse('$base$path');

  static Future<Object?> get(String path, {Duration timeout = const Duration(seconds: 25)}) async =>
      _json(await _send(() => _client.get(_uri(path), headers: _headers()), timeout));

  /// The last write from this phone and when: live banners skip what the user has just done here.
  static String lastWrite = '';
  static DateTime lastWriteAt = DateTime(0);

  static Future<Object?> post(String path, [Object? body, Duration timeout = const Duration(seconds: 90)]) async {
    lastWrite = path;
    lastWriteAt = DateTime.now();
    return _json(await _send(() => _client.post(_uri(path), headers: _headers(), body: jsonEncode(body ?? const <String, dynamic>{})), timeout));
  }

  /// A POST whose answer is binary (the online Bangla voice, audio/mpeg).
  static Future<Uint8List> postBytes(String path, Object body, {Duration timeout = const Duration(seconds: 40)}) async =>
      (await _send(() => _client.post(_uri(path), headers: _headers(), body: jsonEncode(body)), timeout)).bodyBytes;

  static Future<http.Response> _send(Future<http.Response> Function() call, Duration timeout) async {
    final http.Response response;
    try {
      response = await call().timeout(timeout);
    } on TimeoutException {
      throw ApiError(0, 'The server took too long to answer.');
    } catch (_) {
      // SocketException, ClientException, a browser's failed fetch: no route to the node.
      throw ApiError(0, 'The KrishiNexus server could not be reached.');
    }
    if (response.statusCode >= 400) {
      if (response.statusCode == 401 && token != null) onUnauthorized?.call();
      throw ApiError(response.statusCode, _detail(response));
    }
    return response;
  }

  // FastAPI sends JSON without a charset, so the body is decoded as UTF-8 explicitly (Bangla text).
  static Object? _json(http.Response response) =>
      response.bodyBytes.isEmpty ? null : jsonDecode(utf8.decode(response.bodyBytes));

  static String _detail(http.Response response) {
    try {
      final body = _json(response);
      final detail = body is Map ? body['detail'] : null;
      if (detail is String) return detail;
      if (detail is List && detail.isNotEmpty && detail.first is Map) {
        final first = detail.first as Map;
        final field = first['loc'] is List ? (first['loc'] as List).last : null;
        return [if (field != null) '$field:', first['msg'] ?? ''].join(' ');
      }
    } catch (_) {
      // Not JSON (a proxy's HTML error page): fall through to the status line.
    }
    return response.statusCode == 429
        ? 'Too many requests from this phone; wait a minute and try again.'
        : 'HTTP ${response.statusCode} ${response.reasonPhrase ?? ''}'.trim();
  }
}
