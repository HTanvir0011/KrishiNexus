import 'dart:async';

import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'market.dart';
import 'scan.dart' show fadeRoute;

Future<List<Lot>> fetchJobs() async => mapsOf(await Api.get('/market/deliveries')).map(Lot.new).where((l) => l.delivery != null).toList();

int jobStage(String status) => switch (status) { 'AWAITING_DRIVER' => 0, 'ASSIGNED' => 1, 'PICKED_UP' => 2, 'DELIVERED' => 3, _ => 0 };

/// Driver: jobs waiting for a truck, own jobs and finished ones. Judge and admin: every job, read only.
class JobsScreen extends StatefulWidget {
  const JobsScreen({super.key});

  @override
  State<JobsScreen> createState() => _JobsScreenState();
}

class _JobsScreenState extends State<JobsScreen> with Polling<JobsScreen, List<Lot>> {
  @override
  Future<List<Lot>> load() => fetchJobs();

  bool get _driver => app.user?.role == 'driver';

  Future<void> _claim(Lot lot) async {
    final res = await guarded(context, () => Api.post('/market/deliveries/${lot.id}/claim'), done: t('কাজটি আপনার', 'The job is yours'));
    if (res != null) {
      HapticFeedback.heavyImpact();
      await refresh(quiet: true);
      app.goTab('active');
    }
  }

  Future<void> _open(Lot lot) async {
    await Navigator.of(context).push(fadeRoute(JobScreen(lotId: lot.id, initial: lot)));
    refresh(quiet: true);
  }

  @override
  Widget build(BuildContext context) {
    final me = app.user!.id;
    final jobs = data ?? const <Lot>[];
    final mine = jobs.where((l) => l.delivery!.driverId == me && l.delivery!.status != 'DELIVERED').toList();
    final open = jobs.where((l) => l.delivery!.status == 'AWAITING_DRIVER' && l.escrow?.status != 'REFUNDED').toList();
    final done = jobs.where((l) => l.delivery!.status == 'DELIVERED' && (!_driver || l.delivery!.driverId == me)).toList();
    final others = _driver ? const <Lot>[] : jobs.where((l) => l.delivery!.status != 'AWAITING_DRIVER' && l.delivery!.status != 'DELIVERED').toList();
    return Scaffold(
      appBar: AppBar(title: Text(_driver ? t('ডেলিভারির কাজ', 'Delivery jobs') : t('সব ডেলিভারি', 'All deliveries')), actions: const [LiveDot()]),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: loading && data == null
            ? const SkeletonList()
            : error != null && data == null
                ? ListView(children: [ErrorState(error: error!, onRetry: refresh)])
                : ListView(padding: const EdgeInsets.fromLTRB(16, 0, 16, 32), children: [
                    if (mine.isNotEmpty) ...[
                      SectionTitle(t('আমার চলতি কাজ', 'My jobs on the road'), top: 8),
                      for (final l in mine) ...[JobCard(lot: l, onTap: () => _open(l)), const SizedBox(height: 12)],
                    ],
                    if (others.isNotEmpty) ...[
                      SectionTitle(t('পথে', 'On the road'), top: 8),
                      for (final l in others) ...[JobCard(lot: l, onTap: () => _open(l)), const SizedBox(height: 12)],
                    ],
                    SectionTitle(t('চালকের অপেক্ষায়', 'Waiting for a driver'), top: mine.isEmpty && others.isEmpty ? 8 : 24),
                    if (open.isEmpty)
                      AppCard(child: Text(t('এখন কোনো নতুন কাজ নেই। কৃষক বিক্রি নিশ্চিত করলে এখানে আসবে।', 'No new jobs right now. A job appears when a farmer confirms a sale.')))
                    else
                      for (final l in open) ...[
                        JobCard(lot: l, onTap: () => _open(l), action: _driver ? FilledButton.icon(onPressed: () => _claim(l), icon: const Icon(Icons.add_task_rounded), label: Text(t('কাজটি নিন', 'Take this job'))) : null),
                        const SizedBox(height: 12),
                      ],
                    if (done.isNotEmpty) ...[
                      SectionTitle(t('শেষ হয়েছে', 'Delivered')),
                      for (final l in done) ...[JobCard(lot: l, onTap: () => _open(l)), const SizedBox(height: 12)],
                    ],
                  ]),
      ),
    );
  }
}

class JobCard extends StatelessWidget {
  const JobCard({super.key, required this.lot, required this.onTap, this.action});
  final Lot lot;
  final VoidCallback onTap;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final d = lot.delivery!;
    final theme = Theme.of(context);
    return AppCard(
      onTap: onTap,
      tone: d.atRisk ? Tone.rose : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Expanded(child: Text('${cropName(lot.crop)} · ${kg(lot.kg)}', style: theme.textTheme.titleMedium)),
          Pill(deliveryStatus(d.status), tone: d.status == 'DELIVERED' ? Tone.green : d.status == 'AWAITING_DRIVER' ? Tone.amber : Tone.sky),
        ]),
        const SizedBox(height: 10),
        RouteLine(delivery: d, height: 44),
        const SizedBox(height: 8),
        if (truckLine(d) case final line?) ...[TruckLine(text: line), const SizedBox(height: 4)],
        Row(children: [
          Expanded(
            child: Text('${num1(d.km, decimals: 1)} ${t('কিমি', 'km')} · ${num1(d.etaHours, decimals: 1)} ${t('ঘণ্টা', 'h')} · ${lot.farmerName} → ${lot.acceptedBid?.buyerName ?? ''}',
                maxLines: 2, overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          ),
          if (d.atRisk) Pill(t('ঝুঁকি', 'At risk'), tone: Tone.rose, icon: Icons.warning_rounded),
        ]),
        if (action != null) ...[const SizedBox(height: 12), action!],
      ]),
    );
  }
}

/// Origin and destination with the truck placed by the distance it has covered (its last shared position), else by
/// the job's stage; it drives on as either advances.
class RouteLine extends StatelessWidget {
  const RouteLine({super.key, required this.delivery, this.height = 64});
  final Delivery delivery;
  final double height;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final stage = jobStage(delivery.status);
    final p = stage == 3 ? 1.0 : delivery.progress ?? switch (stage) { 0 || 1 => 0.0, 2 => 0.55, _ => 1.0 };
    final fg = (delivery.atRisk ? Tone.rose : Tone.green).fg(context);
    return SizedBox(
      height: height,
      child: LayoutBuilder(builder: (context, box) {
        final w = box.maxWidth;
        return Stack(clipBehavior: Clip.none, children: [
          Positioned(left: 8, right: 8, top: height / 2 - 1.5, child: Container(height: 3, decoration: BoxDecoration(color: theme.colorScheme.outlineVariant, borderRadius: BorderRadius.circular(2)))),
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: p),
            duration: Motion.of(context, const Duration(milliseconds: 1200)),
            curve: Motion.expo,
            builder: (context, v, _) => Stack(clipBehavior: Clip.none, children: [
              Positioned(left: 8, top: height / 2 - 1.5, child: Container(width: (w - 16) * v, height: 3, color: fg)),
              Positioned(
                left: 8 + (w - 16) * v - 16,
                top: height / 2 - 30,
                child: Icon(Icons.local_shipping_rounded, size: 32, color: fg),
              ),
            ]),
          ),
          Positioned(left: 0, top: height / 2 - 8, child: _Dot(color: fg)),
          Positioned(right: 0, top: height / 2 - 8, child: _Dot(color: stage == 3 ? fg : theme.colorScheme.outline)),
          Positioned(left: 0, bottom: -4, child: Text(delivery.origin, style: theme.textTheme.labelMedium)),
          Positioned(right: 0, bottom: -4, child: Text(delivery.destination, style: theme.textTheme.labelMedium)),
        ]);
      }),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.color});
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        width: 16,
        height: 16,
        decoration: BoxDecoration(shape: BoxShape.circle, color: Theme.of(context).colorScheme.surfaceContainerLowest, border: Border.all(color: color, width: 4)),
      );
}

/// The driver's job on the road (the first one assigned or picked up).
class ActiveJobScreen extends StatefulWidget {
  const ActiveJobScreen({super.key});

  @override
  State<ActiveJobScreen> createState() => _ActiveJobScreenState();
}

class _ActiveJobScreenState extends State<ActiveJobScreen> with Polling<ActiveJobScreen, List<Lot>> {
  String? _pick; // the job chosen when the driver has several on the road

  @override
  Future<List<Lot>> load() => fetchJobs();

  @override
  Widget build(BuildContext context) {
    final me = app.user!.id;
    final active = (data ?? const <Lot>[])
        .where((l) => l.delivery!.driverId == me && (l.delivery!.status == 'ASSIGNED' || l.delivery!.status == 'PICKED_UP'))
        .toList();
    final job = active.where((l) => l.id == _pick).firstOrNull ?? active.firstOrNull;
    return Scaffold(
      appBar: AppBar(
        title: Text(t('চলতি ডেলিভারি', 'On the road')),
        actions: const [LiveDot()],
        bottom: active.length < 2
            ? null
            : PreferredSize(
                preferredSize: const Size.fromHeight(56),
                child: SizedBox(
                  height: 56,
                  child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.fromLTRB(16, 4, 16, 8), children: [
                    for (final l in active)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text('${cropName(l.crop)} · ${kg(l.kg)}'),
                          selected: l.id == job?.id,
                          onSelected: (_) => setState(() => _pick = l.id),
                        ),
                      ),
                  ]),
                ),
              ),
      ),
      body: loading && data == null
          ? const SkeletonList(count: 3, height: 140)
          : error != null && data == null
              ? ErrorState(error: error!, onRetry: refresh)
              : job == null
                  ? RefreshIndicator(
                      onRefresh: refresh,
                      child: ListView(children: [
                        EmptyState(
                          icon: Icons.local_shipping_rounded,
                          title: t('এখন পথে কোনো মাল নেই', 'Nothing on the road right now'),
                          body: t('কাজের তালিকা থেকে একটি কাজ নিন।', 'Take a job from the jobs list.'),
                          action: FilledButton.icon(onPressed: () => app.goTab('jobs'), icon: const Icon(Icons.list_alt_rounded), label: Text(t('কাজের তালিকা', 'Jobs list'))),
                        ),
                      ]),
                    )
                  : JobView(
                      key: ValueKey(job.id), // a new job starts with its own sliders and scroll position
                      lot: job,
                      onChanged: (lot) => setState(() => data = [lot, ...?data?.where((l) => l.id != lot.id)]),
                      onRefresh: refresh,
                    ),
    );
  }
}

/// A job opened from a list.
class JobScreen extends StatefulWidget {
  const JobScreen({super.key, required this.lotId, this.initial});
  final String lotId;
  final Lot? initial;

  @override
  State<JobScreen> createState() => _JobScreenState();
}

class _JobScreenState extends State<JobScreen> with Polling<JobScreen, Lot> {
  @override
  bool relevant(MarketEvent e) => e.lotId == null || e.lotId == widget.lotId;

  @override
  void initState() {
    data = widget.initial;
    super.initState();
  }

  @override
  Future<Lot> load() async {
    final lot = (await fetchJobs()).where((l) => l.id == widget.lotId).firstOrNull;
    if (lot == null) throw ApiError(404, t('কাজটি আর নেই।', 'This job is no longer listed.'));
    return lot;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(data == null ? '' : '${cropName(data!.crop)} · ${kg(data!.kg)}'), actions: const [LiveDot()]),
        body: data == null
            ? (error != null ? ErrorState(error: error!, onRetry: refresh) : const SkeletonList(count: 3, height: 140))
            : JobView(lot: data!, onChanged: (lot) => setState(() => data = lot), onRefresh: refresh),
      );
}

/// Route, stage, the next step, the temperature log with its shelf-life check, events and problem reporting.
class JobView extends StatefulWidget {
  const JobView({super.key, required this.lot, required this.onChanged, required this.onRefresh});
  final Lot lot;
  final void Function(Lot lot) onChanged;
  final Future<void> Function() onRefresh;

  @override
  State<JobView> createState() => _JobViewState();
}

class _JobViewState extends State<JobView> {
  late double _temp = widget.lot.delivery?.lastTemp ?? 24;
  late double _rh = widget.lot.delivery?.lastRh ?? 85;
  bool _busy = false;

  bool get _mine => widget.lot.delivery?.driverId == app.user?.id && app.user?.role == 'driver';

  Future<void> _step(String step, {String? done}) async {
    setState(() => _busy = true);
    final body = step == 'temperature' ? {'temp_c': _temp, 'rh_pct': _rh} : const <String, dynamic>{};
    final res = await guarded(context, () => Api.post('/market/deliveries/${widget.lot.id}/$step', body), done: done);
    if (!mounted) return;
    setState(() => _busy = false);
    if (res is Map) {
      HapticFeedback.mediumImpact();
      widget.onChanged(Lot(res.cast<String, dynamic>()));
    }
  }

  Future<void> _deliver() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t('মাল পৌঁছে দিয়েছেন?', 'Delivered the produce?')),
        content: Text(t('নিশ্চিত করলে ব্যাংক কৃষকের টাকা ছেড়ে দেবে।', 'Confirming tells the bank to release the farmer\'s payment.')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(t('এখনো না', 'Not yet'))),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(t('হ্যাঁ, পৌঁছেছে', 'Yes, delivered'))),
        ],
      ),
    );
    if (ok == true) await _step('deliver', done: t('ডেলিভারি সম্পন্ন, কৃষকের টাকা ছাড়া হয়েছে', 'Delivered: the farmer\'s payment is released'));
  }

  Future<void> _report() async {
    final res = await showModalBottomSheet<Object>(context: context, isScrollControlled: true, builder: (_) => DisputeSheet(lotId: widget.lot.id));
    if (res is Map) widget.onChanged(Lot(res.cast<String, dynamic>()));
  }

  @override
  Widget build(BuildContext context) {
    final lot = widget.lot;
    final d = lot.delivery!;
    final theme = Theme.of(context);
    final stage = jobStage(d.status);
    return RefreshIndicator(
      onRefresh: widget.onRefresh,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 32), children: [
        AppCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Expanded(child: Text('${cropName(lot.crop)} · ${kg(lot.kg)} · ${t('গ্রেড', 'grade')} ${lot.grade}', style: theme.textTheme.titleMedium)),
              Pill(deliveryStatus(d.status), tone: d.status == 'DELIVERED' ? Tone.green : Tone.sky),
            ]),
            const SizedBox(height: 16),
            RouteLine(delivery: d, height: 72),
            const SizedBox(height: 18),
            RouteSteps(steps: [t('অপেক্ষা', 'Waiting'), t('নিয়েছেন', 'Assigned'), t('তোলা', 'Picked up'), t('পৌঁছেছে', 'Delivered')], current: stage, tone: d.atRisk ? Tone.rose : Tone.green),
            const SizedBox(height: 12),
            if (truckLine(d) case final line?) ...[TruckLine(text: line), const SizedBox(height: 6)],
            InfoRow(t('দূরত্ব', 'Distance'), '${num1(d.km, decimals: 1)} ${t('কিমি', 'km')} · ${num1(d.etaHours, decimals: 1)} ${t('ঘণ্টা', 'h')}'),
            InfoRow(t('কৃষক', 'Farmer'), '${lot.farmerName} · ${[lot.upazila, lot.district].where((s) => s.isNotEmpty).join(', ')}'),
            InfoRow(t('ক্রেতা', 'Buyer'), lot.acceptedBid?.buyerName ?? '–'),
            if (d.driverName != null) InfoRow(t('চালক', 'Driver'), d.driverName!),
          ]),
        ),
        if (_mine && (d.status == 'ASSIGNED' || d.status == 'PICKED_UP')) ...[
          const SizedBox(height: 12),
          // Removed with the job's end (delivered), so sharing stops with it.
          LiveLocationSwitch(key: ValueKey(lot.id), lotId: lot.id, onChanged: widget.onChanged),
        ],
        if (_mine && d.status == 'ASSIGNED') ...[
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy ? null : () => _step('pickup', done: t('মাল তোলা হয়েছে, শুভ যাত্রা', 'Picked up; drive safe')),
            icon: const Icon(Icons.inventory_2_rounded),
            label: Text(t('মাল তুলেছি', 'I picked it up')),
          ),
        ],
        if (d.status == 'PICKED_UP' || d.lastTemp != null) ...[
          const SizedBox(height: 16),
          _ShelfLife(delivery: d),
        ],
        if (_mine && d.status == 'PICKED_UP') ...[
          const SizedBox(height: 12),
          AppCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(t('ট্রাকের ভেতরের তাপমাত্রা জানান', 'Log the temperature in the truck'), style: theme.textTheme.titleSmall),
              const SizedBox(height: 8),
              Row(children: [
                SizedBox(width: 92, child: Text('${num1(_temp, decimals: 0)}°C', style: theme.textTheme.titleLarge?.copyWith(fontFeatures: tabular))),
                Expanded(child: Slider(value: _temp, min: -5, max: 55, divisions: 60, label: '${_temp.round()}°C', onChanged: (v) => setState(() => _temp = v))),
              ]),
              Row(children: [
                SizedBox(width: 92, child: Text('${num1(_rh, decimals: 0)}% RH', style: theme.textTheme.titleMedium?.copyWith(fontFeatures: tabular))),
                Expanded(child: Slider(value: _rh, min: 5, max: 100, divisions: 95, label: '${_rh.round()}%', onChanged: (v) => setState(() => _rh = v))),
              ]),
              OutlinedButton.icon(
                onPressed: _busy ? null : () => _step('temperature', done: t('তাপমাত্রা জমা হয়েছে', 'Temperature logged')),
                icon: const Icon(Icons.thermostat_rounded),
                label: Text(t('তাপমাত্রা জমা দিন', 'Log temperature')),
              ),
            ]),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _busy ? null : _deliver,
            icon: const Icon(Icons.where_to_vote_rounded),
            label: Text(t('পৌঁছে দিয়েছি', 'I delivered it')),
          ),
        ],
        if (_mine && lot.escrow != null) ...[
          const SizedBox(height: 12),
          OutlinedButton.icon(onPressed: _report, icon: const Icon(Icons.report_outlined), label: Text(t('সমস্যা জানান', 'Report a problem'))),
        ],
        if (lot.disputes.isNotEmpty) ...[
          SectionTitle(t('অভিযোগ', 'Reported problems')),
          for (final x in lot.disputes) ...[DisputeTile(dispute: x), const SizedBox(height: 8)],
        ],
        if (d.events.isNotEmpty) ...[
          SectionTitle(t('যা যা হয়েছে', 'What happened')),
          AppCard(
            child: Column(children: [
              for (final e in d.events.reversed)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    SizedBox(width: 52, child: Text(clock(e.at), style: theme.textTheme.labelMedium?.copyWith(fontFeatures: tabular))),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(e.kind.replaceAll('_', ' ').toLowerCase(), style: theme.textTheme.titleSmall),
                        if (e.detail.isNotEmpty) Text(e.detail, style: theme.textTheme.bodySmall),
                      ]),
                    ),
                  ]),
                ),
            ]),
          ),
        ],
      ]),
    );
  }
}

/// The driver's opt-in: while on, the truck's position goes to the node (a 50 m move at most every 15 s), which shows the
/// buyer and the farmer of this sale a coarse position (rounded to about 1 km) and the time left. Off by default; it
/// stops when switched off, on delivery (the job leaves this screen) and when the driver leaves the screen.
class LiveLocationSwitch extends StatefulWidget {
  const LiveLocationSwitch({super.key, required this.lotId, required this.onChanged});
  final String lotId;
  final void Function(Lot lot) onChanged;

  @override
  State<LiveLocationSwitch> createState() => _LiveLocationSwitchState();
}

class _LiveLocationSwitchState extends State<LiveLocationSwitch> with AutomaticKeepAliveClientMixin {
  StreamSubscription<Position>? _positions;
  Position? _next;
  DateTime _sentAt = DateTime(0);
  Timer? _later;
  String? _sent; // when the node last took a position
  bool _asking = false;

  bool get _on => _positions != null;

  // The job's list builds lazily: while sharing, scrolling down to log a temperature must not end it.
  @override
  bool get wantKeepAlive => _on;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Another tab or a screen on top of this one: the driver has left it.
    if (!TickerMode.valuesOf(context).enabled) _stop();
  }

  @override
  void dispose() {
    _stop();
    super.dispose();
  }

  void _stop() {
    _positions?.cancel();
    _positions = null;
    _later?.cancel();
    _later = null;
    _next = null;
  }

  void _off() {
    setState(_stop);
    updateKeepAlive();
  }

  Future<void> _toggle(bool on) async {
    if (!on) return _off();
    setState(() => _asking = true);
    final allowed = await _allowed();
    if (!mounted) return;
    setState(() {
      _asking = false;
      if (!allowed || !TickerMode.valuesOf(context).enabled) return;
      _sent = null;
      _positions = Geolocator.getPositionStream(
        // Android: the phone's own GPS (LocationManager), not Google's fused provider, so declining Google's
        // "Location Accuracy" prompt does not stop sharing and phones without Play services still work.
        locationSettings: !kIsWeb && defaultTargetPlatform == TargetPlatform.android
            ? AndroidSettings(accuracy: LocationAccuracy.high, distanceFilter: 50, forceLocationManager: true)
            : const LocationSettings(accuracy: LocationAccuracy.high, distanceFilter: 50),
      ).listen(_onPosition, onError: (Object _) {
        if (!mounted) return;
        _off();
        _explain(t('লোকেশন পাওয়া যাচ্ছে না, শেয়ার বন্ধ হলো।', 'The location stopped coming; sharing is off.'));
      });
    });
    updateKeepAlive();
  }

  /// Location on and permitted: asks once; a refusal for good points to the phone's settings.
  Future<bool> _allowed() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        _explain(t('ফোনের লোকেশন (GPS) বন্ধ। চালু করে আবার চেষ্টা করুন।', 'Location (GPS) is off on this phone. Turn it on and try again.'),
            settings: Geolocator.openLocationSettings);
        return false;
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.deniedForever) {
        _explain(
            t('লোকেশনের অনুমতি বন্ধ করা আছে। ফোনের সেটিংসে KrishiNexus-কে লোকেশনের অনুমতি দিন।',
                'Location permission is turned off. Allow it for KrishiNexus in the phone settings.'),
            settings: Geolocator.openAppSettings);
        return false;
      }
      if (permission == LocationPermission.denied) {
        _explain(t('অনুমতি ছাড়া ট্রাকের অবস্থান জানানো যায় না।', 'Without location permission the truck\'s position cannot be shared.'));
        return false;
      }
      return true;
    } catch (_) {
      _explain(t('এই ফোনে লোকেশন পড়া গেল না।', 'This phone\'s location could not be read.'));
      return false;
    }
  }

  void _explain(String message, {Future<bool> Function()? settings}) {
    if (!mounted) return;
    snack(context, message,
        icon: Icons.location_off_rounded,
        tone: Tone.amber,
        action: settings == null || kIsWeb ? null : SnackBarAction(label: t('সেটিংস', 'Settings'), onPressed: () => settings()));
  }

  // At most one position every 15 s: a newer one waits for the slot (the node keeps one per 10 s).
  void _onPosition(Position p) {
    _next = p;
    final wait = const Duration(seconds: 15) - DateTime.now().difference(_sentAt);
    if (wait <= Duration.zero) {
      _send();
    } else {
      _later ??= Timer(wait, _send);
    }
  }

  Future<void> _send() async {
    _later = null;
    final p = _next;
    if (p == null || !_on) return;
    _next = null;
    _sentAt = DateTime.now();
    try {
      final res = await Api.post('/market/deliveries/${widget.lotId}/location', {
        'lat': p.latitude,
        'lng': p.longitude,
        'accuracy_m': p.accuracy,
        if (p.speed > 0) 'speed_kmh': p.speed * 3.6,
      }, const Duration(seconds: 20));
      if (!mounted) return;
      setState(() => _sent = DateTime.now().toIso8601String());
      if (res is Map && res['lot_id'] is String) widget.onChanged(Lot(res.cast<String, dynamic>()));
    } on ApiError catch (e) {
      // No signal or a busy node: the next position tries again. A refusal (delivered, not this driver's job) ends it.
      if (!mounted || e.unreachable || e.status == 429 || e.status >= 500) return;
      _off();
      _explain(friendlyError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final theme = Theme.of(context);
    return AppCard(
      tone: _on ? Tone.sky : null,
      padding: const EdgeInsets.fromLTRB(0, 6, 0, 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SwitchListTile(
          value: _on,
          onChanged: _asking ? null : _toggle,
          secondary: Icon(_on ? Icons.share_location_rounded : Icons.location_off_outlined),
          title: Text(t('লাইভ লোকেশন জানান', 'Share live location')),
          subtitle: Text(t(
            'চালু করলে এই বিক্রির ক্রেতা ও কৃষক (এবং ব্যাংক, বিচারক ও অ্যাডমিন ডেস্ক) ট্রাকের আনুমানিক অবস্থান (প্রায় ১ কিমি) আর পৌঁছানোর সময় দেখবেন; অন্য কেউ পান না। বন্ধ করলে, পৌঁছে দিলে বা এই স্ক্রিন ছাড়লে থেমে যায়।',
            'While on, the buyer and the farmer of this sale (and the bank, judge and admin desks) see the truck\'s rough position (to about 1 km) and the time left; nobody else gets it. It stops when you switch it off, deliver, or leave this screen.',
          )),
        ),
        if (_on)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              _sent == null ? t('প্রথম অবস্থান খোঁজা হচ্ছে…', 'Finding the first position…') : t('শেষ পাঠানো: ${ago(_sent!)}', 'Last sent ${ago(_sent!)}'),
              style: theme.textTheme.bodySmall?.copyWith(color: Tone.sky.fg(context)),
            ),
          ),
      ]),
    );
  }
}

/// Hours the produce will keep at the logged temperature against the hours left to drive.
class _ShelfLife extends StatelessWidget {
  const _ShelfLife({required this.delivery});
  final Delivery delivery;

  @override
  Widget build(BuildContext context) {
    final d = delivery;
    final theme = Theme.of(context);
    final life = d.shelfLifeHours;
    final tone = d.atRisk ? Tone.rose : Tone.green;
    return AppCard(
      tone: tone,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(d.atRisk ? Icons.warning_rounded : Icons.eco_rounded, color: tone.fg(context)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              life == null
                  ? t('তাপমাত্রা জানালে টেকসই সময় হিসাব হবে', 'Log a temperature to check the shelf life')
                  : d.atRisk
                      ? t('ঝুঁকি: পৌঁছানোর আগে মান নষ্ট হতে পারে', 'At risk: quality may not last the drive')
                      : t('পৌঁছানো পর্যন্ত মান ঠিক থাকবে', 'Quality will last the drive'),
              style: theme.textTheme.titleSmall,
            ),
          ),
        ]),
        if (life != null) ...[
          const SizedBox(height: 8),
          MeterRow(
            label: t('টেকসই সময় বনাম পথের সময়', 'Shelf life vs. drive time'),
            value: d.etaHours,
            max: life <= 0 ? 1 : life,
            display: '${num1(d.etaHours, decimals: 1)} / ${num1(life, decimals: 0)} ${t('ঘণ্টা', 'h')}',
            tone: tone,
          ),
          Text(
            t('শেষ তাপমাত্রা ${num1(d.lastTemp ?? 0, decimals: 1)}°C, আর্দ্রতা ${pct(d.lastRh, decimals: 0)}', 'Last logged ${(d.lastTemp ?? 0).toStringAsFixed(1)}°C at ${pct(d.lastRh, decimals: 0)} RH'),
            style: theme.textTheme.bodySmall,
          ),
        ],
      ]),
    );
  }
}
