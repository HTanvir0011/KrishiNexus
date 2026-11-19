import 'package:flutter/material.dart';

import '../core/state.dart';
import '../core/theme.dart';
import 'ask.dart';
import 'bank.dart';
import 'driver.dart';
import 'market.dart';
import 'me.dart';
import 'scan.dart';

class _Tab {
  const _Tab(this.id, this.icon, this.selected, this.bn, this.en, this.build);
  final String id;
  final IconData icon;
  final IconData selected;
  final String bn;
  final String en;
  final Widget Function() build;
}

final _ask = _Tab('ask', Icons.mic_none_rounded, Icons.mic_rounded, 'জিজ্ঞাসা', 'Ask', () => const AskScreen());
final _scan = _Tab('scan', Icons.photo_camera_outlined, Icons.photo_camera_rounded, 'স্ক্যান', 'Scan', () => const ScanScreen());
final _me = _Tab('me', Icons.person_outline_rounded, Icons.person_rounded, 'আমি', 'Me', () => const MeScreen());

/// The tabs each role works in (backend permissions: marketplace.py `_role`). Desk roles keep voice and camera and
/// open their full desk on the website.
List<_Tab> _tabsFor(String role) => switch (role) {
      'farmer' => [_ask, _scan, _Tab('market', Icons.storefront_outlined, Icons.storefront_rounded, 'বাজার', 'Market', () => const MarketScreen()), _me],
      'buyer' => [
          _Tab('market', Icons.storefront_outlined, Icons.storefront_rounded, 'বাজার', 'Market', () => const MarketScreen()),
          _Tab('purchases', Icons.receipt_long_outlined, Icons.receipt_long_rounded, 'কেনা', 'Purchases', () => const PurchasesScreen()),
          _Tab('verify', Icons.verified_outlined, Icons.verified_rounded, 'যাচাই', 'Verify', () => const VerifyScreen()),
          _me,
        ],
      'driver' => [
          _Tab('jobs', Icons.list_alt_rounded, Icons.list_alt_rounded, 'কাজ', 'Jobs', () => const JobsScreen()),
          _Tab('active', Icons.local_shipping_outlined, Icons.local_shipping_rounded, 'চলতি', 'On the road', () => const ActiveJobScreen()),
          _me,
        ],
      'bank' => [
          _Tab('disputes', Icons.report_problem_outlined, Icons.report_problem_rounded, 'অভিযোগ', 'Disputes', () => const DisputesScreen()),
          _Tab('ledger', Icons.account_balance_outlined, Icons.account_balance_rounded, 'লেনদেন', 'Ledger', () => const LedgerScreen()),
          _me,
        ],
      'judge' || 'admin' => [
          _ask,
          _scan,
          _Tab('market', Icons.storefront_outlined, Icons.storefront_rounded, 'বাজার', 'Market', () => const MarketScreen()),
          _Tab('jobs', Icons.local_shipping_outlined, Icons.local_shipping_rounded, 'ডেলিভারি', 'Deliveries', () => const JobsScreen()),
          _me,
        ],
      _ => [_ask, _scan, _Tab('desk', Icons.dashboard_outlined, Icons.dashboard_rounded, 'ডেস্ক', 'Desk', () => const DeskScreen()), _me],
    };

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  // The shell is keyed by the account, so its role and tabs are fixed for its life.
  late final List<_Tab> _tabs = _tabsFor(app.user!.role);
  late final List<Widget?> _built = List.filled(_tabs.length, null);

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: app,
        builder: (context, _) {
          // Signed out: this shell is fading away; drop the tabs before they rebuild without an account.
          if (app.user == null) return const SizedBox.shrink();
          final index = _tabs.indexWhere((tab) => tab.id == app.tab).clamp(0, _tabs.length - 1);
          // Tabs are built the first time they are opened and then kept, so an answer or a camera grade survives a
          // trip to another tab.
          _built[index] ??= _tabs[index].build();
          return PopScope(
            canPop: index == 0,
            onPopInvokedWithResult: (didPop, _) {
              if (!didPop) app.goTab(_tabs.first.id);
            },
            child: Scaffold(
              body: IndexedStack(
                index: index,
                children: [
                  for (var i = 0; i < _tabs.length; i++)
                    TickerMode(enabled: i == index, child: _FadeThrough(active: i == index, child: _built[i] ?? const SizedBox())),
                ],
              ),
              bottomNavigationBar: NavigationBar(
                selectedIndex: index,
                onDestinationSelected: (i) => app.goTab(_tabs[i].id),
                destinations: [
                  for (final tab in _tabs)
                    NavigationDestination(icon: Icon(tab.icon), selectedIcon: Icon(tab.selected), label: t(tab.bn, tab.en)),
                ],
              ),
            ),
          );
        },
      );
}

/// Material fade-through: the tab coming in fades up from 92% scale-free opacity (instant with animations off).
class _FadeThrough extends StatefulWidget {
  const _FadeThrough({required this.active, required this.child});
  final bool active;
  final Widget child;

  @override
  State<_FadeThrough> createState() => _FadeThroughState();
}

class _FadeThroughState extends State<_FadeThrough> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 260), value: 1);

  @override
  void didUpdateWidget(_FadeThrough old) {
    super.didUpdateWidget(old);
    if (widget.active && !old.active && !Motion.reduced(context)) _c.forward(from: 0);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FadeTransition(
        opacity: CurvedAnimation(parent: _c, curve: Motion.expo),
        child: SlideTransition(
          position: Tween(begin: const Offset(0, 0.015), end: Offset.zero).animate(CurvedAnimation(parent: _c, curve: Motion.expo)),
          child: widget.child,
        ),
      );
}
