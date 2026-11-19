import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'market.dart';

const _resolutions = ['RELEASE_TO_FARMER', 'REFUND_TO_BUYER', 'KEEP_HOLDING', 'NO_CHANGE'];

/// Bank: problems farmers, buyers and drivers reported on sales; release, refund or keep holding the payment.
class DisputesScreen extends StatefulWidget {
  const DisputesScreen({super.key});

  @override
  State<DisputesScreen> createState() => _DisputesScreenState();
}

class _DisputesScreenState extends State<DisputesScreen> with Polling<DisputesScreen, List<Dispute>> {
  @override
  Future<List<Dispute>> load() async => mapsOf(await Api.get('/market/disputes')).map(Dispute.new).toList();

  Future<void> _resolve(Dispute d) async {
    final done = await showModalBottomSheet<bool>(context: context, isScrollControlled: true, builder: (_) => _ResolveSheet(dispute: d));
    if (done == true) refresh(quiet: true);
  }

  @override
  Widget build(BuildContext context) {
    final all = data ?? const <Dispute>[];
    final open = all.where((d) => d.status == 'OPEN').toList();
    final closed = all.where((d) => d.status != 'OPEN').toList();
    final canResolve = app.user?.role == 'bank' || app.user?.role == 'admin';
    return Scaffold(
      appBar: AppBar(title: Text(t('অভিযোগ', 'Disputes'))),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: loading && data == null
            ? const SkeletonList()
            : error != null && data == null
                ? ListView(children: [ErrorState(error: error!, onRetry: refresh)])
                : ListView(padding: const EdgeInsets.fromLTRB(16, 0, 16, 32), children: [
                    SectionTitle(t('খোলা (${digits(open.length)})', 'Open (${open.length})'), top: 8),
                    if (open.isEmpty)
                      AppCard(child: Text(t('কোনো খোলা অভিযোগ নেই।', 'No open disputes.')))
                    else
                      for (final d in open) ...[
                        DisputeTile(
                          dispute: d,
                          trailing: canResolve
                              ? Padding(
                                  padding: const EdgeInsets.only(top: 10),
                                  child: FilledButton.tonalIcon(onPressed: () => _resolve(d), icon: const Icon(Icons.gavel_rounded), label: Text(t('মীমাংসা করুন · ${d.lotId}', 'Resolve · ${d.lotId}'))),
                                )
                              : null,
                        ),
                        const SizedBox(height: 10),
                      ],
                    if (closed.isNotEmpty) ...[
                      SectionTitle(t('মীমাংসিত', 'Resolved')),
                      for (final d in closed) ...[DisputeTile(dispute: d), const SizedBox(height: 10)],
                    ],
                  ]),
      ),
    );
  }
}

class _ResolveSheet extends StatefulWidget {
  const _ResolveSheet({required this.dispute});
  final Dispute dispute;

  @override
  State<_ResolveSheet> createState() => _ResolveSheetState();
}

class _ResolveSheetState extends State<_ResolveSheet> {
  String _resolution = 'RELEASE_TO_FARMER';
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/market/disputes/${widget.dispute.id}/resolve', {'resolution': _resolution, 'note': _note.text.trim()}),
        done: t('মীমাংসা হয়েছে', 'Resolved'));
    if (!mounted) return;
    setState(() => _busy = false);
    if (res != null) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${disputeKind(widget.dispute.kind)} · ${widget.dispute.lotId}', style: Theme.of(context).textTheme.titleLarge),
          if (widget.dispute.note.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(widget.dispute.note)),
          const SizedBox(height: 14),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final r in _resolutions) ChoiceChip(label: Text(resolutionName(r)), selected: _resolution == r, onSelected: (_) => setState(() => _resolution = r)),
          ]),
          const SizedBox(height: 8),
          Text(
            t('ফেরত শুধু টাকা আটকে থাকা অবস্থায় হয়; পৌঁছায়নি এমন বিক্রি বাতিল হয়।', 'A refund works only while the payment is held; it cancels an undelivered sale.'),
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          TextField(controller: _note, maxLength: 300, maxLines: 2, decoration: InputDecoration(hintText: t('সিদ্ধান্তের কারণ', 'Why this decision'))),
          FilledButton(onPressed: _busy ? null : _send, child: Text(t('সিদ্ধান্ত দিন', 'Decide'))),
        ]),
      );
}

/// Bank: every payment held or settled (direct sales and one-tap truckload locks, both simulated).
class LedgerScreen extends StatefulWidget {
  const LedgerScreen({super.key});

  @override
  State<LedgerScreen> createState() => _LedgerScreenState();
}

class _LedgerScreenState extends State<LedgerScreen> with Polling<LedgerScreen, List<Map<String, dynamic>>> {
  @override
  Future<List<Map<String, dynamic>>> load() async => mapsOf(await Api.get('/market/ledger'));

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final rows = data ?? const <Map<String, dynamic>>[];
    double sum(String status) => rows.where((r) => r['status'] == status).fold(0.0, (a, r) => a + numOf(r['amount_tk']));
    return Scaffold(
      appBar: AppBar(title: Text(t('লেনদেন', 'Ledger'))),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: loading && data == null
            ? const SkeletonList()
            : error != null && data == null
                ? ListView(children: [ErrorState(error: error!, onRetry: refresh)])
                : ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
                    Row(children: [
                      for (final (status, tone) in [('HELD', Tone.violet), ('RELEASED', Tone.green), ('REFUNDED', Tone.rose)]) ...[
                        Expanded(
                          child: AppCard(
                            tone: tone,
                            padding: const EdgeInsets.all(12),
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(escrowStatus(status), maxLines: 2, style: theme.textTheme.labelMedium),
                              const SizedBox(height: 4),
                              CountUp(value: sum(status), format: (v) => money(v), style: theme.textTheme.titleMedium?.copyWith(color: tone.fg(context))),
                            ]),
                          ),
                        ),
                        if (status != 'REFUNDED') const SizedBox(width: 8),
                      ],
                    ]),
                    SectionTitle(t('সব লেনদেন (${digits(rows.length)})', 'All payments (${rows.length})')),
                    for (final r in rows) ...[
                      AppCard(
                        tone: r['at_risk'] == true || numOf(r['open_disputes']) > 0 ? Tone.amber : null,
                        padding: const EdgeInsets.all(14),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [
                            Expanded(child: Text('${r['kind'] == 'Truckload lock' ? t('ট্রাকলোড লক', 'Truckload lock') : t('সরাসরি বিক্রি', 'Direct sale')} · ${cropName('${r['crop']}')} · ${kg(numOf(r['weight_kg']))}', style: theme.textTheme.titleSmall)),
                            Text(money(numOf(r['amount_tk'])), style: theme.textTheme.titleSmall?.copyWith(fontFeatures: tabular)),
                          ]),
                          const SizedBox(height: 4),
                          Text('${r['farmer']} → ${r['buyer']} · ${r['wallet']} ${r['wallet_masked']}', style: theme.textTheme.bodySmall),
                          const SizedBox(height: 8),
                          Wrap(spacing: 6, runSpacing: 6, children: [
                            Pill(escrowStatus('${r['status']}'), tone: switch (r['status']) { 'RELEASED' => Tone.green, 'REFUNDED' => Tone.rose, _ => Tone.violet }),
                            if (numOf(r['open_disputes']) > 0) Pill(t('${digits(numOf(r['open_disputes']).toInt())} অভিযোগ', '${numOf(r['open_disputes']).toInt()} open dispute(s)'), tone: Tone.amber),
                            if (r['at_risk'] == true) Pill(t('পচনের ঝুঁকি', 'Spoilage risk'), tone: Tone.rose),
                            if (r['below_floor'] == true) Pill(t('খরচের নিচে', 'Below cost'), tone: Tone.rose),
                          ]),
                        ]),
                      ),
                      const SizedBox(height: 10),
                    ],
                  ]),
      ),
    );
  }
}
