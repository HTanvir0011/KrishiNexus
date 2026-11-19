import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'api.dart';
import 'state.dart';

/// How an answer was read out: the phone's own Bangla voice, the node's online voice (POST /edge/tts), or not at all.
enum Spoken { device, online, none }

/// Speech in and out. Listening uses the phone's speech recogniser in Bangla (bn-BD; Google's on Android, the
/// browser's on the web build). Reading uses the phone's Bangla voice and, when it has none, the node's online voice.
class VoiceService {
  VoiceService() {
    _tts.setCompletionHandler(() => speaking.value = false);
    _tts.setCancelHandler(() => speaking.value = false);
    _tts.setErrorHandler((_) => speaking.value = false);
    _player.onPlayerComplete.listen((_) => speaking.value = false);
  }

  final _stt = SpeechToText();
  final _tts = FlutterTts();
  final _player = AudioPlayer();
  bool? _ready;
  bool? _deviceBangla;

  /// True while an answer is being read out.
  final speaking = ValueNotifier<bool>(false);

  /// Microphone loudness, 0 to 1, while listening (Android and iOS report it; the web build does not).
  final level = ValueNotifier<double>(0);

  void Function(String message)? _onError;
  VoidCallback? _onEnd;
  bool _ended = true;

  bool get listening => _stt.isListening;

  Future<bool> available() async {
    if (_ready != null) return _ready!;
    try {
      _ready = await _stt.initialize(onError: _error, onStatus: _status);
    } catch (_) {
      _ready = false;
    }
    return _ready!;
  }

  /// Starts listening in Bangla. [onWords] gets the words heard so far and, last, the final words.
  /// Returns false when this phone has no speech recogniser (the caller offers typing instead).
  Future<bool> listen({
    required void Function(String words, bool isFinal) onWords,
    required void Function(String message) onError,
    required VoidCallback onEnd,
  }) async {
    await stopSpeaking();
    if (!await available()) return false;
    _onError = onError;
    _onEnd = onEnd;
    _ended = false;
    level.value = 0;
    try {
      await _stt.listen(
        onResult: (r) => onWords(r.recognizedWords, r.finalResult),
        onSoundLevelChange: (db) => level.value = ((db + 2) / 12).clamp(0.0, 1.0),
        listenOptions: SpeechListenOptions(
          localeId: 'bn-BD',
          partialResults: true,
          cancelOnError: true,
          listenMode: ListenMode.dictation,
          listenFor: const Duration(seconds: 45),
          pauseFor: const Duration(seconds: 4),
        ),
      );
    } catch (e) {
      _finish();
      onError(t('মাইক্রোফোন চালু করা গেল না।', 'The microphone could not start.'));
    }
    return true;
  }

  /// Stops listening; the recogniser then delivers its final words.
  Future<void> stop() async {
    try {
      await _stt.stop();
    } catch (_) {
      _finish();
    }
  }

  Future<void> cancel() async {
    try {
      await _stt.cancel();
    } catch (_) {
      // never started
    }
    _finish();
  }

  void _status(String status) {
    if (status == SpeechToText.doneStatus || status == SpeechToText.notListeningStatus) _finish();
  }

  void _finish() {
    level.value = 0;
    if (_ended) return;
    _ended = true;
    _onEnd?.call();
  }

  void _error(SpeechRecognitionError error) {
    final code = error.errorMsg;
    final message = switch (code) {
      'error_no_match' || 'error_speech_timeout' || 'no-speech' || 'aborted' =>
        t('কিছু শুনতে পাইনি। আবার বলুন, একটু জোরে।', 'I did not catch that. Please say it again, a little louder.'),
      'error_permission' || 'error_insufficient_permissions' || 'not-allowed' || 'service-not-allowed' || 'audio-capture' => t(
          'মাইক্রোফোনের অনুমতি নেই। ফোনের সেটিংসে KrishiNexus-কে মাইক্রোফোন ব্যবহারের অনুমতি দিন।',
          'Microphone permission is off. Allow it for KrishiNexus in the phone settings.'),
      'error_network' || 'error_network_timeout' || 'error_server_disconnected' || 'network' => t(
          'বাংলা শোনার জন্য ইন্টারনেট দরকার। লিখে পাঠাতে পারেন।',
          'Bangla speech recognition needs the internet here. You can type the question instead.'),
      'error_language_not_supported' || 'error_language_unavailable' || 'language-not-supported' => t(
          'এই ফোনে বাংলা ভয়েস টাইপিং নেই। Google অ্যাপে বাংলা যোগ করুন বা লিখে পাঠান।',
          'This phone has no Bangla speech recognition. Add Bangla in the Google app, or type the question.'),
      'error_busy' => t('মাইক্রোফোন ব্যস্ত, একটু পরে চেষ্টা করুন।', 'The microphone is busy; try again in a moment.'),
      _ => t('শোনা গেল না ($code)।', 'Listening failed ($code).'),
    };
    _onError?.call(message);
    if (error.permanent) _finish();
  }

  // Only a "yes" is cached: a browser lists its voices late, so an early "no" may not hold.
  Future<bool> _hasDeviceBangla() async {
    if (_deviceBangla == true) return true;
    try {
      if (await _tts.isLanguageAvailable('bn-BD') == true) return _deviceBangla = true;
      final voices = await _tts.getVoices;
      return _deviceBangla = voices is List && voices.any((v) => v is Map && '${v['locale']}'.toLowerCase().startsWith('bn'));
    } catch (_) {
      return false;
    }
  }

  /// Reads [text] aloud. Bangla on a phone without a Bangla voice falls back to the node's online voice, unless
  /// [online] is false (Offline edge mode).
  Future<Spoken> speak(String text, {bool bangla = true, bool online = true}) async {
    await stopSpeaking();
    if (text.trim().isEmpty) return Spoken.none;
    if (!bangla || await _hasDeviceBangla()) {
      try {
        await _tts.setLanguage(bangla ? 'bn-BD' : 'en-US');
        // flutter_tts doubles the rate on Android (0.5 = normal); browsers take it as is (1.0 = normal).
        await _tts.setSpeechRate(kIsWeb ? (bangla ? 0.9 : 1.0) : (bangla ? 0.45 : 0.5));
        speaking.value = true;
        final result = await _tts.speak(text);
        if (result == 1 || result == true) return Spoken.device;
      } catch (_) {
        // fall through to the online voice
      }
      speaking.value = false;
    }
    if (!bangla || !online) return Spoken.none;
    try {
      final audio = await Api.postBytes('/edge/tts', {'text': text.length > 1500 ? text.substring(0, 1500) : text});
      speaking.value = true;
      await _player.play(BytesSource(audio, mimeType: 'audio/mpeg'));
      return Spoken.online;
    } catch (_) {
      speaking.value = false;
      return Spoken.none;
    }
  }

  Future<void> stopSpeaking() async {
    if (!speaking.value) return;
    speaking.value = false;
    try {
      await _tts.stop();
      await _player.stop();
    } catch (_) {
      // nothing was playing
    }
  }
}

final voice = VoiceService();
