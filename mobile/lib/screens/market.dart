import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/grade_view.dart';
import 'scan.dart' show fadeRoute;

Future<List<Lot>> fetchLots() async => mapsOf(await Api.get('/market/lots')).map(Lot.new).toList();

/// Polls [load] every [every] while the tab or screen is on show (TickerMode), and on pull-to-refresh.
mixin Polling<T extends StatefulWidget, D> on State<T> {
  D? data;
  Object? error;
  Timer? _timer;
  bool loading = true;

  Future<D> load();
  Duration get every => const Duration(seconds: 12);

  @override
  void initState() {
    super.initState();
    refresh();
    _timer = Timer.periodic(every, (_) {
      if (mounted && TickerMode.valuesOf(context).enabled) refresh(quiet: true);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> refresh({bool quiet = false}) async {
    if (!quiet && mounted && data == null) setState(() => loading = true);
    try {
      final next = await load();
      if (mounted) {
        setState(() {
          data = next;
          error = null;
          loading = false;
        });
      }
    } catch (e) {
      // A failed background poll keeps what is on screen.
      if (mounted && (!quiet || data == null)) {
        setState(() {
          error = e;
          loading = false;
        });
      }
    }
  }
}

int lotStage(Lot lot) => switch (lot.status) { 'OPEN' => 0, 'SOLD' => 1, 'IN_TRANSIT' => 2, 'DELIVERED' => 3, _ => 0 };
Tone lotTone(String status) => switch (status) {
      'OPEN' => Tone.amber,
      'SOLD' => Tone.violet,
      'IN_TRANSIT' => Tone.sky,
      'DELIVERED' => Tone.green,
      _ => Tone.slate,
    };

/// Farmer: own lots and "List a lot". Buyer: open lots to bid on. Judge and admin: every lot, read only.
class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> with Polling<MarketScreen, List<Lot>> {
  String? _crop;
  String _status = 'OPEN';

  @override
  Future<List<Lot>> load() => fetchLots();

  String get _role => app.user?.role ?? '';

  @override
  void initState() {
    super.initState();
    app.addListener(_draftWatcher);
    WidgetsBinding.instance.addPostFrameCallback((_) => _draftWatcher());
  }

  @override
  void dispose() {
    app.removeListener(_draftWatcher);
    super.dispose();
  }

  // A grade or a decision asked to sell a lot: open the listing sheet with its details filled in.
  void _draftWatcher() {
    final draft = app.sellDraft;
    if (draft == null || app.tab != 'market' || !mounted || _role != 'farmer') return;
    app.sellDraft = null;
    _sell(draft);
  }

  Future<void> _sell([Map<String, dynamic>? draft]) async {
    final lot = await showModalBottomSheet<Lot>(context: context, isScrollControlled: true, builder: (_) => SellSheet(draft: draft));
    if (lot == null || !mounted) return;
    await refresh(quiet: true);
    if (mounted) await Navigator.of(context).push(fadeRoute(LotScreen(lotId: lot.id, initial: lot)));
  }

  @override
  Widget build(BuildContext context) {
    final me = app.user!;
    final all = data ?? const <Lot>[];
    final lots = switch (_role) {
      'farmer' => all.where((l) => l.farmerId == me.id).toList(),
      'buyer' => all.where((l) => l.status == 'OPEN' && (_crop == null || l.crop == _crop)).toList(),
      _ => all.where((l) => _status == 'ALL' || l.status == _status).toList(),
    };
    final title = switch (_role) {
      'farmer' => t('আমার লট', 'My lots'),
      'buyer' => t('খোলা লট', 'Open lots'),
      _ => t('সব লট', 'All lots'),
    };
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      floatingActionButton: _role == 'farmer'
          ? FloatingActionButton.extended(onPressed: _sell, icon: const Icon(Icons.add_rounded), label: Text(t('নতুন লট', 'List a lot')))
          : null,
      body: Column(children: [
        if (_role == 'buyer')
          _FilterBar(children: [
            ChoiceChip(label: Text(t('সব ফসল', 'All crops')), selected: _crop == null, onSelected: (_) => setState(() => _crop = null)),
            for (final c in marketCrops) ChoiceChip(label: Text(cropName(c)), selected: _crop == c, onSelected: (_) => setState(() => _crop = c)),
          ]),
        if (_role != 'buyer' && _role != 'farmer')
          _FilterBar(children: [
            for (final s in ['OPEN', 'SOLD', 'IN_TRANSIT', 'DELIVERED', 'ALL'])
              ChoiceChip(label: Text(s == 'ALL' ? t('সব', 'All') : lotStatus(s)), selected: _status == s, onSelected: (_) => setState(() => _status = s)),
          ]),
        Expanded(
          child: RefreshIndicator(
            onRefresh: refresh,
            child: loading && data == null
                ? const SkeletonList()
                : error != null && data == null
                    ? ListView(children: [ErrorState(error: error!, onRetry: refresh)])
                    : lots.isEmpty
                        ? ListView(children: [
                            EmptyState(
                              icon: Icons.storefront_rounded,
                              title: _role == 'farmer' ? t('এখনো কোনো লট নেই', 'No lots yet') : t('এখন কোনো লট নেই', 'Nothing here right now'),
                              body: _role == 'farmer'
                                  ? t('ফসল স্ক্যান করে বা সরাসরি লট দিন; ক্রেতারা খোলাখুলি দর দেবেন।', 'Scan the harvest or list a lot; buyers bid in the open.')
                                  : null,
                              action: _role == 'farmer'
                                  ? FilledButton.icon(onPressed: _sell, icon: const Icon(Icons.add_rounded), label: Text(t('নতুন লট', 'List a lot')))
                                  : null,
                            ),
                          ])
                        : ListView.separated(
                            padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                            itemCount: lots.length,
                            separatorBuilder: (_, _) => const SizedBox(height: 12),
                            itemBuilder: (context, i) => LotCard(
                              lot: lots[i],
                              onTap: () async {
                                await Navigator.of(context).push(fadeRoute(LotScreen(lotId: lots[i].id, initial: lots[i])));
                                refresh(quiet: true);
                              },
                            ),
                          ),
          ),
        ),
      ]),
    );
  }
}

class _FilterBar extends StatelessWidget {
  const _FilterBar({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 56,
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          scrollDirection: Axis.horizontal,
          itemCount: children.length,
          separatorBuilder: (_, _) => const SizedBox(width: 8),
          itemBuilder: (_, i) => children[i],
        ),
      );
}

class LotCard extends StatelessWidget {
  const LotCard({super.key, required this.lot, required this.onTap});
  final Lot lot;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final me = app.user!.id;
    final best = lot.best;
    final sold = lot.acceptedBid;
    final mine = lot.activeBids.where((b) => b.buyerId == me).firstOrNull;
    final leading = mine != null && best != null && mine.id == best.id;
    return AppCard(
      onTap: onTap,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          GradeStamp(letter: lot.grade, size: 46),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${cropName(lot.crop)} · ${kg(lot.kg)}', style: theme.textTheme.titleMedium),
              Text([lot.upazila, lot.district].where((s) => s.isNotEmpty).join(', ') + (app.user!.role == 'farmer' ? '' : ' · ${lot.farmerName}'),
                  maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ]),
          ),
          Pill(lotStatus(lot.status), tone: lotTone(lot.status)),
        ]),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(
                  sold != null
                      ? t('বিক্রি দাম', 'Sold at')
                      : best == null
                          ? t('এখনো দর নেই', 'No bids yet')
                          : t('সর্বোচ্চ দর', 'Highest bid'),
                  style: theme.textTheme.labelMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
              Text(
                  sold != null
                      ? '${perKg(sold.price)} · ${sold.buyerName}'
                      : best == null
                          ? (lot.asking == null ? t('প্রথম দর দিন', 'Be the first to bid') : '${t('চাওয়া', 'asking')} ${perKg(lot.asking)}')
                          : perKg(best.price),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.titleMedium
                      ?.copyWith(fontFeatures: tabular, color: sold == null && best == null ? null : Tone.green.fg(context))),
            ]),
          ),
          if (lot.certId != null) Icon(Icons.verified_rounded, size: 22, color: Tone.green.fg(context), semanticLabel: t('সনদ আছে', 'Certified')),
        ]),
        if (lot.activeBids.isNotEmpty || mine != null) ...[
          const SizedBox(height: 10),
          Wrap(spacing: 6, runSpacing: 6, children: [
            if (lot.activeBids.isNotEmpty) Pill(plural(lot.activeBids.length, 'টি দর', 'bid', 'bids'), tone: Tone.slate, icon: Icons.gavel_rounded),
            if (mine != null) Pill(leading ? t('আপনি এগিয়ে', 'You lead') : t('আপনাকে ছাড়িয়েছে', 'Outbid'), tone: leading ? Tone.green : Tone.rose),
          ]),
        ],
      ]),
    );
  }
}

/// One lot: its stages, bids, payment held by the bank, the delivery and any reported problem. Actions follow the
/// node's rules: the listing farmer accepts or cancels, buyers bid, the sale's parties report problems.
class LotScreen extends StatefulWidget {
  const LotScreen({super.key, required this.lotId, this.initial});
  final String lotId;
  final Lot? initial;

  @override
  State<LotScreen> createState() => _LotScreenState();
}

class _LotScreenState extends State<LotScreen> with Polling<LotScreen, Lot> {
  @override
  Duration get every => const Duration(seconds: 8);

  @override
  void initState() {
    data = widget.initial;
    super.initState();
  }

  @override
  Future<Lot> load() async {
    final lot = (await fetchLots()).where((l) => l.id == widget.lotId).firstOrNull;
    if (lot == null) throw ApiError(404, t('লটটি আর নেই।', 'This lot no longer exists.'));
    return lot;
  }

  void _replace(Object? json) {
    if (json is Map && mounted) setState(() => data = Lot(json.cast<String, dynamic>()));
  }

  Future<void> _accept(Bid bid) async {
    final lot = data!;
    final res = await showModalBottomSheet<Object>(context: context, isScrollControlled: true, builder: (_) => AcceptSheet(lot: lot, bid: bid));
    if (res != null) {
      _replace(res);
      HapticFeedback.heavyImpact();
      if (mounted) snack(context, t('বিক্রি নিশ্চিত: টাকা ব্যাংকের এসক্রোতে জমা আছে।', 'Sold: the payment is held in escrow by the bank.'), icon: Icons.lock_rounded, tone: Tone.green);
    }
  }

  Future<void> _cancel() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t('লটটি বাতিল করবেন?', 'Cancel this lot?')),
        content: Text(t('সব দর বন্ধ হয়ে যাবে। এটি ফেরানো যায় না।', 'All bids close. This cannot be undone.')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(t('না', 'Keep it'))),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Theme.of(context).colorScheme.error),
            onPressed: () => Navigator.pop(context, true),
            child: Text(t('বাতিল করুন', 'Cancel the lot')),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    _replace(await guarded<Object?>(context, () => Api.post('/market/lots/${widget.lotId}/cancel'), done: t('লট বাতিল হয়েছে', 'Lot cancelled')));
  }

  Future<void> _report() async {
    final res = await showModalBottomSheet<Object>(context: context, isScrollControlled: true, builder: (_) => DisputeSheet(lotId: widget.lotId));
    if (res != null) {
      _replace(res);
      if (mounted) snack(context, t('অভিযোগ ব্যাংকে পাঠানো হয়েছে।', 'Reported: the bank will look into it.'), icon: Icons.report_rounded);
    }
  }

  @override
  Widget build(BuildContext context) {
    final lot = data;
    final theme = Theme.of(context);
    if (lot == null) {
      return Scaffold(
        appBar: AppBar(),
        body: error != null ? ErrorState(error: error!, onRetry: refresh) : const SkeletonList(count: 3, height: 140),
      );
    }
    final me = app.user!;
    final isOwner = me.role == 'farmer' && lot.farmerId == me.id;
    final isBuyer = me.role == 'buyer';
    final accepted = lot.acceptedBid;
    final party = isOwner || (accepted != null && accepted.buyerId == me.id) || (lot.delivery?.driverId == me.id);
    return Scaffold(
      appBar: AppBar(
        title: Text('${cropName(lot.crop)} · ${kg(lot.kg)}'),
        actions: [
          if (isOwner && lot.status == 'OPEN')
            IconButton(onPressed: _cancel, icon: const Icon(Icons.delete_outline_rounded), tooltip: t('লট বাতিল', 'Cancel the lot')),
        ],
      ),
      bottomNavigationBar: isBuyer && lot.status == 'OPEN' ? BidBar(lot: lot, onPlaced: _replace) : null,
      body: RefreshIndicator(
        onRefresh: refresh,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
          children: [
            AppCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  GradeStamp(letter: lot.grade, size: 64),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(gradeName(lot.grade), style: theme.textTheme.titleMedium),
                      Text('${lot.farmerName} · ${[lot.upazila, lot.district].where((s) => s.isNotEmpty).join(', ')}',
                          style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                      Text('${t('তালিকাভুক্ত', 'Listed')} ${ago(lot.listedAt)}', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                    ]),
                  ),
                  Pill(lotStatus(lot.status), tone: lotTone(lot.status)),
                ]),
                const SizedBox(height: 16),
                if (lot.status != 'CANCELLED')
                  RouteSteps(
                    steps: [t('তালিকা', 'Listed'), t('বিক্রি', 'Sold'), t('পথে', 'On the road'), t('পৌঁছেছে', 'Delivered')],
                    current: lotStage(lot),
                  ),
                const SizedBox(height: 8),
                if (lot.asking != null) InfoRow(t('চাওয়া দাম', 'Asking price'), perKg(lot.asking)),
                if (isOwner) InfoRow(t('খরচের সীমা', 'Cost floor'), perKg(lot.floor)),
                if (lot.note.isNotEmpty) InfoRow(t('নোট', 'Note'), lot.note),
                if (lot.certId != null) _CertRow(certId: lot.certId!),
              ]),
            ),
            if (lot.escrow != null) ...[const SizedBox(height: 12), EscrowCard(lot: lot)],
            if (lot.delivery != null) ...[const SizedBox(height: 12), DeliveryCard(delivery: lot.delivery!)],
            if (lot.disputes.isNotEmpty) ...[
              SectionTitle(t('অভিযোগ', 'Reported problems')),
              for (final d in lot.disputes) ...[DisputeTile(dispute: d), const SizedBox(height: 8)],
            ],
            if (party && lot.escrow != null) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(onPressed: _report, icon: const Icon(Icons.report_outlined), label: Text(t('সমস্যা জানান', 'Report a problem'))),
            ],
            SectionTitle(
              t('দর', 'Bids'),
              trailing: lot.bids.isEmpty ? null : Text(plural(lot.activeBids.length, 'টি চালু', 'active', 'active'), style: theme.textTheme.bodySmall),
            ),
            if (lot.bids.isEmpty)
              AppCard(child: Text(t('এখনো কেউ দর দেয়নি।', 'No one has bid yet.'), style: theme.textTheme.bodyMedium))
            else
              ..._bids(lot, isOwner),
          ],
        ),
      ),
    );
  }

  List<Widget> _bids(Lot lot, bool isOwner) {
    final me = app.user!.id;
    final active = lot.activeBids;
    final others = lot.bids.where((b) => b.status != 'ACTIVE').toList();
    return [
      for (var i = 0; i < active.length; i++) ...[
        BidTile(
          bid: active[i],
          lot: lot,
          highest: i == 0,
          mine: active[i].buyerId == me,
          onAccept: isOwner && lot.status == 'OPEN' ? () => _accept(active[i]) : null,
        ),
        const SizedBox(height: 8),
      ],
      if (others.isNotEmpty)
        Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text(t('আগের ও বন্ধ দর (${digits(others.length)})', 'Earlier and closed bids (${others.length})'), style: Theme.of(context).textTheme.bodyMedium),
            children: [for (final b in others) BidTile(bid: b, lot: lot, highest: false, mine: b.buyerId == me)],
          ),
        ),
    ];
  }
}

class _CertRow extends StatefulWidget {
  const _CertRow({required this.certId});
  final String certId;

  @override
  State<_CertRow> createState() => _CertRowState();
}

class _CertRowState extends State<_CertRow> {
  bool? _ok;
  bool _busy = false;

  Future<void> _verify() async {
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/edge/verify-certificate', {'cert_id': widget.certId}));
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (res is Map) _ok = res['signature_valid'] == true && res['payload_hash_valid'] == true && res['tampered'] != true;
    });
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Row(children: [
          Icon(Icons.verified_rounded, size: 20, color: Tone.green.fg(context)),
          const SizedBox(width: 8),
          Expanded(child: Text(shortId(widget.certId, keep: 14), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace'))),
          if (_ok == null)
            TextButton(onPressed: _busy ? null : _verify, child: Text(_busy ? '…' : t('যাচাই', 'Verify')))
          else
            Pill(_ok! ? t('সঠিক', 'Valid') : t('বদলানো', 'Tampered'), tone: _ok! ? Tone.green : Tone.rose),
        ]),
      );
}

class BidTile extends StatelessWidget {
  const BidTile({super.key, required this.bid, required this.lot, required this.highest, required this.mine, this.onAccept});
  final Bid bid;
  final Lot lot;
  final bool highest;
  final bool mine;
  final VoidCallback? onAccept;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final below = bid.price < lot.floor;
    final closed = bid.status != 'ACTIVE';
    return AppCard(
      tone: highest ? Tone.green : null,
      padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
              Text(bid.buyerName, style: theme.textTheme.titleSmall),
              if (highest) Pill(t('সর্বোচ্চ', 'Highest'), tone: Tone.green),
              if (mine) Pill(t('আপনি', 'You'), tone: Tone.violet),
              if (closed) Pill(bid.status.toLowerCase(), tone: Tone.slate),
            ]),
            Text('${bid.buyerDistrict} · ${ago(bid.placedAt)}${bid.note.isNotEmpty ? ' · ${bid.note}' : ''}',
                maxLines: 2, overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          ]),
        ),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(perKg(bid.price), style: theme.textTheme.titleMedium?.copyWith(fontFeatures: tabular, color: closed ? theme.colorScheme.onSurfaceVariant : null)),
          Text(money(bid.price * lot.kg), style: theme.textTheme.bodySmall?.copyWith(fontFeatures: tabular)),
          if (below && !closed) Text(t('খরচের নিচে', 'below cost'), style: theme.textTheme.labelSmall?.copyWith(color: Tone.rose.fg(context))),
        ]),
        if (onAccept != null) ...[
          const SizedBox(width: 8),
          FilledButton(
            onPressed: onAccept,
            style: FilledButton.styleFrom(minimumSize: const Size(64, 44), padding: const EdgeInsets.symmetric(horizontal: 14)),
            child: Text(t('গ্রহণ', 'Accept')),
          ),
        ],
      ]),
    );
  }
}

/// Buyer: the bid in reach of the thumb, with quick raises over the highest bid.
class BidBar extends StatefulWidget {
  const BidBar({super.key, required this.lot, required this.onPlaced});
  final Lot lot;
  final void Function(Object? json) onPlaced;

  @override
  State<BidBar> createState() => _BidBarState();
}

class _BidBarState extends State<BidBar> {
  late final _price = TextEditingController(text: _suggest(0.5));
  bool _busy = false;

  // A raise goes over the highest bid, or over the asking price (else the cost floor) while nobody has bid.
  String _suggest(double raise) {
    final lot = widget.lot;
    final base = lot.best?.price ?? lot.asking ?? lot.floor;
    return (base + raise).toStringAsFixed(2);
  }

  @override
  void dispose() {
    _price.dispose();
    super.dispose();
  }

  Future<void> _place() async {
    final price = double.tryParse(_price.text.trim());
    if (price == null || price <= 0 || price > 500) {
      snack(context, t('৳০ থেকে ৳৫০০-এর মধ্যে কেজিপ্রতি দাম লিখুন।', 'Enter a price per kg between Tk 0 and Tk 500.'), tone: Tone.amber);
      return;
    }
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/market/lots/${widget.lot.id}/bids', {'price_tk_per_kg': price}),
        done: t('আপনার দর দেওয়া হয়েছে', 'Your bid is in'));
    if (!mounted) return;
    setState(() => _busy = false);
    if (res != null) {
      HapticFeedback.mediumImpact();
      widget.onPlaced(res);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final lot = widget.lot;
    final mine = lot.activeBids.where((b) => b.buyerId == app.user!.id).firstOrNull;
    final leading = mine != null && lot.best?.id == mine.id;
    final price = double.tryParse(_price.text) ?? 0;
    return Material(
      color: theme.colorScheme.surfaceContainerLowest,
      elevation: 8,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: EdgeInsets.fromLTRB(16, 12, 16, 12 + MediaQuery.viewInsetsOf(context).bottom),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Expanded(
                child: Text(
                  mine == null
                      ? t('সর্বোচ্চ ${lot.best == null ? '–' : perKg(lot.best!.price)}', 'Highest ${lot.best == null ? '–' : perKg(lot.best!.price)}')
                      : leading
                          ? t('আপনার দর সবার উপরে', 'Your bid leads')
                          : t('আপনাকে ছাড়িয়ে গেছে, দর বাড়ান', 'You were outbid; raise your bid'),
                  style: theme.textTheme.titleSmall?.copyWith(color: mine == null ? null : (leading ? Tone.green.fg(context) : Tone.rose.fg(context))),
                ),
              ),
              Text('= ${money(price * lot.kg)}', style: theme.textTheme.titleSmall?.copyWith(fontFeatures: tabular)),
            ]),
            const SizedBox(height: 10),
            Row(children: [
              for (final raise in [0.25, 0.5, 1.0]) ...[
                if (raise != 0.25) const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(minimumSize: const Size(0, 44), padding: EdgeInsets.zero),
                    onPressed: () => setState(() => _price.text = _suggest(raise)),
                    child: Text('+${digits(raise.toStringAsFixed(2))}'),
                  ),
                ),
              ],
            ]),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _price,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                  onChanged: (_) => setState(() {}),
                  style: theme.textTheme.titleMedium?.copyWith(fontFeatures: tabular),
                  decoration: InputDecoration(prefixText: '৳ ', suffixText: '/${t('কেজি', 'kg')}'),
                ),
              ),
              const SizedBox(width: 10),
              FilledButton.icon(
                onPressed: _busy ? null : _place,
                icon: _busy ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.gavel_rounded),
                label: Text(mine == null ? t('দর দিন', 'Bid') : t('বাড়ান', 'Raise')),
              ),
            ]),
          ]),
        ),
      ),
    );
  }
}

/// The farmer accepts a bid: the buyer's payment is locked in escrow (simulated) and released on delivery.
class AcceptSheet extends StatefulWidget {
  const AcceptSheet({super.key, required this.lot, required this.bid});
  final Lot lot;
  final Bid bid;

  @override
  State<AcceptSheet> createState() => _AcceptSheetState();
}

class _AcceptSheetState extends State<AcceptSheet> {
  String _wallet = 'bKash';
  final _number = TextEditingController();
  bool _belowOk = false;
  bool _busy = false;

  @override
  void dispose() {
    _number.dispose();
    super.dispose();
  }

  // Bangla digits typed on a Bangla keyboard count too.
  String get _ascii => _number.text.trim().split('').map((c) {
        final i = '০১২৩৪৫৬৭৮৯'.indexOf(c);
        return i >= 0 ? '$i' : c;
      }).join();

  bool get _valid => RegExp(r'^01[3-9]\d{8}$').hasMatch(_ascii);

  Future<void> _confirm() async {
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/market/lots/${widget.lot.id}/accept', {
          'bid_id': widget.bid.id,
          'wallet': _wallet,
          'wallet_number': _ascii,
          'accept_below_floor': _belowOk,
        }));
    if (!mounted) return;
    setState(() => _busy = false);
    if (res != null) Navigator.pop(context, res);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final lot = widget.lot;
    final bid = widget.bid;
    final below = bid.price < lot.floor;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(t('${bid.buyerName}-এর দর গ্রহণ', 'Accept ${bid.buyerName}\'s bid'), style: theme.textTheme.titleLarge),
          const SizedBox(height: 12),
          AppCard(
            tone: Tone.green,
            child: Column(children: [
              InfoRow(t('দাম', 'Price'), perKg(bid.price)),
              InfoRow(t('পরিমাণ', 'Quantity'), kg(lot.kg)),
              InfoRow(t('মোট', 'Total'), money(bid.price * lot.kg), strong: true),
            ]),
          ),
          if (below) ...[
            const SizedBox(height: 12),
            AppCard(
              tone: Tone.rose,
              padding: const EdgeInsets.fromLTRB(8, 4, 12, 4),
              child: CheckboxListTile(
                value: _belowOk,
                onChanged: (v) => setState(() => _belowOk = v ?? false),
                controlAffinity: ListTileControlAffinity.leading,
                contentPadding: EdgeInsets.zero,
                title: Text(t('দামটি উৎপাদন খরচের (${perKg(lot.floor)}) নিচে। জেনেশুনে বিক্রি করছি।',
                    'This is below the ${perKg(lot.floor)} production cost. I am selling knowingly.')),
              ),
            ),
          ],
          const SizedBox(height: 16),
          Text(t('টাকা কোন ওয়ালেটে আসবে?', 'Which wallet should receive the money?'), style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            segments: const [ButtonSegment(value: 'bKash', label: Text('bKash')), ButtonSegment(value: 'Nagad', label: Text('Nagad'))],
            selected: {_wallet},
            onSelectionChanged: (s) => setState(() => _wallet = s.first),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _number,
            keyboardType: TextInputType.phone,
            maxLength: 11,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              labelText: t('ওয়ালেট নম্বর', 'Wallet number'),
              hintText: '01XXXXXXXXX',
              helperText: t('নম্বরের শুধু শেষ অংশ সংরক্ষিত থাকে।', 'Only a masked form of the number is stored.'),
              errorText: _number.text.isNotEmpty && !_valid ? t('০১ দিয়ে শুরু ১১ সংখ্যার নম্বর দিন', 'Enter an 11-digit number starting 01') : null,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            t('ক্রেতার টাকা ব্যাংকের এসক্রোতে আটকে থাকবে, মাল পৌঁছালে আপনার ওয়ালেটে যাবে (ডেমোতে কোনো আসল টাকা নড়ে না)।',
                'The buyer\'s money is held in escrow by the bank and paid to your wallet on delivery (simulated: no real money moves).'),
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy || !_valid || (below && !_belowOk) ? null : _confirm,
            icon: _busy ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.lock_rounded),
            label: Text(t('বিক্রি নিশ্চিত করুন', 'Confirm the sale')),
          ),
        ]),
      ),
    );
  }
}

class EscrowCard extends StatelessWidget {
  const EscrowCard({super.key, required this.lot});
  final Lot lot;

  @override
  Widget build(BuildContext context) {
    final e = lot.escrow!;
    final theme = Theme.of(context);
    final tone = switch (e.status) { 'RELEASED' => Tone.green, 'REFUNDED' => Tone.rose, _ => Tone.violet };
    return AppCard(
      tone: tone,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.account_balance_wallet_rounded, color: tone.fg(context)),
          const SizedBox(width: 8),
          Expanded(child: Text(escrowStatus(e.status), style: theme.textTheme.titleSmall)),
          CountUp(value: e.amount, format: (v) => money(v), style: theme.textTheme.titleLarge?.copyWith(color: tone.fg(context))),
        ]),
        const SizedBox(height: 6),
        InfoRow(t('ক্রেতা', 'Buyer'), lot.acceptedBid?.buyerName ?? '–'),
        InfoRow(t('ওয়ালেট', 'Wallet'), '${e.wallet} ${e.walletMasked}'),
        InfoRow(t('এসক্রো', 'Escrow'), e.id, mono: true),
      ]),
    );
  }
}

class DeliveryCard extends StatelessWidget {
  const DeliveryCard({super.key, required this.delivery});
  final Delivery delivery;

  @override
  Widget build(BuildContext context) {
    final d = delivery;
    final theme = Theme.of(context);
    return AppCard(
      tone: d.atRisk ? Tone.rose : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.local_shipping_rounded, color: (d.atRisk ? Tone.rose : Tone.sky).fg(context)),
          const SizedBox(width: 8),
          Expanded(child: Text(deliveryStatus(d.status), style: theme.textTheme.titleSmall)),
          if (d.atRisk) Pill(t('পচনের ঝুঁকি', 'Spoilage risk'), tone: Tone.rose, icon: Icons.warning_rounded),
        ]),
        const SizedBox(height: 6),
        InfoRow(t('পথ', 'Route'), '${d.origin} → ${d.destination} · ${num1(d.km, decimals: 1)} ${t('কিমি', 'km')}'),
        InfoRow(t('সময়', 'Drive time'), '${num1(d.etaHours, decimals: 1)} ${t('ঘণ্টা', 'h')}'),
        if (d.driverName != null) InfoRow(t('চালক', 'Driver'), d.driverName!),
        if (d.lastTemp != null) InfoRow(t('তাপমাত্রা', 'Temperature'), '${num1(d.lastTemp!, decimals: 1)}°C · ${pct(d.lastRh, decimals: 0)} RH'),
        if (d.shelfLifeHours != null) InfoRow(t('টেকসই থাকবে', 'Shelf life left'), '${num1(d.shelfLifeHours!, decimals: 0)} ${t('ঘণ্টা', 'h')}'),
      ]),
    );
  }
}

class DisputeTile extends StatelessWidget {
  const DisputeTile({super.key, required this.dispute, this.trailing});
  final Dispute dispute;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final d = dispute;
    final theme = Theme.of(context);
    final open = d.status == 'OPEN';
    return AppCard(
      tone: open ? Tone.amber : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(disputeKind(d.kind), style: theme.textTheme.titleSmall)),
          Pill(open ? t('খোলা', 'Open') : t('মীমাংসিত', 'Resolved'), tone: open ? Tone.amber : Tone.green),
        ]),
        const SizedBox(height: 4),
        Text('${d.raisedByName} (${roleName(d.raisedByRole)}) · ${ago(d.openedAt)}', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
        if (d.note.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(d.note, style: theme.textTheme.bodyMedium)),
        if (d.resolution != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('${t('সিদ্ধান্ত', 'Decision')}: ${resolutionName(d.resolution!)}${d.resolutionNote.isNotEmpty ? ' · ${d.resolutionNote}' : ''}',
                style: theme.textTheme.bodySmall),
          ),
        ?trailing,
      ]),
    );
  }
}

/// A sale's farmer, buyer or driver reports a problem to the bank (the note is scrubbed of personal details).
class DisputeSheet extends StatefulWidget {
  const DisputeSheet({super.key, required this.lotId});
  final String lotId;

  @override
  State<DisputeSheet> createState() => _DisputeSheetState();
}

class _DisputeSheetState extends State<DisputeSheet> {
  String _kind = 'PAYMENT_NOT_RECEIVED';
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/market/lots/${widget.lotId}/disputes', {'kind': _kind, 'note': _note.text.trim()}));
    if (!mounted) return;
    setState(() => _busy = false);
    if (res != null) Navigator.pop(context, res);
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(t('কী সমস্যা হয়েছে?', 'What went wrong?'), style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final k in disputeKinds) ChoiceChip(label: Text(disputeKind(k)), selected: _kind == k, onSelected: (_) => setState(() => _kind = k)),
          ]),
          const SizedBox(height: 12),
          TextField(
            controller: _note,
            maxLength: 300,
            maxLines: 3,
            decoration: InputDecoration(hintText: t('একটু খুলে বলুন (নাম-নম্বর লুকিয়ে রাখা হবে)', 'Tell the bank a little more (names and numbers are hidden)')),
          ),
          FilledButton.icon(
            onPressed: _busy ? null : _send,
            icon: const Icon(Icons.send_rounded),
            label: Text(t('ব্যাংকে পাঠান', 'Send to the bank')),
          ),
        ]),
      );
}

/// List a lot on the direct market; a grade or a decision may have filled it in.
class SellSheet extends StatefulWidget {
  const SellSheet({super.key, this.draft});
  final Map<String, dynamic>? draft;

  @override
  State<SellSheet> createState() => _SellSheetState();
}

class _SellSheetState extends State<SellSheet> {
  late String _crop = marketCrops.contains(widget.draft?['crop']) ? widget.draft!['crop'] as String : marketCrops.first;
  late String _grade = ['A', 'B', 'C'].contains(widget.draft?['grade']) ? widget.draft!['grade'] as String : 'B';
  late String? _cert = widget.draft?['certificate_id'] as String?;
  String _unit = 'kg';
  late final _qty = TextEditingController(text: numOf(widget.draft?['weight_kg']) > 0 ? numOf(widget.draft?['weight_kg']).toStringAsFixed(0) : '');
  final _price = TextEditingController();
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _qty.dispose();
    _price.dispose();
    _note.dispose();
    super.dispose();
  }

  double get _kg => (double.tryParse(_qty.text) ?? 0) * (_unit == 'maund' ? 40 : 1);

  Future<void> _list() async {
    final user = app.user!;
    final price = double.tryParse(_price.text);
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/market/lots', {
          'crop': _crop,
          'grade': _grade,
          'weight_kg': _kg,
          'district': (widget.draft?['district'] as String?)?.isNotEmpty == true ? widget.draft!['district'] : (user.district.isEmpty ? 'Bogura' : user.district),
          if ((widget.draft?['upazila'] as String?)?.isNotEmpty == true) 'upazila': widget.draft!['upazila'],
          if (price != null && price > 0) 'asking_price_tk_per_kg': price,
          'certificate_id': ?_cert,
          if (_note.text.trim().isNotEmpty) 'note': _note.text.trim(),
        }));
    if (!mounted) return;
    setState(() => _busy = false);
    if (res is Map) {
      HapticFeedback.heavyImpact();
      Navigator.pop(context, Lot(res.cast<String, dynamic>()));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final valid = _kg >= 50 && _kg <= 20000;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(t('নতুন লট দিন', 'List a lot'), style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(t('ক্রেতারা খোলাখুলি দর দেবেন; আপনি যেটা চান সেটা গ্রহণ করবেন।', 'Buyers bid in the open; you accept the one you want.'),
              style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          const SizedBox(height: 14),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final c in marketCrops)
              ChoiceChip(
                label: Text(cropName(c)),
                selected: _crop == c,
                onSelected: (_) => setState(() {
                  _crop = c;
                  _cert = null; // a certificate belongs to one crop
                }),
              ),
          ]),
          const SizedBox(height: 14),
          Row(children: [
            Text(t('গ্রেড', 'Grade'), style: theme.textTheme.titleSmall),
            const SizedBox(width: 12),
            Expanded(
              child: SegmentedButton<String>(
                segments: const [ButtonSegment(value: 'A', label: Text('A')), ButtonSegment(value: 'B', label: Text('B')), ButtonSegment(value: 'C', label: Text('C'))],
                selected: {_grade},
                onSelectionChanged: _cert == null ? (s) => setState(() => _grade = s.first) : null,
              ),
            ),
          ]),
          if (_cert != null) ...[
            const SizedBox(height: 10),
            InputChip(
              avatar: const Icon(Icons.verified_rounded, size: 18),
              label: Text(t('সনদ যুক্ত: ${shortId(_cert!, keep: 12)}', 'Certificate attached: ${shortId(_cert!, keep: 12)}')),
              onDeleted: () => setState(() => _cert = null),
            ),
          ],
          const SizedBox(height: 14),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _qty,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  labelText: t('পরিমাণ', 'Quantity'),
                  helperText: _unit == 'maund' && _kg > 0 ? '= ${kg(_kg)}' : t('কমপক্ষে ৫০ কেজি', 'At least 50 kg'),
                ),
              ),
            ),
            const SizedBox(width: 10),
            SegmentedButton<String>(
              showSelectedIcon: false,
              segments: [ButtonSegment(value: 'kg', label: Text(t('কেজি', 'kg'))), ButtonSegment(value: 'maund', label: Text(t('মণ', 'maund')))],
              selected: {_unit},
              onSelectionChanged: (s) => setState(() => _unit = s.first),
            ),
          ]),
          const SizedBox(height: 12),
          TextField(
            controller: _price,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
            decoration: InputDecoration(labelText: t('চাওয়া দাম (ঐচ্ছিক)', 'Asking price (optional)'), prefixText: '৳ ', suffixText: '/${t('কেজি', 'kg')}'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _note,
            maxLength: 200,
            decoration: InputDecoration(labelText: t('নোট (ঐচ্ছিক)', 'Note (optional)'), hintText: t('যেমন: বস্তায় ভরা, শনিবার পর্যন্ত', 'e.g. bagged, ready until Saturday')),
          ),
          FilledButton.icon(
            onPressed: _busy || !valid ? null : _list,
            icon: _busy ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.storefront_rounded),
            label: Text(valid ? t('${kg(_kg)} বাজারে দিন', 'List ${kg(_kg)}') : t('বাজারে দিন', 'List it')),
          ),
        ]),
      ),
    );
  }
}

/// Buyer: lots won (payment, delivery) and lots still being bid on.
class PurchasesScreen extends StatefulWidget {
  const PurchasesScreen({super.key});

  @override
  State<PurchasesScreen> createState() => _PurchasesScreenState();
}

class _PurchasesScreenState extends State<PurchasesScreen> with Polling<PurchasesScreen, List<Lot>> {
  @override
  Future<List<Lot>> load() => fetchLots();

  @override
  Widget build(BuildContext context) {
    final me = app.user!.id;
    final lots = data ?? const <Lot>[];
    final won = lots.where((l) => l.acceptedBid?.buyerId == me).toList();
    final bidding = lots.where((l) => l.status == 'OPEN' && l.activeBids.any((b) => b.buyerId == me)).toList();
    Future<void> open(Lot lot) async {
      await Navigator.of(context).push(fadeRoute(LotScreen(lotId: lot.id, initial: lot)));
      refresh(quiet: true);
    }

    return Scaffold(
      appBar: AppBar(title: Text(t('আমার কেনা', 'My purchases'))),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: loading && data == null
            ? const SkeletonList()
            : error != null && data == null
                ? ListView(children: [ErrorState(error: error!, onRetry: refresh)])
                : ListView(padding: const EdgeInsets.fromLTRB(16, 0, 16, 32), children: [
                    SectionTitle(t('কেনা লট', 'Won lots'), top: 8),
                    if (won.isEmpty)
                      AppCard(child: Text(t('এখনো কোনো লট জেতেননি। কৃষক আপনার দর গ্রহণ করলে এখানে আসবে।', 'No lots won yet. A lot appears here when a farmer accepts your bid.')))
                    else
                      for (final l in won) ...[_PurchaseCard(lot: l, onTap: () => open(l)), const SizedBox(height: 12)],
                    SectionTitle(t('যেখানে দর দিয়েছেন', 'Bidding on')),
                    if (bidding.isEmpty)
                      AppCard(child: Text(t('কোনো খোলা দর নেই।', 'No open bids.')))
                    else
                      for (final l in bidding) ...[LotCard(lot: l, onTap: () => open(l)), const SizedBox(height: 12)],
                  ]),
      ),
    );
  }
}

class _PurchaseCard extends StatelessWidget {
  const _PurchaseCard({required this.lot, required this.onTap});
  final Lot lot;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AppCard(
      onTap: onTap,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('${cropName(lot.crop)} · ${kg(lot.kg)} · ${lot.farmerName}', style: theme.textTheme.titleSmall)),
          Pill(lotStatus(lot.status), tone: lotTone(lot.status)),
        ]),
        const SizedBox(height: 12),
        RouteSteps(steps: [t('তালিকা', 'Listed'), t('বিক্রি', 'Sold'), t('পথে', 'On the road'), t('পৌঁছেছে', 'Delivered')], current: lotStage(lot)),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: Text(lot.escrow == null ? '' : escrowStatus(lot.escrow!.status), style: theme.textTheme.bodySmall)),
          Text(money(lot.escrow?.amount), style: theme.textTheme.titleSmall?.copyWith(fontFeatures: tabular)),
        ]),
      ]),
    );
  }
}

/// Buyer: check any certificate the node issued (POST /edge/verify-certificate).
class VerifyScreen extends StatefulWidget {
  const VerifyScreen({super.key});

  @override
  State<VerifyScreen> createState() => _VerifyScreenState();
}

class _VerifyScreenState extends State<VerifyScreen> with Polling<VerifyScreen, List<Lot>> {
  final _id = TextEditingController();
  Map<String, dynamic>? _result;
  bool _busy = false;

  @override
  Duration get every => const Duration(seconds: 30);

  @override
  Future<List<Lot>> load() => fetchLots();

  @override
  void dispose() {
    _id.dispose();
    super.dispose();
  }

  Future<void> _verify([String? id]) async {
    final certId = (id ?? _id.text).trim().toUpperCase();
    if (certId.isEmpty) return;
    _id.text = certId;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/edge/verify-certificate', {'cert_id': certId}));
    if (!mounted) return;
    setState(() {
      _busy = false;
      _result = res is Map ? res.cast<String, dynamic>() : null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final certified = (data ?? const <Lot>[]).where((l) => l.certId != null && l.status == 'OPEN').toList();
    final r = _result;
    final ok = r != null && r['known'] == true && r['signature_valid'] == true && r['payload_hash_valid'] == true && r['tampered'] != true;
    return Scaffold(
      appBar: AppBar(title: Text(t('সনদ যাচাই', 'Verify a certificate'))),
      body: ListView(padding: const EdgeInsets.fromLTRB(20, 4, 20, 32), children: [
        Text(t('কৃষকের ছবি-গ্রেডের সনদ আসল কিনা দেখুন', 'Check that a farmer\'s photo-grade certificate is genuine'), style: theme.textTheme.headlineSmall),
        const SizedBox(height: 16),
        TextField(
          controller: _id,
          textCapitalization: TextCapitalization.characters,
          onSubmitted: (_) => _verify(),
          decoration: InputDecoration(
            labelText: t('সনদ নম্বর', 'Certificate number'),
            hintText: 'DQC-EDGE-CAR-…',
            suffixIcon: IconButton(
              onPressed: () async {
                final clip = await Clipboard.getData(Clipboard.kTextPlain);
                if (clip?.text != null) _id.text = clip!.text!.trim();
              },
              icon: const Icon(Icons.content_paste_rounded),
              tooltip: t('পেস্ট', 'Paste'),
            ),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: _busy ? null : _verify,
          icon: _busy ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.shield_rounded),
          label: Text(t('যাচাই করুন', 'Verify')),
        ),
        AnimatedSwitcher(
          duration: Motion.of(context, Motion.medium),
          child: r == null
              ? const SizedBox.shrink()
              : Padding(
                  key: ValueKey(r['cert_id']),
                  padding: const EdgeInsets.only(top: 16),
                  child: AppCard(
                    tone: ok ? Tone.green : Tone.rose,
                    strong: true,
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Icon(ok ? Icons.verified_rounded : Icons.gpp_bad_rounded, color: (ok ? Tone.green : Tone.rose).fg(context), size: 32),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(ok ? t('আসল সনদ', 'Genuine certificate') : (r['known'] == true ? t('সনদটি বদলানো হয়েছে', 'This certificate was changed') : t('এই নোডের সনদ নয়', 'Not issued by this node')),
                              style: theme.textTheme.titleMedium),
                        ),
                      ]),
                      const SizedBox(height: 8),
                      InfoRow(t('নোডে আছে', 'Known to node'), r['known'] == true ? t('হ্যাঁ', 'Yes') : t('না', 'No')),
                      InfoRow(t('স্বাক্ষর', 'Signature'), r['signature_valid'] == true ? t('ঠিক', 'Valid') : t('ভুল', 'Invalid')),
                      InfoRow(t('তথ্যের হ্যাশ', 'Data hash'), r['payload_hash_valid'] == true ? t('ঠিক', 'Valid') : t('ভুল', 'Invalid')),
                      for (final w in stringsOf(r['warnings'])) Padding(padding: const EdgeInsets.only(top: 6), child: Pill(w, tone: Tone.amber, icon: Icons.warning_amber_rounded)),
                    ]),
                  ),
                ),
        ),
        if (certified.isNotEmpty) ...[
          SectionTitle(t('বাজারে সনদওয়ালা লট', 'Certified lots on the market')),
          for (final l in certified)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: AppCard(
                onTap: () => _verify(l.certId),
                padding: const EdgeInsets.all(12),
                child: Row(children: [
                  GradeStamp(letter: l.grade, size: 40),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${cropName(l.crop)} · ${kg(l.kg)} · ${l.farmerName}', style: theme.textTheme.titleSmall),
                      Text(shortId(l.certId!, keep: 14), style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
                    ]),
                  ),
                  const Icon(Icons.chevron_right_rounded),
                ]),
              ),
            ),
        ],
      ]),
    );
  }
}
