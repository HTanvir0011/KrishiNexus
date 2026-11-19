import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

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

  Future<void> _signIn(User user, {String? password}) async {
    setState(() => _busy = user.id);
    try {
      final session = await Api.post('/auth/login', {'user_id': user.id, 'password': ?password});
      await app.signIn((session as Map).cast<String, dynamic>());
    } on ApiError catch (e) {
      if (!mounted) return;
      if (e.status == 401 && password == null) {
        _askPassword(user);
      } else {
        snack(context, friendlyError(e), icon: Icons.error_outline_rounded, tone: Tone.rose);
      }
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Future<void> _askPassword(User user) async {
    final controller = TextEditingController();
    final password = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(t('${user.name}: পাসওয়ার্ড দিন', 'Password for ${user.name}'), style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(
            user.role == 'admin'
                ? t('অ্যাডমিন অ্যাকাউন্ট শুধু সার্ভারের অ্যাডমিন পাসওয়ার্ডে খোলে।', 'Admin accounts open only with the server\'s admin password.')
                : t('ডেমো অ্যাকাউন্টের পাসওয়ার্ড: krishi2026', 'Demo accounts use the password krishi2026.'),
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: controller,
            obscureText: true,
            autofocus: true,
            autofillHints: const [AutofillHints.password],
            decoration: InputDecoration(labelText: t('পাসওয়ার্ড', 'Password')),
            onSubmitted: (v) => Navigator.pop(context, v),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: Text(t('লগইন', 'Log in'))),
          ),
        ]),
      ),
    );
    controller.dispose();
    if (password != null && password.isNotEmpty) await _signIn(user, password: password);
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
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
                  sliver: SliverToBoxAdapter(
                    child: Text(
                      t('ডেমো সার্ভার: ${Api.base.replaceFirst('https://', '')} · ট্যাপ করলেই লগইন; পাসওয়ার্ড লাগলে চাওয়া হবে।',
                          'Demo node: ${Api.base.replaceFirst('https://', '')} · one tap signs in; a password is asked where needed.'),
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                  ),
                ),
              ],
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
              onTap: _busy == null ? () => _signIn(u) : null,
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
