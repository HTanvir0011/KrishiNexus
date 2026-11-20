import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'driver.dart' show BandLiveDot;
import 'market.dart';

/// Bank: problems farmers, buyers and drivers reported on sales; release, refund or keep holding the payment.
class DisputesScreen extends StatefulWidget {
  const DisputesScreen({super.key});

  @override
  State<DisputesScreen> createState() => _DisputesScreenState();
}

class _DisputesScreenState extends State<DisputesScreen>
    with Polling<DisputesScreen, List<Dispute>> {
  @override
  Future<List<Dispute>> load() async =>
      mapsOf(await Api.get('/market/disputes')).map(Dispute.new).toList();

  @override
  bool relevant(MarketEvent e) =>
      e.lotId == null || e.kind.startsWith('dispute');

  Future<void> _resolve(Dispute d, String resolution) async {
    final done = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _DecideSheet(dispute: d, resolution: resolution),
    );
    if (done == true) refresh(quiet: true);
  }

  /// The three outcomes as labelled buttons (refund in rose, always confirmed in the sheet) and a quiet "no change".
  Widget _outcomes(Dispute d) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '${t('বিক্রি', 'Sale')} ${d.lotId}',
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: () => _resolve(d, 'RELEASE_TO_FARMER'),
            icon: const Icon(Icons.check_circle_rounded),
            label: Text(resolutionName('RELEASE_TO_FARMER')),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            style: FilledButton.styleFrom(
              backgroundColor: scheme.error,
              foregroundColor: scheme.onError,
            ),
            onPressed: () => _resolve(d, 'REFUND_TO_BUYER'),
            icon: const Icon(Icons.undo_rounded),
            label: Text(resolutionName('REFUND_TO_BUYER')),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () => _resolve(d, 'KEEP_HOLDING'),
            icon: const Icon(Icons.lock_clock_rounded),
            label: Text(resolutionName('KEEP_HOLDING')),
          ),
          TextButton(
            onPressed: () => _resolve(d, 'NO_CHANGE'),
            child: Text(resolutionName('NO_CHANGE')),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final all = data ?? const <Dispute>[];
    final open = all.where((d) => d.status == 'OPEN').toList();
    final closed = all.where((d) => d.status != 'OPEN').toList();
    final canResolve = app.user?.role == 'bank' || app.user?.role == 'admin';
    return Scaffold(
      body: Column(
        children: [
          HeaderBand(
            title: t('অভিযোগ', 'Disputes'),
            trailing: const BandLiveDot(),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: AmountText(
                    digits(open.length),
                    color: Colors.white,
                    caption: t('খোলা অভিযোগ', 'Open disputes'),
                  ),
                ),
                AmountText(
                  digits(closed.length),
                  size: 22,
                  color: Colors.white,
                  caption: t('মীমাংসিত', 'Resolved'),
                ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: refresh,
              child: loading && data == null
                  ? const SkeletonList()
                  : error != null && data == null
                  ? ListView(
                      children: [ErrorState(error: error!, onRetry: refresh)],
                    )
                  : ListView(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                      children: [
                        SectionTitle(
                          t(
                            'খোলা (${digits(open.length)})',
                            'Open (${open.length})',
                          ),
                          top: 16,
                        ),
                        if (open.isEmpty)
                          EmptyState(
                            icon: Icons.verified_rounded,
                            title: t(
                              'কোনো খোলা অভিযোগ নেই',
                              'No open disputes',
                            ),
                          )
                        else
                          for (final d in open) ...[
                            DisputeTile(
                              dispute: d,
                              trailing: canResolve ? _outcomes(d) : null,
                            ),
                            const SizedBox(height: 12),
                          ],
                        if (closed.isNotEmpty) ...[
                          SectionTitle(t('মীমাংসিত', 'Resolved')),
                          for (final d in closed) ...[
                            DisputeTile(dispute: d),
                            const SizedBox(height: 12),
                          ],
                        ],
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Confirms one outcome: names it, takes the reason, and sends it. A refund shows in rose.
class _DecideSheet extends StatefulWidget {
  const _DecideSheet({required this.dispute, required this.resolution});
  final Dispute dispute;
  final String resolution;

  @override
  State<_DecideSheet> createState() => _DecideSheetState();
}

class _DecideSheetState extends State<_DecideSheet> {
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() => _busy = true);
    final res = await guarded(
      context,
      () => Api.post('/market/disputes/${widget.dispute.id}/resolve', {
        'resolution': widget.resolution,
        'note': _note.text.trim(),
      }),
      done: t('মীমাংসা হয়েছে', 'Resolved'),
    );
    if (!mounted) return;
    setState(() => _busy = false);
    if (res != null) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final refund = widget.resolution == 'REFUND_TO_BUYER';
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        20,
        0,
        20,
        20 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            resolutionName(widget.resolution),
            style: theme.textTheme.titleLarge?.copyWith(
              color: refund ? theme.colorScheme.error : null,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${disputeKind(widget.dispute.kind)} · ${widget.dispute.lotId}',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          if (widget.dispute.note.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(widget.dispute.note),
            ),
          if (refund) ...[
            const SizedBox(height: 8),
            Text(
              t(
                'ফেরত শুধু টাকা আটকে থাকা অবস্থায় হয়; পৌঁছায়নি এমন বিক্রি বাতিল হয়।',
                'A refund works only while the payment is held; it cancels an undelivered sale.',
              ),
              style: theme.textTheme.bodySmall,
            ),
          ],
          const SizedBox(height: 14),
          TextField(
            controller: _note,
            maxLength: 300,
            maxLines: 2,
            decoration: InputDecoration(
              hintText: t('সিদ্ধান্তের কারণ', 'Why this decision'),
            ),
          ),
          const SizedBox(height: 8),
          FilledButton(
            style: refund
                ? FilledButton.styleFrom(
                    backgroundColor: theme.colorScheme.error,
                    foregroundColor: theme.colorScheme.onError,
                  )
                : null,
            onPressed: _busy ? null : _send,
            child: Text(t('নিশ্চিত করুন', 'Confirm')),
          ),
          TextButton(
            onPressed: _busy ? null : () => Navigator.pop(context, false),
            child: Text(t('ফিরে যান', 'Go back')),
          ),
        ],
      ),
    );
  }
}

/// Bank: every payment held or settled (direct sales and one-tap truckload locks, both simulated).
class LedgerScreen extends StatefulWidget {
  const LedgerScreen({super.key});

  @override
  State<LedgerScreen> createState() => _LedgerScreenState();
}

class _LedgerScreenState extends State<LedgerScreen>
    with Polling<LedgerScreen, List<Map<String, dynamic>>> {
  @override
  Future<List<Map<String, dynamic>>> load() async =>
      mapsOf(await Api.get('/market/ledger'));

  @override
  bool relevant(MarketEvent e) => e.kind != 'location';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final rows = data ?? const <Map<String, dynamic>>[];
    double sum(String status) => rows
        .where((r) => r['status'] == status)
        .fold(0.0, (a, r) => a + numOf(r['amount_tk']));
    return Scaffold(
      body: Column(
        children: [
          HeaderBand(
            title: t('লেনদেন', 'Ledger'),
            trailing: const BandLiveDot(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                AmountText(
                  money(sum('HELD')),
                  color: Colors.white,
                  caption: escrowStatus('HELD'),
                ),
                const SizedBox(height: 12),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: AmountText(
                        money(sum('RELEASED')),
                        size: 22,
                        color: Colors.white,
                        caption: escrowStatus('RELEASED'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: AmountText(
                        money(sum('REFUNDED')),
                        size: 22,
                        color: Colors.white,
                        caption: escrowStatus('REFUNDED'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: refresh,
              child: loading && data == null
                  ? const SkeletonList()
                  : error != null && data == null
                  ? ListView(
                      children: [ErrorState(error: error!, onRetry: refresh)],
                    )
                  : ListView(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                      children: [
                        SectionTitle(
                          t(
                            'সব লেনদেন (${digits(rows.length)})',
                            'All payments (${rows.length})',
                          ),
                          top: 16,
                        ),
                        if (rows.isEmpty)
                          EmptyState(
                            icon: Icons.receipt_long_rounded,
                            title: t('এখনো কোনো লেনদেন নেই', 'No payments yet'),
                          ),
                        for (final r in rows) ...[
                          _LedgerRow(row: r, theme: theme),
                          const SizedBox(height: 12),
                        ],
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

/// One payment as a receipt row: status icon in its colour, what and who, the amount, and the status in words.
class _LedgerRow extends StatelessWidget {
  const _LedgerRow({required this.row, required this.theme});
  final Map<String, dynamic> row;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    final r = row;
    final status = '${r['status']}';
    final (tone, icon) = switch (status) {
      'RELEASED' => (Tone.green, Icons.check_circle_rounded),
      'REFUNDED' => (Tone.rose, Icons.undo_rounded),
      _ => (Tone.violet, Icons.lock_clock_rounded),
    };
    final disputes = numOf(r['open_disputes']).toInt();
    return AppCard(
      tone: r['at_risk'] == true || disputes > 0 ? Tone.amber : null,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: tone.bg(context),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: tone.fg(context), size: 26),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${cropName('${r['crop']}')} · ${kg(numOf(r['weight_kg']))}',
                      style: theme.textTheme.titleSmall,
                    ),
                    Text(
                      r['kind'] == 'Truckload lock'
                          ? t('ট্রাকলোড লক', 'Truckload lock')
                          : t('সরাসরি বিক্রি', 'Direct sale'),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              AmountText(
                money(numOf(r['amount_tk'])),
                size: 22,
                color: tone.fg(context),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '${r['farmer']} → ${r['buyer']} · ${r['wallet']} ${r['wallet_masked']}',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              Pill(escrowStatus(status), tone: tone, icon: icon),
              if (disputes > 0)
                Pill(
                  t('${digits(disputes)} অভিযোগ', '$disputes open dispute(s)'),
                  tone: Tone.amber,
                  icon: Icons.report_problem_rounded,
                ),
              if (r['at_risk'] == true)
                Pill(
                  t('পচনের ঝুঁকি', 'Spoilage risk'),
                  tone: Tone.rose,
                  icon: Icons.warning_rounded,
                ),
              if (r['below_floor'] == true)
                Pill(
                  t('খরচের নিচে', 'Below cost'),
                  tone: Tone.rose,
                  icon: Icons.trending_down_rounded,
                ),
            ],
          ),
        ],
      ),
    );
  }
}
