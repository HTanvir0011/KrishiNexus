import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'guide.dart';
import 'scan.dart' show fadeRoute;
import 'signup.dart';
import 'team.dart';

IconData roleIcon(String role) => switch (role) {
      'farmer' => Icons.agriculture_rounded,
      'buyer' => Icons.storefront_rounded,
      'driver' => Icons.local_shipping_rounded,
      'coop' => Icons.groups_rounded,
      'storage' => Icons.ac_unit_rounded,
      'bank' => Icons.account_balance_rounded,
      'judge' => Icons.gavel_rounded,
      'admin' => Icons.admin_panel_settings_rounded,
      _ => Icons.person_rounded,
    };

/// Pick an account: one tap signs in on the demo node (quick login); a password is needed where the node asks.
/// New people create an account; a signed-up account logs in with its account ID and password.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late Future<List<User>> _users = _load();
  String? _busy;

  Future<List<User>> _load() async =>
      ((await Api.get('/auth/demo-users')) as List).map((u) => User((u as Map).cast<String, dynamic>())).where((u) => u.active).toList();

  Future<void> _signIn(String id, {String? password, User? user}) async {
    setState(() => _busy = id);
    try {
      final session = await Api.post('/auth/login', {'user_id': id, 'password': ?password});
      await app.signIn((session as Map).cast<String, dynamic>());
    } on ApiError catch (e) {
      if (!mounted) return;
      if (e.status == 401 && password == null) {
        _askPassword(user);
      } else {
        final message = switch (e.status) {
          401 => t('অ্যাকাউন্ট আইডি বা পাসওয়ার্ড মেলেনি।', 'The account ID or the password is wrong.'),
          403 when e.message.contains('waiting') =>
            t('অ্যাকাউন্টটি এখনো অ্যাডমিনের অনুমোদনের অপেক্ষায়। অনুমোদন হলে লগইন করা যাবে।', 'This account is still waiting for an admin to approve it.'),
          403 => t('এই অ্যাকাউন্ট নেই বা বন্ধ করা আছে।', 'That account does not exist or is disabled.'),
          _ => friendlyError(e),
        };
        snack(context, message, icon: Icons.error_outline_rounded, tone: Tone.rose);
      }
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  /// The password for a listed account, or (no [user]) an account ID and password, as a signed-up account logs in.
  Future<void> _askPassword(User? user) async {
    final idField = TextEditingController();
    final controller = TextEditingController();
    final entered = await showModalBottomSheet<(String, String)>(
      context: context,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(user == null ? t('অ্যাকাউন্ট আইডি দিয়ে লগইন', 'Log in with your account ID') : t('${user.name}: পাসওয়ার্ড দিন', 'Password for ${user.name}'),
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(
            user == null
                ? t('অ্যাকাউন্ট খোলার সময় পাওয়া আইডি (যেমন FARM-DHA-7K2Q) আর আপনার পাসওয়ার্ড দিন।',
                    'Enter the ID you got when you created the account (like FARM-DHA-7K2Q) and your password.')
                : user.role == 'admin'
                    ? t('অ্যাডমিন অ্যাকাউন্ট শুধু সার্ভারের অ্যাডমিন পাসওয়ার্ডে খোলে।', 'Admin accounts open only with the server\'s admin password.')
                    : t('ডেমো অ্যাকাউন্টের পাসওয়ার্ড: krishi2026', 'Demo accounts use the password krishi2026.'),
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 16),
          if (user == null) ...[
            TextField(
              controller: idField,
              autofocus: true,
              textCapitalization: TextCapitalization.characters,
              autofillHints: const [AutofillHints.username],
              decoration: InputDecoration(labelText: t('অ্যাকাউন্ট আইডি', 'Account ID')),
            ),
            const SizedBox(height: 12),
          ],
          TextField(
            controller: controller,
            obscureText: true,
            autofocus: user != null,
            autofillHints: const [AutofillHints.password],
            decoration: InputDecoration(labelText: t('পাসওয়ার্ড', 'Password')),
            onSubmitted: (v) => Navigator.pop(context, (idField.text, v)),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton(onPressed: () => Navigator.pop(context, (idField.text, controller.text)), child: Text(t('লগইন', 'Log in'))),
          ),
        ]),
      ),
    );
    idField.dispose();
    controller.dispose();
    if (entered == null) return;
    final id = user?.id ?? entered.$1.trim();
    if (id.isNotEmpty && entered.$2.isNotEmpty) await _signIn(id, password: entered.$2, user: user);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: FutureBuilder<List<User>>(
          future: _users,
          builder: (context, snap) {
            final users = snap.data ?? const <User>[];
            final field = users.where((u) => ['farmer', 'buyer', 'driver'].contains(u.role)).toList();
            final desks = users.where((u) => !['farmer', 'buyer', 'driver'].contains(u.role)).toList();
            return CustomScrollView(slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
                sliver: SliverToBoxAdapter(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      const LogoMark(size: 44),
                      const SizedBox(width: 10),
                      Text('KrishiNexus', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                      const Spacer(),
                      SegmentedButton<String>(
                        showSelectedIcon: false,
                        style: const ButtonStyle(visualDensity: VisualDensity.compact),
                        segments: const [ButtonSegment(value: 'bn', label: Text('বাং')), ButtonSegment(value: 'en', label: Text('EN'))],
                        selected: {app.lang},
                        onSelectionChanged: (s) => app.setLang(s.first),
                      ),
                    ]),
                    const SizedBox(height: 28),
                    Text(t('ন্যায্য দাম, খোলা হিমাগার,\nবন্যার আগাম খবর।', 'Fair prices, open cold storage,\nflood warnings in time.'),
                        style: theme.textTheme.headlineMedium),
                    const SizedBox(height: 8),
                    Text(
                      t('বাংলায় প্রশ্ন বলুন, ফসলের ছবি তুলে গ্রেড নিন, সরাসরি ক্রেতার কাছে বেচুন।',
                          'Ask in Bangla, grade the harvest with the camera, sell straight to buyers.'),
                      style: theme.textTheme.bodyLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                    if (app.sessionExpired) ...[
                      const SizedBox(height: 12),
                      Pill(t('সেশন শেষ, আবার লগইন করুন', 'Session ended; log in again'), tone: Tone.amber, icon: Icons.timer_off_rounded),
                    ],
                    const SizedBox(height: 24),
                    Text(t('কে ব্যবহার করছেন?', 'Who is using the app?'), style: theme.textTheme.titleMedium),
                  ]),
                ),
              ),
              if (snap.connectionState != ConnectionState.done)
                const SliverToBoxAdapter(child: SizedBox(height: 360, child: SkeletonList(count: 3, height: 84)))
              else if (snap.hasError)
                SliverToBoxAdapter(child: ErrorState(error: snap.error!, onRetry: () => setState(() => _users = _load())))
              else ...[
                _accounts(field, big: true),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
                  sliver: SliverToBoxAdapter(child: Text(t('অফিস ও পর্যবেক্ষক', 'Desks and observers'), style: theme.textTheme.titleMedium)),
                ),
                _accounts(desks, big: false),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                  sliver: SliverToBoxAdapter(
                    child: Text(
                      t('ডেমো সার্ভার: ${Api.base.replaceFirst('https://', '')} · ট্যাপ করলেই লগইন; পাসওয়ার্ড লাগলে চাওয়া হবে।',
                          'Demo node: ${Api.base.replaceFirst('https://', '')} · one tap signs in; a password is asked where needed.'),
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                  ),
                ),
              ],
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
                sliver: SliverToBoxAdapter(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Text(t('নতুন এসেছেন?', 'New here?'), style: theme.textTheme.titleMedium),
                    const SizedBox(height: 10),
                    FilledButton.tonalIcon(
                      onPressed: () => Navigator.of(context).push(fadeRoute(const SignUpScreen())),
                      icon: const Icon(Icons.person_add_alt_1_rounded),
                      label: Text(t('নতুন অ্যাকাউন্ট খুলুন', 'Create an account')),
                    ),
                    const SizedBox(height: 6),
                    TextButton.icon(
                      onPressed: _busy == null ? () => _askPassword(null) : null,
                      icon: const Icon(Icons.key_rounded),
                      label: Text(t('অ্যাকাউন্ট আইডি দিয়ে লগইন', 'Log in with an account ID')),
                    ),
                  ]),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                sliver: SliverToBoxAdapter(
                  child: Wrap(alignment: WrapAlignment.center, crossAxisAlignment: WrapCrossAlignment.center, children: [
                    TextButton.icon(
                      onPressed: () => openWeb(context, '/'),
                      icon: const Icon(Icons.language_rounded),
                      label: Text(Api.base.replaceFirst(RegExp('^https?://'), '')),
                    ),
                    TextButton(
                      onPressed: () => Navigator.of(context).push(fadeRoute(const GuideScreen())),
                      child: Text(t('কীভাবে ব্যবহার করবেন', 'How to use')),
                    ),
                    TextButton(
                      onPressed: () => Navigator.of(context).push(fadeRoute(const TeamScreen())),
                      child: Text(t('টিম হিট ওয়েভ', 'Team Heat Wave')),
                    ),
                  ]),
                ),
              ),
            ]);
          },
        ),
      ),
    );
  }

  Widget _accounts(List<User> users, {required bool big}) => SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        sliver: SliverList.separated(
          itemCount: users.length,
          separatorBuilder: (_, _) => const SizedBox(height: 10),
          itemBuilder: (context, i) {
            final u = users[i];
            final theme = Theme.of(context);
            return AppCard(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: big ? 14 : 10),
              onTap: _busy == null ? () => _signIn(u.id, user: u) : null,
              child: Row(children: [
                CircleAvatar(
                  radius: big ? 24 : 20,
                  backgroundColor: theme.colorScheme.primaryContainer,
                  child: Icon(roleIcon(u.role), color: theme.colorScheme.onPrimaryContainer, size: big ? 26 : 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(u.name, style: big ? theme.textTheme.titleMedium : theme.textTheme.titleSmall),
                    Text([roleName(u.role), if (u.district.isNotEmpty) u.district, u.title].join(' · '),
                        maxLines: 2, overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                  ]),
                ),
                const SizedBox(width: 8),
                _busy == u.id
                    ? const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
                    : Icon(Icons.arrow_forward_rounded, color: theme.colorScheme.onSurfaceVariant),
              ]),
            );
          },
        ),
      );
}
