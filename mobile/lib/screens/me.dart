import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../core/voice.dart';
import '../widgets/common.dart';
import 'guide.dart';
import 'login.dart' show roleIcon;
import 'market.dart' show Polling;
import 'scan.dart' show fadeRoute;
import 'team.dart';

/// The account, language, theme, offline mode, voice checks, privacy and the server this app talks to.
class MeScreen extends StatelessWidget {
  const MeScreen({super.key});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: app,
        builder: (context, _) {
          final theme = Theme.of(context);
          final user = app.user;
          if (user == null) return const SizedBox.shrink(); // signed out, fading away
          return Scaffold(
            appBar: AppBar(title: Text(t('আমি', 'Me'))),
            body: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 40), children: [
              AppCard(
                child: Row(children: [
                  CircleAvatar(
                    radius: 30,
                    backgroundColor: theme.colorScheme.primaryContainer,
                    child: Icon(roleIcon(user.role), size: 30, color: theme.colorScheme.onPrimaryContainer),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(user.name, style: theme.textTheme.titleLarge),
                      Text([roleName(user.role), if (user.district.isNotEmpty) user.district].join(' · '), style: theme.textTheme.bodyMedium),
                      if (user.title.isNotEmpty)
                        Text(user.title, style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                    ]),
                  ),
                ]),
              ),
              if (user.kyc != null) _KycCard(user: user),
              SectionTitle(t('অ্যাপ', 'App')),
              AppCard(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Column(children: [
                  _Row(
                    icon: Icons.translate_rounded,
                    title: t('ভাষা', 'Language'),
                    trailing: SegmentedButton<String>(
                      showSelectedIcon: false,
                      segments: const [ButtonSegment(value: 'bn', label: Text('বাংলা')), ButtonSegment(value: 'en', label: Text('English'))],
                      selected: {app.lang},
                      onSelectionChanged: (s) => app.setLang(s.first),
                    ),
                  ),
                  _Row(
                    icon: Icons.contrast_rounded,
                    title: t('রং', 'Theme'),
                    trailing: SegmentedButton<ThemeMode>(
                      showSelectedIcon: false,
                      segments: [
                        ButtonSegment(value: ThemeMode.system, icon: const Icon(Icons.brightness_auto_rounded), tooltip: t('ফোনের মতো', 'Follow the phone')),
                        ButtonSegment(value: ThemeMode.light, icon: const Icon(Icons.light_mode_rounded), tooltip: t('দিনের', 'Light')),
                        ButtonSegment(value: ThemeMode.dark, icon: const Icon(Icons.dark_mode_rounded), tooltip: t('রাতের', 'Dark')),
                      ],
                      selected: {app.themeMode},
                      onSelectionChanged: (s) => app.setTheme(s.first),
                    ),
                  ),
                  SwitchListTile(
                    secondary: const Icon(Icons.cloud_off_rounded),
                    title: Text(t('অফলাইন এজ মোড', 'Offline edge mode')),
                    subtitle: Text(t('উত্তর কিয়স্কের নিজস্ব মডেল থেকে; অনলাইন কণ্ঠ বন্ধ থাকে।', 'Answers from the kiosk\'s own model; the online voice stays off.')),
                    value: app.offline,
                    onChanged: app.setOffline,
                  ),
                ]),
              ),
              SectionTitle(t('কণ্ঠ', 'Voice')),
              const _VoiceChecks(),
              SectionTitle(t('গোপনীয়তা', 'Privacy')),
              AppCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  for (final line in [
                    t('প্রশ্ন শোনে ফোনের নিজস্ব কথা-চেনার সেবা; নোডে যায় শুধু লেখা।', 'The phone\'s own speech service hears your question; only the words go to the node.'),
                    t('নাম, ফোন ও এনআইডি নম্বর লুকানো হয় এবং ২৪ ঘণ্টায় মুছে যায়।', 'Names, phone and NID numbers are hidden and erased within 24 hours.'),
                    t('ছবি গ্রেড করতে নোডে যায়, জমা রাখা হয় না; সনদে থাকে শুধু মাপজোখ।', 'Photos go to the node for grading and are not kept; the certificate holds only the measurements.'),
                    t('ফোনে বাংলা কণ্ঠ না থাকলে উত্তরের লেখা (ব্যক্তিগত তথ্য ছাড়া) Google বা Microsoft-এর কণ্ঠে পড়ানো হয়; অফলাইনে কখনো না।',
                        'Without a Bangla voice on the phone, the answer text (personal details removed) is read by Google\'s or Microsoft\'s voice; never offline.'),
                  ])
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 5),
                      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Padding(padding: const EdgeInsets.only(top: 3), child: Icon(Icons.shield_outlined, size: 18, color: Tone.sky.fg(context))),
                        const SizedBox(width: 10),
                        Expanded(child: Text(line, style: theme.textTheme.bodyMedium)),
                      ]),
                    ),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                      child: Text(app.consent ? t('আপনি সম্মতি দিয়েছেন', 'You have given consent') : t('সম্মতি দেওয়া হয়নি', 'No consent given'),
                          style: theme.textTheme.titleSmall),
                    ),
                    if (app.consent) TextButton(onPressed: app.withdrawConsent, child: Text(t('প্রত্যাহার', 'Withdraw'))),
                  ]),
                ]),
              ),
              SectionTitle(t('সার্ভার', 'Server')),
              AppCard(
                padding: EdgeInsets.zero,
                child: Column(children: [
                  ListTile(
                    leading: const Icon(Icons.dns_rounded),
                    title: Text(Api.base.replaceFirst(RegExp('^https?://'), '')),
                    subtitle: Text(t('গ্রামের কিয়স্ক বা ল্যাপটপের নোডেও যুক্ত করা যায়', 'Point the app at a village kiosk or a laptop node')),
                    trailing: const Icon(Icons.edit_rounded),
                    onTap: () => _editServer(context),
                  ),
                  ListTile(
                    leading: const Icon(Icons.open_in_new_rounded),
                    title: Text(t('ওয়েবসাইট ও ডকুমেন্টেশন', 'Website and documentation')),
                    onTap: () => openWeb(context, '/docs'),
                  ),
                ]),
              ),
              SectionTitle(t('সাহায্য', 'Help')),
              AppCard(
                padding: EdgeInsets.zero,
                child: Column(children: [
                  ListTile(
                    leading: const Icon(Icons.menu_book_rounded),
                    title: Text(t('কৃষিনেক্সাস কীভাবে ব্যবহার করবেন', 'How to use KrishiNexus')),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => Navigator.of(context).push(fadeRoute(const GuideScreen())),
                  ),
                  ListTile(
                    leading: const Icon(Icons.groups_rounded),
                    title: Text(t('টিম হিট ওয়েভ', 'Team Heat Wave')),
                    subtitle: Text(t('কৃষিনেক্সাস যাঁরা বানিয়েছেন', 'The people who build KrishiNexus')),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => Navigator.of(context).push(fadeRoute(const TeamScreen())),
                  ),
                ]),
              ),
              const SizedBox(height: 24),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(foregroundColor: theme.colorScheme.error, side: BorderSide(color: theme.colorScheme.error.withValues(alpha: 0.5))),
                onPressed: () => app.logout(),
                icon: const Icon(Icons.logout_rounded),
                label: Text(t('লগআউট', 'Log out')),
              ),
              const SizedBox(height: 16),
              Center(child: Text('KrishiNexus 1.1.0', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant))),
            ]),
          );
        },
      );

  Future<void> _editServer(BuildContext context) async {
    final controller = TextEditingController(text: Api.base);
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t('সার্ভারের ঠিকানা', 'Server address')),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(hintText: 'https://tanvir.health'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, Api.defaultBase), child: Text(t('আগের মতো', 'Reset'))),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: Text(t('রাখুন', 'Save'))),
        ],
      ),
    );
    controller.dispose();
    if (value == null || value.isEmpty) return;
    final url = value.replaceAll(RegExp(r'/+$'), '');
    if (Uri.tryParse(url)?.hasScheme != true) {
      if (context.mounted) snack(context, t('পুরো ঠিকানা দিন, যেমন https://…', 'Enter a full address, like https://…'), tone: Tone.amber);
      return;
    }
    app.setServer(url);
    // Another node does not know this session: sign in there again.
    await app.logout();
  }
}

/// A signed-up account's registered details, masked as the node keeps them (the full numbers only as hashes).
class _KycCard extends StatelessWidget {
  const _KycCard({required this.user});
  final User user;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final kyc = user.kyc!;
    final (label, tone) = kyc.verified
        ? (t('যাচাই করা', 'Verified'), Tone.green)
        : user.pendingReview
            ? (t('অনুমোদনের অপেক্ষায়', 'Awaiting approval'), Tone.amber)
            : (t('এখনো যাচাই হয়নি', 'Not verified yet'), Tone.slate);
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(t('নিবন্ধনের তথ্য', 'Registered details'), style: theme.textTheme.titleSmall)),
            Pill(label, tone: tone, icon: kyc.verified ? Icons.verified_rounded : Icons.hourglass_top_rounded),
          ]),
          const SizedBox(height: 6),
          InfoRow(t('অ্যাকাউন্ট আইডি', 'Account ID'), user.id, mono: true),
          InfoRow(t('ফোন', 'Phone'), digits(kyc.phoneMasked)),
          InfoRow(t('জাতীয় পরিচয়পত্র', 'National ID'), '…${digits(kyc.nidLast4)}'),
          InfoRow(t('টাকা পাওয়ার ওয়ালেট', 'Payout wallet'), '${kyc.walletProvider} ${digits(kyc.walletMasked)}'),
          if (kyc.registeredAt.isNotEmpty) InfoRow(t('নিবন্ধন', 'Registered'), ago(kyc.registeredAt)),
          const SizedBox(height: 4),
          Text(
            t('পুরো নম্বরগুলো শুধু হ্যাশ করে রাখা হয়, তাই এখানে শেষ অঙ্কগুলোই দেখা যায়। লগইন করতে অ্যাকাউন্ট আইডি ও পাসওয়ার্ড লাগে।',
                'The full numbers are kept only as hashes, so only their last digits show here. You log in with the account ID and your password.'),
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ]),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.icon, required this.title, required this.trailing});
  final IconData icon;
  final String title;
  final Widget trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(children: [
          Icon(icon, color: Theme.of(context).colorScheme.onSurfaceVariant),
          const SizedBox(width: 16),
          Expanded(child: Text(title, style: Theme.of(context).textTheme.bodyLarge)),
          trailing,
        ]),
      );
}

class _VoiceChecks extends StatefulWidget {
  const _VoiceChecks();

  @override
  State<_VoiceChecks> createState() => _VoiceChecksState();
}

class _VoiceChecksState extends State<_VoiceChecks> {
  String? _speak;
  String? _listen;

  Future<void> _testSpeak() async {
    setState(() => _speak = t('চলছে…', 'Playing…'));
    final how = await voice.speak('আমি কৃষিনেক্সাস। ন্যায্য দাম পেতে আপনার পাশে আছি।', online: !app.offline);
    if (!mounted) return;
    setState(() => _speak = switch (how) {
          Spoken.device => t('ফোনের নিজস্ব বাংলা কণ্ঠ', 'The phone\'s own Bangla voice'),
          Spoken.online => t('অনলাইন বাংলা কণ্ঠ (ফোনে বাংলা কণ্ঠ নেই)', 'The online Bangla voice (the phone has none)'),
          Spoken.none => t('বাংলা কণ্ঠ পাওয়া যায়নি', 'No Bangla voice available'),
        });
  }

  Future<void> _testListen() async {
    final ok = await voice.available();
    if (mounted) {
      setState(() => _listen = ok
          ? t('কথা চেনা যাবে (বাংলা, bn-BD)', 'Speech recognition is available (Bangla, bn-BD)')
          : t('এই ফোনে কথা চেনার সেবা নেই; লিখে প্রশ্ন করুন', 'No speech recognition on this phone; type your questions'));
    }
  }

  @override
  Widget build(BuildContext context) => AppCard(
        padding: EdgeInsets.zero,
        child: Column(children: [
          ListTile(
            leading: const Icon(Icons.record_voice_over_rounded),
            title: Text(t('বাংলা কণ্ঠ পরীক্ষা', 'Test the Bangla voice')),
            subtitle: _speak == null ? null : Text(_speak!),
            trailing: const Icon(Icons.play_arrow_rounded),
            onTap: _testSpeak,
          ),
          ListTile(
            leading: const Icon(Icons.mic_rounded),
            title: Text(t('কথা চেনা পরীক্ষা', 'Check speech recognition')),
            subtitle: _listen == null ? null : Text(_listen!),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: _testListen,
          ),
        ]),
      );
}

/// Co-op and cold-storage roles: the live picture from the node, and their full desk on the website.
class DeskScreen extends StatefulWidget {
  const DeskScreen({super.key});

  @override
  State<DeskScreen> createState() => _DeskScreenState();
}

class _DeskScreenState extends State<DeskScreen> with Polling<DeskScreen, List<Map<String, dynamic>>> {
  bool get _coop => app.user?.role == 'coop';

  // Truck pools and chamber alerts change outside the market feed: keep polling them.
  @override
  bool get followsMarket => false;

  @override
  Future<List<Map<String, dynamic>>> load() async => mapsOf(await Api.get(_coop ? '/automation/truck-pools' : '/mcp/anomalies'));

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final rows = data ?? const <Map<String, dynamic>>[];
    return Scaffold(
      appBar: AppBar(title: Text(_coop ? t('সমবায় ডেস্ক', 'Co-op desk') : t('হিমাগার ডেস্ক', 'Cold-storage desk'))),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 32), children: [
          AppCard(
            tone: Tone.sky,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(
                _coop
                    ? t('কৃষকদের ছোট লট মিলিয়ে ৫ টনের ট্রাক ভরে, ভরলেই ট্রাক রওনা হয়।', 'Smallholders\' lots pool into 5-ton trucks; a full truck dispatches itself.')
                    : t('চেম্বারের তাপমাত্রা, বিদ্যুৎ বিভ্রাট ও বন্যার মহড়া চলে ওয়েব ডেস্কে।', 'Chamber telemetry, power-cut and flood drills run on the web desk.'),
                style: theme.textTheme.bodyLarge,
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: () => openWeb(context, _coop ? '/os/coop' : '/os/himagar'),
                icon: const Icon(Icons.open_in_new_rounded),
                label: Text(t('পুরো ডেস্ক খুলুন', 'Open the full desk')),
              ),
            ]),
          ),
          SectionTitle(_coop ? t('ট্রাক পুল', 'Truck pools') : t('চলমান সতর্কতা', 'Active alerts')),
          if (loading && data == null)
            const SizedBox(height: 200, child: SkeletonList(count: 2, height: 80))
          else if (error != null && data == null)
            ErrorState(error: error!, onRetry: refresh)
          else if (rows.isEmpty)
            AppCard(child: Text(_coop ? t('কোনো ট্রাক পুল নেই।', 'No truck pools.') : t('এখন কোনো সতর্কতা নেই।', 'No active alerts.')))
          else
            for (final r in rows) ...[
              _coop ? _PoolCard(pool: r) : _AlertCard(alert: r),
              const SizedBox(height: 10),
            ],
        ]),
      ),
    );
  }
}

class _PoolCard extends StatelessWidget {
  const _PoolCard({required this.pool});
  final Map<String, dynamic> pool;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dispatched = pool['status'] == 'DISPATCHED';
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('${cropName('${pool['crop']}')} · ${pool['upazila']}, ${pool['district']}', style: theme.textTheme.titleSmall)),
          Pill(dispatched ? t('রওনা হয়েছে', 'Dispatched') : t('ভরছে', 'Filling'), tone: dispatched ? Tone.green : Tone.amber),
        ]),
        const SizedBox(height: 4),
        MeterRow(
          label: t('${digits(numOf(pool['smallholders']).toInt())} জন কৃষক', '${numOf(pool['smallholders']).toInt()} smallholders'),
          value: numOf(pool['loaded_kg']),
          max: numOf(pool['capacity_kg']) <= 0 ? 1 : numOf(pool['capacity_kg']),
          display: '${kg(numOf(pool['loaded_kg']))} / ${kg(numOf(pool['capacity_kg']))}',
          tone: dispatched ? Tone.green : Tone.amber,
        ),
      ]),
    );
  }
}

class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.alert});
  final Map<String, dynamic> alert;

  @override
  Widget build(BuildContext context) {
    final flood = alert['anomaly_type'] == 'haor_flash_flood';
    return AppCard(
      tone: Tone.rose,
      child: Row(children: [
        Icon(flood ? Icons.flood_rounded : Icons.power_off_rounded, color: Tone.rose.fg(context)),
        const SizedBox(width: 10),
        Expanded(
          child: Text('${flood ? t('হাওরে আকস্মিক বন্যা', 'Haor flash flood') : t('চেম্বারে বিদ্যুৎ নেই', 'Chamber power cut')} · ${alert['target']}',
              style: Theme.of(context).textTheme.titleSmall),
        ),
      ]),
    );
  }
}
