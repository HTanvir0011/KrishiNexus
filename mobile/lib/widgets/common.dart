import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/live.dart';
import '../core/state.dart';
import '../core/theme.dart';

/// The KrishiNexus mark from the website's favicon: a tall flag-green field beside mustard and monsoon plots.
class LogoMark extends StatelessWidget {
  const LogoMark({super.key, this.size = 40});
  final double size;

  @override
  Widget build(BuildContext context) {
    final u = size / 24;
    Widget block(double w, double h, Color c) =>
        Container(width: w * u, height: h * u, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(1.5 * u)));
    return SizedBox.square(
      dimension: size,
      child: Padding(
        padding: EdgeInsets.all(3 * u),
        child: Row(children: [
          block(8, 18, Brand.flag),
          SizedBox(width: 2 * u),
          Column(children: [block(8, 8, Brand.mustard), SizedBox(height: 2 * u), block(8, 8, Brand.monsoon)]),
        ]),
      ),
    );
  }
}

/// A short status label in one tone.
class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.tone = Tone.slate, this.icon});
  final String text;
  final Tone tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final fg = tone.fg(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: tone.bg(context), borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 14, color: fg), const SizedBox(width: 4)],
        Flexible(
          child: Text(text,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(color: fg, fontWeight: FontWeight.w600)),
        ),
      ]),
    );
  }
}

/// A card surface; tappable when [onTap] is given (scales a touch on press).
class AppCard extends StatelessWidget {
  const AppCard({super.key, required this.child, this.onTap, this.padding = const EdgeInsets.all(16), this.tone, this.strong = false});
  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;
  final Tone? tone;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final border = tone == null ? scheme.outlineVariant : tone!.fg(context).withValues(alpha: strong ? 0.55 : 0.22);
    final card = Material(
      color: tone == null ? scheme.surfaceContainerLowest : tone!.bg(context),
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16), side: BorderSide(color: border, width: strong ? 1.6 : 1)),
      clipBehavior: Clip.antiAlias,
      child: onTap == null ? Padding(padding: padding, child: child) : InkWell(onTap: onTap, child: Padding(padding: padding, child: child)),
    );
    return onTap == null ? card : Pressable(child: card);
  }
}

/// Acknowledges a press by settling to 97% (instant when animations are off).
class Pressable extends StatefulWidget {
  const Pressable({super.key, required this.child});
  final Widget child;

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  bool _down = false;

  @override
  Widget build(BuildContext context) => Listener(
        onPointerDown: (_) => setState(() => _down = true),
        onPointerUp: (_) => setState(() => _down = false),
        onPointerCancel: (_) => setState(() => _down = false),
        child: AnimatedScale(
          scale: _down ? 0.97 : 1,
          duration: Motion.of(context, const Duration(milliseconds: 140)),
          curve: Motion.expo,
          child: widget.child,
        ),
      );
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing, this.top = 24});
  final String text;
  final Widget? trailing;
  final double top;

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.only(top: top, bottom: 10),
        child: Row(children: [
          Expanded(child: Text(text, style: Theme.of(context).textTheme.titleMedium)),
          ?trailing,
        ]),
      );
}

/// A centred message for an empty list, with an optional action.
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, this.body, this.action});
  final IconData icon;
  final String title;
  final String? body;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 48),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(color: theme.colorScheme.primaryContainer, shape: BoxShape.circle),
          child: Icon(icon, size: 34, color: theme.colorScheme.onPrimaryContainer),
        ),
        const SizedBox(height: 16),
        Text(title, textAlign: TextAlign.center, style: theme.textTheme.titleMedium),
        if (body != null) ...[
          const SizedBox(height: 6),
          Text(body!, textAlign: TextAlign.center, style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
        ],
        if (action != null) ...[const SizedBox(height: 20), action!],
      ]),
    );
  }
}

class ErrorState extends StatelessWidget {
  const ErrorState({super.key, required this.error, required this.onRetry});
  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => EmptyState(
        icon: error is ApiError && (error as ApiError).unreachable ? Icons.wifi_off_rounded : Icons.error_outline_rounded,
        title: friendlyError(error),
        action: FilledButton.tonalIcon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: Text(t('আবার চেষ্টা', 'Try again'))),
      );
}

/// What went wrong, in the app's language; the node's own explanation when it gave one.
String friendlyError(Object error) {
  if (error is ApiError) {
    if (error.unreachable) {
      return t('সার্ভারে পৌঁছানো যাচ্ছে না। ইন্টারনেট দেখে আবার চেষ্টা করুন।',
          'Cannot reach the KrishiNexus server. Check the internet and try again.');
    }
    if (error.status == 401) return t('সেশন শেষ হয়েছে, আবার লগইন করুন।', 'Your session ended; please log in again.');
    if (error.status == 429) return t('অনেক অনুরোধ হয়েছে, এক মিনিট পরে চেষ্টা করুন।', 'Too many requests; try again in a minute.');
    return error.message;
  }
  return '$error';
}

void snack(BuildContext context, String message, {Tone tone = Tone.slate, IconData? icon, SnackBarAction? action}) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      action: action,
      content: Row(children: [
        if (icon != null) ...[Icon(icon, color: Theme.of(context).colorScheme.onInverseSurface, size: 20), const SizedBox(width: 10)],
        Expanded(child: Text(message)),
      ]),
    ));
  if (tone == Tone.rose) HapticFeedback.heavyImpact();
}

/// Opens [url] in the browser or the app that handles it (mail, a social app).
Future<void> openLink(BuildContext context, String url) async {
  final uri = Uri.tryParse(url);
  final ok = uri != null && await launchUrl(uri, mode: LaunchMode.externalApplication).catchError((_) => false);
  if (!ok && context.mounted) snack(context, t('ব্রাউজার খোলা গেল না।', 'Could not open the browser.'), tone: Tone.rose);
}

/// A page of the KrishiNexus website, served by the node the app talks to.
Future<void> openWeb(BuildContext context, String path) => openLink(context, '${Api.base}$path');

/// The live feed's state for the app bar: a green dot and "Live" while market events stream in, a quiet grey dot
/// while it reconnects (screens then keep polling on their own).
class LiveDot extends StatelessWidget {
  const LiveDot({super.key});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: live,
        builder: (context, _) {
          final on = live.connected;
          final color = on ? Tone.green.fg(context) : Theme.of(context).colorScheme.outline;
          return Semantics(
            label: on ? t('লাইভ: বাজারের খবর সাথে সাথে আসছে', 'Live: market updates arrive as they happen') : t('লাইভ সংযোগ আবার চেষ্টা হচ্ছে', 'Reconnecting to live updates'),
            child: ExcludeSemantics(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  AnimatedContainer(
                    duration: Motion.of(context, Motion.medium),
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                  ),
                  if (on) ...[
                    const SizedBox(width: 6),
                    Text(t('লাইভ', 'Live'), style: Theme.of(context).textTheme.labelMedium?.copyWith(color: color, fontWeight: FontWeight.w600)),
                  ],
                ]),
              ),
            ),
          );
        },
      );
}

/// Stages of a sale or a delivery, filled up to [current] (index), drawing on when it advances.
class RouteSteps extends StatelessWidget {
  const RouteSteps({super.key, required this.steps, required this.current, this.tone = Tone.green});
  final List<String> steps;
  final int current;
  final Tone tone;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final fg = tone.fg(context);
    final text = Theme.of(context).textTheme.labelMedium;
    return Column(children: [
      LayoutBuilder(builder: (context, box) {
        final n = steps.length;
        final fill = n < 2 ? 1.0 : (current.clamp(0, n - 1) / (n - 1));
        return SizedBox(
          height: 22,
          child: Stack(alignment: Alignment.centerLeft, children: [
            Positioned(left: 11, right: 11, child: Container(height: 3, color: scheme.outlineVariant)),
            Positioned(
              left: 11,
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: fill),
                duration: Motion.of(context, Motion.long),
                curve: Motion.expo,
                builder: (_, v, _) => Container(height: 3, width: (box.maxWidth - 22) * v, color: fg),
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                for (var i = 0; i < n; i++)
                  AnimatedContainer(
                    duration: Motion.of(context, Motion.medium),
                    width: 22,
                    height: 22,
                    decoration: BoxDecoration(
                      color: i <= current ? fg : scheme.surfaceContainerLowest,
                      shape: BoxShape.circle,
                      border: Border.all(color: i <= current ? fg : scheme.outline, width: 2),
                    ),
                    child: i < current
                        ? Icon(Icons.check_rounded, size: 14, color: scheme.surface)
                        : i == current
                            ? Center(child: Container(width: 7, height: 7, decoration: BoxDecoration(color: scheme.surface, shape: BoxShape.circle)))
                            : null,
                  ),
              ],
            ),
          ]),
        );
      }),
      const SizedBox(height: 6),
      Row(children: [
        for (var i = 0; i < steps.length; i++)
          Expanded(
            child: Text(steps[i],
                textAlign: i == 0 ? TextAlign.left : i == steps.length - 1 ? TextAlign.right : TextAlign.center,
                maxLines: 2,
                style: text?.copyWith(
                    color: i <= current ? scheme.onSurface : scheme.onSurfaceVariant,
                    fontWeight: i == current ? FontWeight.w700 : FontWeight.w500)),
          ),
      ]),
    ]);
  }
}

/// A labelled bar from 0 to [max].
class MeterRow extends StatelessWidget {
  const MeterRow({super.key, required this.label, required this.value, required this.display, this.max = 100, this.tone = Tone.green});
  final String label;
  final double value;
  final double max;
  final String display;
  final Tone tone;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(label, style: theme.textTheme.bodyMedium)),
          Text(display, style: theme.textTheme.titleSmall?.copyWith(fontFeatures: tabular)),
        ]),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: (value / max).clamp(0, 1)),
            duration: Motion.of(context, Motion.long),
            curve: Motion.expo,
            builder: (_, v, _) => LinearProgressIndicator(
                value: v, minHeight: 8, color: tone.fg(context), backgroundColor: theme.colorScheme.surfaceContainerHigh),
          ),
        ),
      ]),
    );
  }
}

/// A number that counts up to its value once (lands at once when animations are off).
class CountUp extends StatelessWidget {
  const CountUp({super.key, required this.value, required this.format, this.style});
  final double value;
  final String Function(double) format;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: value),
        duration: Motion.of(context, const Duration(milliseconds: 900)),
        curve: Motion.expo,
        builder: (_, v, _) => Text(format(v), style: style?.copyWith(fontFeatures: tabular)),
      );
}

/// Grey placeholders that breathe while a list loads.
class SkeletonList extends StatefulWidget {
  const SkeletonList({super.key, this.count = 4, this.height = 96});
  final int count;
  final double height;

  @override
  State<SkeletonList> createState() => _SkeletonListState();
}

class _SkeletonListState extends State<SkeletonList> with SingleTickerProviderStateMixin {
  late final _pulse = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat(reverse: true);

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final base = Theme.of(context).colorScheme.surfaceContainerHigh;
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      physics: const NeverScrollableScrollPhysics(),
      itemCount: widget.count,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (_, _) => FadeTransition(
        opacity: Motion.reduced(context) ? const AlwaysStoppedAnimation(0.7) : Tween(begin: 0.45, end: 1.0).animate(_pulse),
        child: Container(height: widget.height, decoration: BoxDecoration(color: base, borderRadius: BorderRadius.circular(16))),
      ),
    );
  }
}

/// A key-value row for receipts and certificates.
class InfoRow extends StatelessWidget {
  const InfoRow(this.label, this.value, {super.key, this.mono = false, this.strong = false});
  final String label;
  final String value;
  final bool mono;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 120, child: Text(label, style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant))),
        Expanded(
          child: Text(value,
              style: (strong ? theme.textTheme.titleSmall : theme.textTheme.bodyMedium)
                  ?.copyWith(fontFeatures: tabular, fontFamily: mono ? 'monospace' : null, fontSize: mono ? 13 : null)),
        ),
      ]),
    );
  }
}

/// Runs [action] with a spinner on the button and shows the error as a snackbar.
Future<T?> guarded<T>(BuildContext context, Future<T> Function() action, {String? done}) async {
  try {
    final result = await action();
    if (done != null && context.mounted) snack(context, done, icon: Icons.check_circle_rounded, tone: Tone.green);
    return result;
  } catch (e) {
    if (context.mounted) snack(context, friendlyError(e), icon: Icons.error_outline_rounded, tone: Tone.rose);
    return null;
  }
}

/// Header strip shown when the app runs in Offline edge mode.
class OfflineBanner extends StatelessWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: app,
        builder: (context, _) => AnimatedSize(
          duration: Motion.of(context, Motion.medium),
          curve: Motion.expo,
          child: !app.offline
              ? const SizedBox(width: double.infinity)
              : Container(
                  width: double.infinity,
                  color: Tone.amber.bg(context),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(children: [
                    Icon(Icons.cloud_off_rounded, size: 18, color: Tone.amber.fg(context)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        t('অফলাইন এজ মোড: উত্তর গ্রামের কিয়স্কের নিজস্ব মডেল থেকে, অনলাইন কণ্ঠ বন্ধ।',
                            'Offline edge mode: answers come from the kiosk\'s own model; the online voice is off.'),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Tone.amber.fg(context)),
                      ),
                    ),
                  ]),
                ),
        ),
      );
}

String plural(int n, String bnUnit, String enOne, String enMany) => t('${digits(n)} $bnUnit', '$n ${n == 1 ? enOne : enMany}');
