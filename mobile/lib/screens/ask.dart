import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../core/voice.dart';
import '../widgets/common.dart';
import '../widgets/consent.dart';
import '../widgets/mic_orb.dart';

class _Preset {
  const _Preset(this.id, this.titleBn, this.titleEn, this.question, this.district, this.upazila);
  final String id;
  final String titleBn;
  final String titleEn;
  final String question;
  final String district;
  final String upazila;
}

/// The five recorded dialect questions the node ships (backend edge_node/bangla_voice.VOICE_PRESETS).
const _presets = [
  _Preset(
    'rangpur_potato_distress',
    'রহিম মিয়া · রংপুরের আলু',
    'Rahim Mia · Rangpur potato',
    'এলা বেচমু না হিমাগারত থুমু?',
    'Rangpur',
    'Mithapukur',
  ),
  _Preset(
    'bogura_chili_syndicate',
    'বগুড়ার কাঁচা মরিচ',
    'Bogura green chili',
    'সিন্ডিকেট ছাড়া ক্যাংকা করি সরাসরি ব্যাচমু?',
    'Bogura',
    'Sariakandi',
  ),
  _Preset('sunamganj_haor_flood', 'আব্দুল · হাওরের বোরো ধান', 'Abdul · Sunamganj haor rice', 'অখন কাটমু নি?', 'Sunamganj', 'Tahirpur'),
  _Preset(
    'munshiganj_cold_storage',
    'মুন্সিগঞ্জের হিমাগার',
    'Munshiganj cold storage',
    'সমিতির মাধ্যমে হিমাগারে জায়গা পাওয়া যাবে?',
    'Munshiganj',
    'Tongibari',
  ),
  _Preset(
    'jessore_brinjal_pooling',
    'যশোরের বেগুন',
    'Jessore brinjal pooling',
    'পাশের গ্রামের চাষিদের সাথে মিলে ঢাকায় পাঠাতে চাই।',
    'Jessore',
    'Jhikargacha',
  ),
];

/// Ask by voice: the farmer speaks (or types, or taps a recorded question), the node's agents decide, and the
/// answer is shown as decision cards and read back in Bangla.
class AskScreen extends StatefulWidget {
  const AskScreen({super.key});

  @override
  State<AskScreen> createState() => _AskScreenState();
}

class _AskScreenState extends State<AskScreen> {
  final _scroll = ScrollController();
  final _typed = TextEditingController();
  final _typedFocus = FocusNode();
  final _answerKey = GlobalKey();

  OrbState _orb = OrbState.idle;
  String _live = '';
  String? _heard;
  VoiceResult? _result;
  late _Preset _place = _presets.firstWhere((p) => p.district == app.user?.district, orElse: () => _presets.first);
  String? _speechNote;
  String? _detached; // a photo grade the farmer chose not to use

  /// The certificate the next question is graded by: one picked from a grade, else the latest photo grade.
  String? get _cert {
    if (app.askWithCert != null) return app.askWithCert;
    final grade = app.lastGrade;
    return grade != null && grade.result.fromPhoto && grade.result.certId != _detached ? grade.result.certId : null;
  }

  @override
  void initState() {
    super.initState();
    voice.speaking.addListener(_onSpeaking);
  }

  void _onSpeaking() {
    if (!voice.speaking.value && _speechNote != null && mounted) setState(() => _speechNote = null);
  }

  @override
  void dispose() {
    voice.speaking.removeListener(_onSpeaking);
    voice.cancel();
    voice.stopSpeaking();
    _scroll.dispose();
    _typed.dispose();
    _typedFocus.dispose();
    super.dispose();
  }

  bool get _isFarmer => app.user?.role == 'farmer';

  Future<void> _toggleMic() async {
    if (_orb == OrbState.thinking) return;
    if (_orb == OrbState.listening) {
      await voice.stop();
      return;
    }
    if (!await ensureConsent(context)) return;
    setState(() {
      _orb = OrbState.listening;
      _live = '';
    });
    var finalWords = '';
    final started = await voice.listen(
      onWords: (words, isFinal) {
        if (!mounted) return;
        setState(() => _live = words);
        if (isFinal) finalWords = words;
      },
      onError: (message) {
        if (mounted) snack(context, message, icon: Icons.mic_off_rounded, tone: Tone.amber);
      },
      onEnd: () {
        if (!mounted) return;
        final words = (finalWords.isNotEmpty ? finalWords : _live).trim();
        setState(() => _orb = OrbState.idle);
        if (words.isNotEmpty) _ask(text: words, spoken: true);
      },
    );
    if (!started && mounted) {
      setState(() => _orb = OrbState.idle);
      snack(
        context,
        t('এই ফোনে কথা শোনার সুবিধা নেই। প্রশ্নটি লিখে পাঠান।', 'This phone has no speech recognition. Please type the question.'),
        icon: Icons.keyboard_rounded,
        tone: Tone.amber,
      );
      _typedFocus.requestFocus();
    }
  }

  Future<void> _sendTyped() async {
    final text = _typed.text.trim();
    if (text.isEmpty || _orb != OrbState.idle) return;
    if (!await ensureConsent(context)) return;
    _typed.clear();
    FocusManager.instance.primaryFocus?.unfocus();
    await _ask(text: text);
  }

  /// One question to the node. A farmer's own words are placed in their home district.
  Future<void> _ask({String? text, _Preset? preset, bool spoken = false}) async {
    if (preset != null) _place = preset;
    // Answering the node's follow-up question: send it together with the question it follows.
    if (text != null && _result?.needsClarification == true && _heard != null) text = '$_heard $text';
    final user = app.user;
    final cert = _cert;
    final body = <String, dynamic>{
      if (text != null) ...{
        'text': text,
        'district': _isFarmer && user!.district.isNotEmpty ? user.district : _place.district,
        if (!_isFarmer || _place.district == user!.district) 'upazila': _place.upazila,
      } else
        'preset_id': preset!.id,
      'offline_mode': app.offline,
      'session_id': 'KNX-APP-${math.Random().nextInt(0x7fffffff).toRadixString(36).toUpperCase().padLeft(6, '0')}',
      if (_isFarmer) 'farmer_id': user!.id,
      'edge_certificate_id': ?cert,
    };
    setState(() {
      _orb = OrbState.thinking;
      _heard = text ?? preset!.question;
      _speechNote = null;
    });
    HapticFeedback.lightImpact();
    try {
      final json = await Api.post('/edge/voice-interact', body, const Duration(seconds: 120));
      final result = VoiceResult((json as Map).cast<String, dynamic>());
      if (!mounted) return;
      setState(() {
        _result = result;
        // A recorded question shows what the node heard, with names and numbers already hidden.
        if (preset != null && result.scrubbedTranscript.isNotEmpty) _heard = result.scrubbedTranscript;
        _orb = OrbState.idle;
      });
      HapticFeedback.mediumImpact();
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final target = _answerKey.currentContext;
        if (target != null && target.mounted) {
          Scrollable.ensureVisible(
            target,
            duration: Motion.of(context, const Duration(milliseconds: 700)),
            curve: Motion.expo,
            alignment: 0.02,
          );
        }
      });
      if (spoken) _readAloud(result.needsClarification ? (result.followUp ?? result.spoken) : result.spoken);
    } catch (e) {
      if (!mounted) return;
      setState(() => _orb = OrbState.idle);
      snack(context, friendlyError(e), icon: Icons.error_outline_rounded, tone: Tone.rose);
    }
  }

  Future<void> _readAloud(String text, {bool bangla = true}) async {
    if (voice.speaking.value) {
      await voice.stopSpeaking();
      return;
    }
    setState(() => _speechNote = bangla && !app.offline ? t('বাংলা কণ্ঠ আনা হচ্ছে…', 'Getting the Bangla voice…') : null);
    final how = await voice.speak(text, bangla: bangla, online: !app.offline);
    if (!mounted) return;
    setState(
      () => _speechNote = switch (how) {
        Spoken.device => null,
        Spoken.online when !voice.speaking.value => null,
        Spoken.online => t(
          'অনলাইন বাংলা কণ্ঠে শোনানো হচ্ছে (ফোনে বাংলা কণ্ঠ নেই)।',
          'Playing the online Bangla voice (this phone has none).',
        ),
        Spoken.none =>
          app.offline
              ? t(
                  'অফলাইনে এই ফোনে বাংলা কণ্ঠ নেই; উত্তরটি লেখা আছে।',
                  'Offline, and this phone has no Bangla voice; the answer is written above.',
                )
              : t('বাংলা কণ্ঠ পাওয়া গেল না; উত্তরটি লেখা আছে।', 'The Bangla voice could not be reached; the answer is written above.'),
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(t('জিজ্ঞাসা', 'Ask')),
        actions: [
          ListenableBuilder(
            listenable: app,
            builder: (context, _) => IconButton(
              isSelected: app.offline,
              icon: const Icon(Icons.cloud_done_outlined),
              selectedIcon: Icon(Icons.cloud_off_rounded, color: Tone.amber.fg(context)),
              tooltip: app.offline ? t('অফলাইন এজ মোড চালু', 'Offline edge mode is on') : t('অফলাইন এজ মোড', 'Offline edge mode'),
              onPressed: () {
                app.setOffline(!app.offline);
                snack(
                  context,
                  app.offline ? t('অফলাইন এজ মোড চালু', 'Offline edge mode on') : t('আবার অনলাইন', 'Back online'),
                  icon: app.offline ? Icons.cloud_off_rounded : Icons.cloud_done_rounded,
                );
              },
            ),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(
            child: ListView(
              controller: _scroll,
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
              children: [
                Text(
                  _isFarmer
                      ? t('${app.user!.name}, কী জানতে চান?', '${app.user!.name}, what would you like to know?')
                      : t('কৃষকের মতো জিজ্ঞাসা করুন', 'Ask as a farmer would'),
                  style: theme.textTheme.headlineSmall,
                ),
                const SizedBox(height: 4),
                Text(
                  t(
                    'বিক্রি করবেন, হিমাগারে রাখবেন, না যৌথ ট্রাকে পাঠাবেন: নিজের ভাষায় বলুন।',
                    'Sell now, store, or send on a shared truck: say it in your own words and dialect.',
                  ),
                  style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
                _gradeChip(),
                const SizedBox(height: 8),
                Center(
                  child: MicOrb(
                    state: _orb,
                    level: voice.level,
                    onTap: _toggleMic,
                    label: _orb == OrbState.listening
                        ? t('শোনা বন্ধ করুন', 'Stop listening')
                        : t('বাংলায় প্রশ্ন বলুন', 'Speak your question in Bangla'),
                  ),
                ),
                Center(
                  child: AnimatedSwitcher(
                    duration: Motion.of(context, Motion.short),
                    child: Text(
                      key: ValueKey(_orb),
                      switch (_orb) {
                        OrbState.idle => t('ট্যাপ করে বাংলায় বলুন', 'Tap and speak in Bangla'),
                        OrbState.listening => t('শুনছি… শেষ হলে আবার ট্যাপ করুন', 'Listening… tap again when you finish'),
                        OrbState.thinking => t('এজেন্টরা হিসাব করছে…', 'The agents are working it out…'),
                      },
                      style: theme.textTheme.titleSmall?.copyWith(
                        color: _orb == OrbState.listening ? Tone.rose.fg(context) : theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                _transcript(),
                const SizedBox(height: 12),
                _typeRow(),
                SectionTitle(t('রেকর্ড করা প্রশ্ন শুনে দেখুন', 'Try a recorded question'), top: 22),
                SizedBox(
                  height: 128,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    clipBehavior: Clip.none,
                    itemCount: _presets.length,
                    separatorBuilder: (_, _) => const SizedBox(width: 10),
                    itemBuilder: (context, i) => _presetCard(_presets[i]),
                  ),
                ),
                if (_result != null && _orb != OrbState.thinking)
                  KeyedSubtree(
                    key: _answerKey,
                    child: _Answer(
                      result: _result!,
                      onRead: _readAloud,
                      note: _speechNote,
                      onAnswerFollowUp: _toggleMic,
                      heard: _heard ?? '',
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _gradeChip() => ListenableBuilder(
    listenable: app,
    builder: (context, _) {
      final certId = _cert;
      final grade = app.grades.where((g) => g.result.certId == certId).firstOrNull;
      if (certId == null || grade == null) return const SizedBox(height: 8);
      return Padding(
        padding: const EdgeInsets.only(top: 12),
        child: InputChip(
          avatar: const Icon(Icons.photo_camera_rounded, size: 18),
          label: Text(
            t(
              'গ্রেড যুক্ত: ${cropName(grade.result.crop)} · ${grade.result.grade}',
              'Grade attached: ${cropName(grade.result.crop)} · ${grade.result.grade}',
            ),
          ),
          onDeleted: () => setState(() {
            _detached = certId;
            app.askWithCert = null;
          }),
          deleteButtonTooltipMessage: t('বাদ দিন', 'Detach'),
        ),
      );
    },
  );

  Widget _transcript() {
    final theme = Theme.of(context);
    final showing = _orb == OrbState.listening ? _live : _heard;
    return AnimatedSize(
      duration: Motion.of(context, Motion.medium),
      curve: Motion.expo,
      alignment: Alignment.topCenter,
      child: showing == null || (showing.isEmpty && _orb != OrbState.listening)
          ? const SizedBox(width: double.infinity)
          : AppCard(
              tone: _orb == OrbState.listening ? Tone.rose : null,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _orb == OrbState.listening ? t('শুনছি', 'Hearing') : t('আপনার প্রশ্ন', 'Your question'),
                    style: theme.textTheme.labelMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    showing.isEmpty ? '…' : showing.replaceAll(RegExp(r'<[A-Z_]+_REDACTED>'), t('[লুকানো]', '[hidden]')),
                    style: voiceStyle(context, size: 20),
                  ),
                  if (_result != null && _orb == OrbState.idle) ...[
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        if (_result!.dialect.isNotEmpty) Pill(_result!.dialect, tone: Tone.violet, icon: Icons.record_voice_over_rounded),
                        if (_result!.intent.isNotEmpty) Pill(_sentence(_result!.intent), tone: Tone.sky),
                        if (_result!.quantityKg != null) Pill(kg(_result!.quantityKg!), tone: Tone.slate),
                        if (_result!.piiHidden > 0)
                          Pill(
                            t(
                              '${digits(_result!.piiHidden)}টি ব্যক্তিগত তথ্য লুকানো',
                              '${_result!.piiHidden} personal detail${_result!.piiHidden == 1 ? '' : 's'} hidden',
                            ),
                            tone: Tone.amber,
                            icon: Icons.visibility_off_rounded,
                          ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
    );
  }

  Widget _typeRow() => Row(
    children: [
      Expanded(
        child: TextField(
          controller: _typed,
          focusNode: _typedFocus,
          maxLength: 600,
          minLines: 1,
          maxLines: 3,
          textInputAction: TextInputAction.send,
          onSubmitted: (_) => _sendTyped(),
          style: voiceStyle(context, size: 17),
          decoration: InputDecoration(
            counterText: '',
            hintText: t('অথবা লিখুন: "১০ মণ আলু, ফড়িয়া ১২ টাকা বলছে"', 'Or type: "10 maund potatoes, the faria offers 12 taka"'),
          ),
        ),
      ),
      const SizedBox(width: 8),
      IconButton.filled(
        onPressed: _orb == OrbState.idle ? _sendTyped : null,
        icon: const Icon(Icons.send_rounded),
        tooltip: t('পাঠান', 'Send'),
        style: IconButton.styleFrom(minimumSize: const Size(52, 52)),
      ),
    ],
  );

  Widget _presetCard(_Preset p) {
    final theme = Theme.of(context);
    final active = _place.id == p.id && _result != null;
    return SizedBox(
      width: 232,
      child: AppCard(
        tone: active ? Tone.green : null,
        strong: active,
        padding: const EdgeInsets.all(14),
        onTap: _orb == OrbState.idle ? () => _ask(preset: p) : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.play_circle_fill_rounded, color: theme.colorScheme.primary, size: 20),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(t(p.titleBn, p.titleEn), maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.labelLarge),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Expanded(
              child: Text(p.question, maxLines: 2, overflow: TextOverflow.ellipsis, style: voiceStyle(context, size: 17)),
            ),
          ],
        ),
      ),
    );
  }
}

/// The agents' decision as cards: the flood alert, the middleman's offer (struck when the circuit breaker blocks it),
/// the recommended route with its money, the alternative, and the Bangla answer to listen to.
class _Answer extends StatelessWidget {
  const _Answer({required this.result, required this.onRead, required this.note, required this.onAnswerFollowUp, required this.heard});
  final VoiceResult result;
  final Future<void> Function(String text, {bool bangla}) onRead;
  final String? note;
  final VoidCallback onAnswerFollowUp;
  final String heard;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final r = result;
    if (r.needsClarification) {
      return Padding(
        padding: const EdgeInsets.only(top: 24),
        child: AppCard(
          tone: Tone.amber,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.help_rounded, color: Tone.amber.fg(context)),
                  const SizedBox(width: 8),
                  Text(t('আরেকটু জানা দরকার', 'A little more is needed'), style: theme.textTheme.titleMedium),
                ],
              ),
              const SizedBox(height: 8),
              Text(r.followUp ?? r.spoken, style: voiceStyle(context, size: 20)),
              const SizedBox(height: 12),
              Row(
                children: [
                  FilledButton.icon(
                    onPressed: onAnswerFollowUp,
                    icon: const Icon(Icons.mic_rounded),
                    label: Text(t('উত্তর বলুন', 'Answer by voice')),
                  ),
                  const SizedBox(width: 8),
                  _ListenButton(text: r.followUp ?? r.spoken, onRead: onRead),
                ],
              ),
              if (note != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(note!, style: theme.textTheme.bodySmall),
                ),
            ],
          ),
        ),
      );
    }
    final cold = r.cold;
    final breaker = r.breaker;
    final credit = r.credit;
    final syn = r.syndicate;
    final cards = <Widget>[
      if (r.floodAlert)
        _DecisionCard(
          tone: credit!['flood_alert_level'] == 'RED'
              ? Tone.rose
              : credit['flood_alert_level'] == 'GREEN'
              ? Tone.green
              : Tone.amber,
          icon: Icons.flood_rounded,
          title: t('হাওর বন্যার সতর্কতা', 'Haor flood alert'),
          value: pct(numOf(credit['flood_breach_probability_pct'])),
          detail: t(
            '৭২ ঘণ্টায় বাঁধ ভাঙার সম্ভাবনা · উপগ্রহ রাডার ${digits(numOf(credit['sar_backscatter_db']).toStringAsFixed(1))} dB',
            'Chance the embankment breaks within 72 hours · Sentinel-1 radar ${numOf(credit['sar_backscatter_db']).toStringAsFixed(1)} dB',
          ),
        ),
      if (r.offer != null && r.spotValue != null)
        _DecisionCard(
          tone: Tone.rose,
          icon: Icons.block_rounded,
          title: t('ফড়িয়ার দাম', 'The middleman\'s offer'),
          value: perKg(r.offer),
          struck: r.saleBlocked,
          detail: r.saleBlocked
              ? t(
                  'খরচের নিচে, তাই সার্কিট ব্রেকার এই বিক্রি আটকে দিয়েছে (খরচ ${perKg(numOf(breaker?['production_cost_floor_bdt']))})। মোট মাত্র ${money(r.spotValue)}।',
                  'Below the ${perKg(numOf(breaker?['production_cost_floor_bdt']))} production cost, so the circuit breaker blocks this sale. Worth only ${money(r.spotValue)}.',
                )
              : t(
                  'খরচের উপরে; ${kg(r.qty)}-এর দাম ${money(r.spotValue)}।',
                  'Above the cost floor; ${money(r.spotValue)} for ${kg(r.qty)}.',
                ),
        ),
      if (syn != null && r.pooledValue != null && !r.storeFirst) _TruckCard(result: r),
      if (breaker != null && r.storeValue != null)
        _DecisionCard(
          tone: r.storeFirst ? Tone.green : Tone.sky,
          recommended: r.storeFirst,
          icon: Icons.ac_unit_rounded,
          title: t(
            '${digits(numOf(cold!['horizon_days']).toInt())} দিন হিমাগারে রাখুন',
            '${numOf(cold['horizon_days']).toInt()}-day cold storage',
          ),
          value: money(r.storeValue),
          detail: [
            if (mapOf(cold['facility']) != null)
              '${mapOf(cold['facility'])!['name']} · ${t('ভাড়া', 'tariff')} ${perKg(numOf(mapOf(cold['facility'])!['tariff_tk_per_kg']))}',
            '${t('প্রত্যাশিত দাম', 'expected price')} ${perKg(numOrNull(cold['expected_future_price_tk_per_kg']))}',
            '${t('ফড়িয়ার চেয়ে', 'vs the middleman')} ${money(numOf(breaker['delta_pi_bdt']))}',
          ].join(' · '),
          footer: r.loanEligible
              ? Pill(
                  t(
                    '${money(numOf(credit!['loan_amount_tk']))} কৃষি ঋণ ${digits(numOf(credit['annual_rate_pct']))}% · স্কোর ${digits(numOf(credit['credit_score']).toInt())}',
                    '${money(numOf(credit['loan_amount_tk']))} working capital at ${numOf(credit['annual_rate_pct'])}% · score ${numOf(credit['credit_score']).toInt()}',
                  ),
                  tone: Tone.violet,
                  icon: Icons.account_balance_rounded,
                )
              : null,
        ),
      if (syn != null && r.pooledValue != null && r.storeFirst)
        _DecisionCard(
          tone: Tone.sky,
          icon: Icons.local_shipping_rounded,
          title: t('৫ টনের যৌথ ট্রাক', '5-ton pooled truck'),
          value: money(r.pooledValue),
          detail: t(
            '${perKg(numOf(syn['b2b_net_tk_per_kg']))} নিট, ${syn['best_hub_name']}-এ',
            '${perKg(numOf(syn['b2b_net_tk_per_kg']))} net to ${syn['best_hub_name']}',
          ),
        ),
      if (breaker == null && r.loanEligible)
        Pill(
          t(
            'ক্রেডিট স্কোর ${digits(numOf(credit!['credit_score']).toInt())}: ${money(numOf(credit['loan_amount_tk']))} ঋণ আগেই অনুমোদিত',
            'Credit score ${numOf(credit['credit_score']).toInt()}: ${money(numOf(credit['loan_amount_tk']))} pre-approved',
          ),
          tone: Tone.violet,
          icon: Icons.account_balance_rounded,
        ),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionTitle(t('আপনার সিদ্ধান্ত', 'Your decision'), top: 28),
        for (var i = 0; i < cards.length; i++)
          _Rise(
            order: i,
            child: Padding(padding: const EdgeInsets.only(bottom: 12), child: cards[i]),
          ),
        _Rise(
          order: cards.length,
          child: AppCard(
            tone: Tone.green,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(r.spoken, style: voiceStyle(context, size: 19)),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _ListenButton(text: r.spoken, onRead: onRead),
                    OutlinedButton.icon(
                      onPressed: () => onRead(_englishSummary(r), bangla: false),
                      icon: const Icon(Icons.translate_rounded),
                      label: const Text('English'),
                    ),
                  ],
                ),
                if (note != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(note!, style: theme.textTheme.bodySmall),
                  ),
              ],
            ),
          ),
        ),
        if (app.user?.role == 'farmer' && r.crop.isNotEmpty && marketCrops.contains(r.crop)) ...[
          const SizedBox(height: 12),
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: theme.colorScheme.secondary, foregroundColor: theme.colorScheme.onSecondary),
            onPressed: () => app.sellLot({
              'crop': r.crop,
              'weight_kg': r.qty,
              'grade': r.marketGrade,
              'district': r.district,
              'upazila': r.upazila,
              'certificate_id': ?r.qualityCert?['edge_certificate_id'],
            }),
            icon: const Icon(Icons.storefront_rounded),
            label: Text(t('সরাসরি ক্রেতাদের কাছে বেচুন', 'Sell directly to buyers')),
          ),
        ],
        const SizedBox(height: 12),
        _HowDecided(result: r),
        const SizedBox(height: 12),
        _Feedback(key: ValueKey(r.sessionId), sessionId: r.sessionId),
      ],
    );
  }
}

String _englishSummary(VoiceResult r) {
  final cert = r.qualityCert;
  final syn = r.syndicate;
  final credit = r.credit;
  return [
    if (cert != null) 'Your ${r.qty.toStringAsFixed(0)} kilograms of ${r.crop} are certified ${cert['grade']}.',
    if (r.saleBlocked) 'The middleman offer of ${r.offer} taka per kilo is below the production cost, so that sale is blocked.',
    if (syn != null)
      'A pooled five-ton truck to ${syn['best_hub_name']} pays ${numOf(syn['b2b_net_tk_per_kg']).toStringAsFixed(2)} taka per kilo.',
    if (r.floodAlert)
      'The chance of an embankment breach in the next 72 hours is ${numOf(credit!['flood_breach_probability_pct']).toStringAsFixed(1)} percent.',
    if (r.loanEligible)
      'Your agri-credit score is ${numOf(credit!['credit_score']).toInt()}; up to ${numOf(credit['loan_amount_tk']).toInt()} taka working capital is pre-approved.',
  ].join(' ');
}

class _ListenButton extends StatelessWidget {
  const _ListenButton({required this.text, required this.onRead});
  final String text;
  final Future<void> Function(String text, {bool bangla}) onRead;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
    valueListenable: voice.speaking,
    builder: (context, speaking, _) => FilledButton.tonalIcon(
      onPressed: () => onRead(text),
      icon: Icon(speaking ? Icons.stop_rounded : Icons.volume_up_rounded),
      label: Text(speaking ? t('থামান', 'Stop') : t('শুনুন', 'Listen')),
    ),
  );
}

/// Cards rise into place one after another (at once with animations off).
class _Rise extends StatelessWidget {
  const _Rise({required this.order, required this.child});
  final int order;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (Motion.reduced(context)) return child;
    final delay = order * 90;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 520 + delay),
      curve: Interval(delay / (520 + delay), 1, curve: Motion.expo),
      builder: (_, v, child) => Opacity(
        opacity: v,
        child: Transform.translate(offset: Offset(0, 18 * (1 - v)), child: child),
      ),
      child: child,
    );
  }
}

class _DecisionCard extends StatelessWidget {
  const _DecisionCard({
    required this.tone,
    required this.icon,
    required this.title,
    required this.value,
    required this.detail,
    this.struck = false,
    this.recommended = false,
    this.footer,
  });
  final Tone tone;
  final IconData icon;
  final String title;
  final String value;
  final String detail;
  final bool struck;
  final bool recommended;
  final Widget? footer;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final fg = tone.fg(context);
    return AppCard(
      tone: tone,
      strong: recommended,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: fg),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: theme.textTheme.titleSmall),
                    if (recommended) ...[
                      const SizedBox(height: 4),
                      Pill(t('পরামর্শ', 'Recommended'), tone: Tone.green, icon: Icons.thumb_up_alt_rounded),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                value,
                style: theme.textTheme.titleLarge?.copyWith(
                  color: fg,
                  fontFeatures: tabular,
                  decoration: struck ? TextDecoration.lineThrough : null,
                  decorationThickness: 2.5,
                  decorationColor: fg,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(detail, style: theme.textTheme.bodyMedium),
          if (footer != null) ...[const SizedBox(height: 10), footer!],
        ],
      ),
    );
  }
}

/// The recommended route: a five-ton truck shared with neighbours, with a one-tap join.
class _TruckCard extends StatefulWidget {
  const _TruckCard({required this.result});
  final VoiceResult result;

  @override
  State<_TruckCard> createState() => _TruckCardState();
}

class _TruckCardState extends State<_TruckCard> {
  bool _busy = false;
  String? _joined;
  Map<String, dynamic>? _pool;

  Future<void> _join() async {
    final r = widget.result;
    final pool = r.pool!;
    setState(() => _busy = true);
    final res = await guarded(
      context,
      () => Api.post('/automation/truck-pools/join', {
        'cluster_id': pool['pool_id'],
        'farmer_id': r.farmerId,
        'crop': r.crop,
        'weight_kg': r.qty,
        'grade': 'Grade-${r.marketGrade}',
      }),
    );
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (res is Map) {
        _joined = res['message'] as String? ?? '';
        _pool = mapOf(res['pool']);
        HapticFeedback.heavyImpact();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.result;
    final syn = r.syndicate!;
    final pool = r.pool;
    final theme = Theme.of(context);
    const onGreen = Colors.white;
    final capacity = numOf(_pool?['capacity_kg'] ?? pool?['capacity_kg']);
    final after = numOf(_pool?['loaded_kg'] ?? pool?['after_join_kg']);
    final dispatched = (_pool?['status'] ?? '') == 'DISPATCHED';
    return Container(
      decoration: BoxDecoration(
        color: Brand.green,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [BoxShadow(color: Brand.green.withValues(alpha: 0.28), blurRadius: 24, offset: const Offset(0, 10))],
      ),
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.local_shipping_rounded, color: Color(0xFFD1FAE5), size: 20),
              const SizedBox(width: 6),
              Text(
                t('পরামর্শ · ৫ টনের যৌথ ট্রাক', 'Recommended · 5-ton pooled truck'),
                style: theme.textTheme.labelLarge?.copyWith(color: const Color(0xFFD1FAE5)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          CountUp(
            value: r.pooledValue!,
            format: (v) => money(v),
            style: theme.textTheme.displaySmall?.copyWith(color: onGreen, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            t(
              '${perKg(numOf(syn['b2b_net_tk_per_kg']))} নিট ${syn['best_hub_name']}-এ, ভাড়া ${perKg(numOf(syn['pooled_transport_tk_per_kg']))} বাদে',
              '${perKg(numOf(syn['b2b_net_tk_per_kg']))} net to ${syn['best_hub_name']}, after ${perKg(numOf(syn['pooled_transport_tk_per_kg']))} freight',
            ),
            style: theme.textTheme.bodyMedium?.copyWith(color: const Color(0xFFECFDF5)),
          ),
          if (pool != null && capacity > 0) ...[
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: Text(
                    t(
                      '${digits(numOf(pool['neighbor_farmers']).toInt())} জন প্রতিবেশী তুলছেন',
                      '${numOf(pool['neighbor_farmers']).toInt()} neighbours loading',
                    ),
                    style: theme.textTheme.bodySmall?.copyWith(color: const Color(0xFFD1FAE5)),
                  ),
                ),
                Text(
                  '${kg(after)} / ${kg(capacity)}',
                  style: theme.textTheme.bodySmall?.copyWith(color: const Color(0xFFD1FAE5), fontFeatures: tabular),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: (after / capacity).clamp(0, 1)),
                duration: Motion.of(context, Motion.long),
                curve: Motion.expo,
                builder: (_, v, _) =>
                    LinearProgressIndicator(value: v, minHeight: 10, color: Brand.mustard, backgroundColor: const Color(0xFF064E3B)),
              ),
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: Colors.white, foregroundColor: Brand.greenDeep),
                onPressed: _busy || _joined != null || r.farmerId.isEmpty ? null : _join,
                icon: _busy
                    ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : Icon(_joined != null ? Icons.check_circle_rounded : Icons.add_task_rounded),
                label: Text(
                  _joined != null
                      ? (dispatched ? t('ট্রাক রওনা হচ্ছে', 'Truck dispatched') : t('ট্রাকে যুক্ত হয়েছে', 'Joined the truck'))
                      : t('হ্যাঁ, ট্রাকে যুক্ত করুন', 'Yes, join this truck'),
                ),
              ),
            ),
            if (_joined != null) ...[
              const SizedBox(height: 8),
              Text(_joined!, style: theme.textTheme.bodySmall?.copyWith(color: const Color(0xFFECFDF5))),
            ],
          ],
        ],
      ),
    );
  }
}

/// The path the agents took, read from the node's own orchestration record.
class _HowDecided extends StatelessWidget {
  const _HowDecided({required this.result});
  final VoiceResult result;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final path = result.graphPath;
    if (path.isEmpty) return const SizedBox.shrink();
    return AppCard(
      padding: EdgeInsets.zero,
      child: Theme(
        data: theme.copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          shape: const Border(),
          leading: const Icon(Icons.account_tree_rounded),
          title: Text(t('এজেন্টরা কীভাবে ঠিক করল', 'How the agents decided'), style: theme.textTheme.titleSmall),
          subtitle: Text(
            t(
              '${digits(path.length)} ধাপ · ${digits((result.latencyMs / 1000).toStringAsFixed(1))} সেকেন্ড',
              '${path.length} steps · ${(result.latencyMs / 1000).toStringAsFixed(1)} s',
            ),
            style: theme.textTheme.bodySmall,
          ),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          children: [
            for (var i = 0; i < path.length; i++)
              Row(
                children: [
                  Column(
                    children: [
                      Container(width: 2, height: 8, color: i == 0 ? Colors.transparent : theme.colorScheme.outlineVariant),
                      Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(color: theme.colorScheme.primary, shape: BoxShape.circle),
                      ),
                      Container(width: 2, height: 8, color: i == path.length - 1 ? Colors.transparent : theme.colorScheme.outlineVariant),
                    ],
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Text(_humanize(path[i]), style: theme.textTheme.bodyMedium)),
                ],
              ),
          ],
        ),
      ),
    );
  }

  static String _humanize(String node) {
    final words = node.replaceAll(RegExp(r'[_\-]+'), ' ').trim();
    return words.isEmpty ? node : words[0].toUpperCase() + words.substring(1);
  }
}

/// "Was this advice useful?" (POST /feedback; the comment is scrubbed of personal details on the node).
class _Feedback extends StatefulWidget {
  const _Feedback({super.key, required this.sessionId});
  final String sessionId;

  @override
  State<_Feedback> createState() => _FeedbackState();
}

class _FeedbackState extends State<_Feedback> {
  bool? _useful;
  final _comment = TextEditingController();
  bool _sending = false;
  bool _sent = false;

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() => _sending = true);
    final ok = await guarded(
      context,
      () => Api.post('/feedback', {
        'useful': _useful,
        if (_comment.text.trim().isNotEmpty) 'comment': _comment.text.trim(),
        if (widget.sessionId.isNotEmpty) 'session_id': widget.sessionId,
        'lang': app.lang,
        'context': 'farmer_decision',
      }),
    );
    if (mounted) {
      setState(() {
        _sending = false;
        _sent = ok != null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_sent) {
      return AppCard(
        child: Row(
          children: [
            Icon(Icons.favorite_rounded, color: Tone.green.fg(context)),
            const SizedBox(width: 10),
            Expanded(child: Text(t('ধন্যবাদ! আপনার মতামত আমাদের উন্নত করে।', 'Thank you, your answer helps us improve.'))),
          ],
        ),
      );
    }
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(t('পরামর্শটি কি কাজে লাগল?', 'Was this advice useful?'), style: theme.textTheme.titleSmall),
          const SizedBox(height: 10),
          SegmentedButton<bool>(
            emptySelectionAllowed: true,
            segments: [
              ButtonSegment(value: true, icon: const Icon(Icons.thumb_up_alt_rounded), label: Text(t('হ্যাঁ', 'Yes'))),
              ButtonSegment(value: false, icon: const Icon(Icons.thumb_down_alt_rounded), label: Text(t('না', 'No'))),
            ],
            selected: {?_useful},
            onSelectionChanged: (s) => setState(() => _useful = s.firstOrNull),
          ),
          AnimatedSize(
            duration: Motion.of(context, Motion.medium),
            curve: Motion.expo,
            child: _useful == null
                ? const SizedBox(width: double.infinity)
                : Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Column(
                      children: [
                        TextField(
                          controller: _comment,
                          maxLength: 500,
                          maxLines: 2,
                          decoration: InputDecoration(hintText: t('কিছু বলতে চাইলে লিখুন (ঐচ্ছিক)', 'Anything to add? (optional)')),
                        ),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton(onPressed: _sending ? null : _send, child: Text(t('পাঠান', 'Send'))),
                        ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

String _sentence(String code) {
  final words = code.replaceAll('_', ' ').toLowerCase().trim();
  return words.isEmpty ? code : words[0].toUpperCase() + words.substring(1);
}
