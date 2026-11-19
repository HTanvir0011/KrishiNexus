import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import 'common.dart';

Tone gradeTone(String letter) => switch (letter) { 'A' => Tone.green, 'B' => Tone.amber, _ => Tone.rose };

Tone labelTone(String label) => switch (label) {
      'uniform_A' => Tone.green,
      'minor_bruise' => Tone.amber,
      'fungal_blight' => Tone.rose,
      _ => Tone.sky,
    };

String labelName(String label) => switch (label) {
      'uniform_A' => t('ভালো, সমান', 'Sound, even'),
      'minor_bruise' => t('হালকা দাগ', 'Minor bruise'),
      'fungal_blight' => t('পচন / ধসা', 'Rot or blight'),
      _ => t('ছোট আকার', 'Undersized'),
    };

/// The photo (or, for a sample lot, a drawn sorting tray) with each detected piece outlined. Pieces appear one
/// after another once a grade arrives; tap one to read its size and defect.
class GradeCanvas extends StatefulWidget {
  const GradeCanvas({super.key, required this.result, this.photo, this.radius = 20});
  final GradeResult result;
  final Uint8List? photo;
  final double radius;

  @override
  State<GradeCanvas> createState() => _GradeCanvasState();
}

class _GradeCanvasState extends State<GradeCanvas> with SingleTickerProviderStateMixin {
  late final _reveal = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400));
  Box? _picked;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (Motion.reduced(context)) {
      _reveal.value = 1;
    } else if (!_reveal.isAnimating && _reveal.value == 0) {
      _reveal.forward();
    }
  }

  @override
  void dispose() {
    _reveal.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.result;
    final boxes = r.boxes;
    final aspect = r.frameW > 0 && r.frameH > 0 ? r.frameW / r.frameH : 4 / 3;
    return ClipRRect(
      borderRadius: BorderRadius.circular(widget.radius),
      child: AspectRatio(
        aspectRatio: aspect,
        child: LayoutBuilder(builder: (context, box) {
          final scale = r.frameW > 0 ? box.maxWidth / r.frameW : 1.0;
          return GestureDetector(
            onTapUp: (d) {
              final p = d.localPosition / scale;
              final hit = boxes.where((b) {
                final q = b.rect;
                return p.dx >= q[0] && p.dx <= q[0] + q[2] && p.dy >= q[1] && p.dy <= q[1] + q[3];
              }).firstOrNull;
              HapticFeedback.selectionClick();
              setState(() => _picked = hit);
            },
            child: Stack(fit: StackFit.expand, children: [
              if (widget.photo != null)
                Image.memory(widget.photo!, fit: BoxFit.fill, gaplessPlayback: true)
              else
                CustomPaint(painter: _TrayPainter(crop: r.crop, boxes: boxes, scale: scale)),
              AnimatedBuilder(
                animation: _reveal,
                builder: (context, _) => CustomPaint(
                  painter: _BoxesPainter(
                    boxes: boxes,
                    scale: scale,
                    progress: _reveal.value,
                    picked: _picked,
                    colors: {for (final l in ['uniform_A', 'minor_bruise', 'fungal_blight', 'undersized']) l: labelTone(l).fg(context)},
                    darkPhoto: widget.photo != null,
                  ),
                ),
              ),
              if (_picked != null)
                Positioned(
                  left: 10,
                  right: 10,
                  bottom: 10,
                  child: _PickedCard(box: _picked!, onClose: () => setState(() => _picked = null)),
                ),
            ]),
          );
        }),
      ),
    );
  }
}

class _PickedCard extends StatelessWidget {
  const _PickedCard({required this.box, required this.onClose});
  final Box box;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final tone = labelTone(box.label);
    return Material(
      color: theme.colorScheme.surfaceContainerLowest.withValues(alpha: 0.96),
      borderRadius: BorderRadius.circular(14),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 8, 4, 8),
        child: Row(children: [
          Container(width: 12, height: 12, decoration: BoxDecoration(color: tone.fg(context), shape: BoxShape.circle)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '${labelName(box.label)} · ${digits(box.diameterMm.toStringAsFixed(0))} ${t('মিমি', 'mm')} · '
              '${t('দাগ', 'defect')} ${pct(box.defectPct)} · ${t('নিশ্চয়তা', 'confidence')} ${pct(box.confidence * 100, decimals: 0)}',
              style: theme.textTheme.bodySmall?.copyWith(fontFeatures: tabular),
            ),
          ),
          IconButton(onPressed: onClose, icon: const Icon(Icons.close_rounded, size: 20), tooltip: t('বন্ধ', 'Close')),
        ]),
      ),
    );
  }
}

class _BoxesPainter extends CustomPainter {
  _BoxesPainter({required this.boxes, required this.scale, required this.progress, required this.picked, required this.colors, required this.darkPhoto});
  final List<Box> boxes;
  final double scale;
  final double progress;
  final Box? picked;
  final Map<String, Color> colors;
  final bool darkPhoto;

  @override
  void paint(Canvas canvas, Size size) {
    final n = boxes.length;
    for (var i = 0; i < n; i++) {
      // Each piece fades and settles in over its own slice of the reveal.
      final start = n <= 1 ? 0.0 : (i / n) * 0.7;
      final p = ((progress - start) / 0.3).clamp(0.0, 1.0);
      if (p <= 0) continue;
      final b = boxes[i];
      final q = b.rect;
      final grow = 1.25 - 0.25 * Curves.easeOutCubic.transform(p);
      final center = Offset((q[0] + q[2] / 2) * scale, (q[1] + q[3] / 2) * scale);
      final rect = Rect.fromCenter(center: center, width: q[2] * scale * grow, height: q[3] * scale * grow);
      final color = colors[b.label] ?? Colors.white;
      final selected = picked != null && picked!.j['object_id'] == b.j['object_id'];
      final rr = RRect.fromRectAndRadius(rect, Radius.circular(math.min(rect.shortestSide * 0.2, 10)));
      if (darkPhoto) {
        canvas.drawRRect(rr, Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = selected ? 6 : 4
          ..color = Colors.black.withValues(alpha: 0.35 * p));
      }
      canvas.drawRRect(rr, Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = selected ? 3.5 : 2
        ..color = color.withValues(alpha: p));
      if (selected) canvas.drawRRect(rr, Paint()..color = color.withValues(alpha: 0.18));
    }
  }

  @override
  bool shouldRepaint(_BoxesPainter old) =>
      old.progress != progress || old.picked?.j['object_id'] != picked?.j['object_id'] || old.scale != scale;
}

/// A sample lot has no photo: draw the sorting tray the sweep graded, piece by piece, with its blemishes.
class _TrayPainter extends CustomPainter {
  _TrayPainter({required this.crop, required this.boxes, required this.scale});
  final String crop;
  final List<Box> boxes;
  final double scale;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..shader = const LinearGradient(
      begin: Alignment.topCenter, end: Alignment.bottomCenter,
      colors: [Color(0xFF1E2B24), Color(0xFF131C17)],
    ).createShader(rect));
    final grid = Paint()..color = Colors.white.withValues(alpha: 0.04)..strokeWidth = 1;
    for (var x = 0.0; x < size.width; x += 24) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
    }
    for (var y = 0.0; y < size.height; y += 24) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }
    final (skin, shade) = switch (crop) {
      'Green Chili' => (const Color(0xFF4C9A3A), const Color(0xFF2E6B24)),
      'Brinjal' => (const Color(0xFF5B3270), const Color(0xFF3A1D4B)),
      'Diamant Potato' => (const Color(0xFFD9B77E), const Color(0xFFB08D55)),
      _ => (const Color(0xFFC7895E), const Color(0xFF9A6142)), // Cardinal: red-skinned
    };
    final long = crop == 'Green Chili' || crop == 'Brinjal';
    for (final b in boxes) {
      final q = b.rect;
      final r = Rect.fromLTWH(q[0] * scale, q[1] * scale, q[2] * scale, q[3] * scale).deflate(math.min(q[2], q[3]) * scale * 0.08);
      final piece = long ? RRect.fromRectAndRadius(r, Radius.circular(r.shortestSide / 2)) : RRect.fromRectAndRadius(r, Radius.elliptical(r.width / 2, r.height / 2));
      canvas.drawRRect(piece.shift(const Offset(0, 3)), Paint()..color = Colors.black.withValues(alpha: 0.35));
      canvas.drawRRect(piece, Paint()..shader = RadialGradient(
        center: const Alignment(-0.35, -0.4), radius: 0.9, colors: [Color.lerp(skin, Colors.white, 0.18)!, skin, shade],
        stops: const [0, 0.6, 1],
      ).createShader(r));
      final rnd = math.Random(b.j['object_id'] as int? ?? 0);
      if (b.label == 'minor_bruise' || b.label == 'fungal_blight') {
        final blight = b.label == 'fungal_blight';
        final spots = blight ? 3 : 2;
        for (var s = 0; s < spots; s++) {
          final c = Offset(r.left + r.width * (0.25 + rnd.nextDouble() * 0.5), r.top + r.height * (0.25 + rnd.nextDouble() * 0.5));
          canvas.drawCircle(c, r.shortestSide * (blight ? 0.16 : 0.11) * (0.7 + rnd.nextDouble() * 0.6),
              Paint()..color = (blight ? const Color(0xFF2F3A2A) : const Color(0xFF6B4226)).withValues(alpha: 0.75));
        }
      }
    }
  }

  @override
  bool shouldRepaint(_TrayPainter old) => old.scale != scale || old.boxes != boxes;
}

/// The light that sweeps a photo while the node grades it.
class ScanSweep extends StatefulWidget {
  const ScanSweep({super.key, this.color = const Color(0xFF6EE7B7)});
  final Color color;

  @override
  State<ScanSweep> createState() => _ScanSweepState();
}

class _ScanSweepState extends State<ScanSweep> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!Motion.reduced(context) && !_c.isAnimating) _c.repeat(reverse: true);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (Motion.reduced(context)) return ColoredBox(color: widget.color.withValues(alpha: 0.08));
    return AnimatedBuilder(
      animation: _c,
      builder: (context, _) => CustomPaint(painter: _SweepPainter(Curves.easeInOut.transform(_c.value), widget.color)),
    );
  }
}

class _SweepPainter extends CustomPainter {
  _SweepPainter(this.p, this.color);
  final double p;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final y = size.height * p;
    final band = Rect.fromLTWH(0, y - 70, size.width, 70);
    canvas.drawRect(band, Paint()..shader = LinearGradient(
      begin: Alignment.topCenter, end: Alignment.bottomCenter,
      colors: [color.withValues(alpha: 0), color.withValues(alpha: 0.28)],
    ).createShader(band));
    canvas.drawRect(Rect.fromLTWH(0, y - 1.5, size.width, 3), Paint()..color = color);
    // corner brackets of the inspection frame
    final b = Paint()..color = color..strokeWidth = 3..style = PaintingStyle.stroke..strokeCap = StrokeCap.round;
    const m = 18.0, l = 34.0;
    for (final (x, y2, dx, dy) in [(m, m, 1.0, 1.0), (size.width - m, m, -1.0, 1.0), (m, size.height - m, 1.0, -1.0), (size.width - m, size.height - m, -1.0, -1.0)]) {
      canvas.drawLine(Offset(x, y2), Offset(x + l * dx, y2), b);
      canvas.drawLine(Offset(x, y2), Offset(x, y2 + l * dy), b);
    }
  }

  @override
  bool shouldRepaint(_SweepPainter old) => old.p != p;
}

/// The grade letter, set down like an inspector's stamp (once; at once when animations are off).
class GradeStamp extends StatelessWidget {
  const GradeStamp({super.key, required this.letter, this.size = 96});
  final String letter;
  final double size;

  @override
  Widget build(BuildContext context) {
    final tone = gradeTone(letter);
    final fg = tone.fg(context);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Motion.of(context, const Duration(milliseconds: 560)),
      curve: Motion.expo,
      builder: (context, p, child) => Opacity(
        opacity: p.clamp(0, 1),
        child: Transform.rotate(angle: (1 - p) * -0.22, child: Transform.scale(scale: 1.45 - 0.45 * p, child: child)),
      ),
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: tone.bg(context),
          border: Border.all(color: fg, width: 3.5),
        ),
        child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(letter, style: TextStyle(fontSize: size * 0.46, height: 1, fontWeight: FontWeight.w800, color: fg)),
            Text(t('গ্রেড', 'GRADE'), style: TextStyle(fontSize: size * 0.11, letterSpacing: 1.2, fontWeight: FontWeight.w700, color: fg)),
          ]),
        ),
      ),
    );
  }
}

/// How many pieces fell in each class.
class GradeLegend extends StatelessWidget {
  const GradeLegend({super.key, required this.result});
  final GradeResult result;

  @override
  Widget build(BuildContext context) {
    final counts = <String, int>{};
    for (final b in result.boxes) {
      counts[b.label] = (counts[b.label] ?? 0) + 1;
    }
    return Wrap(spacing: 8, runSpacing: 8, children: [
      for (final label in ['uniform_A', 'minor_bruise', 'fungal_blight', 'undersized'])
        if ((counts[label] ?? 0) > 0) Pill('${labelName(label)} · ${digits(counts[label]!)}', tone: labelTone(label)),
    ]);
  }
}

class GradeMetrics extends StatelessWidget {
  const GradeMetrics({super.key, required this.result});
  final GradeResult result;

  @override
  Widget build(BuildContext context) {
    final m = result.metrics;
    double v(String k) => numOf(m[k]);
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(t('মাপজোখ', 'Measurements'), style: Theme.of(context).textTheme.titleMedium)),
          Text('${digits(v('sample_count').toInt())} ${t('টি', 'pieces')} · ${t('গড়', 'avg')} ${digits(v('avg_diameter_mm').toStringAsFixed(0))} ${t('মিমি', 'mm')}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFeatures: tabular)),
        ]),
        const SizedBox(height: 8),
        MeterRow(label: t('আকারে সমতা', 'Size uniformity'), value: v('size_uniformity_pct'), display: pct(v('size_uniformity_pct')), tone: Tone.green),
        MeterRow(label: t('দাগ / থেঁতলানো', 'Bruising'), value: v('mechanical_bruising_pct'), display: pct(v('mechanical_bruising_pct')), max: 20, tone: Tone.amber),
        MeterRow(label: t('পচন ঝুঁকি', 'Rot and blight risk'), value: v('rot_blight_risk_pct'), display: pct(v('rot_blight_risk_pct')), max: 20, tone: Tone.rose),
        MeterRow(label: t('ছোট আকার', 'Undersized'), value: v('undersized_pct'), display: pct(v('undersized_pct')), tone: Tone.sky),
        MeterRow(label: t('আর্দ্রতা (আনুমানিক)', 'Moisture (estimated)'), value: v('estimated_moisture_pct'), display: pct(v('estimated_moisture_pct')), tone: Tone.slate),
      ]),
    );
  }
}

/// The signed certificate, with an on-the-spot check against the node (POST /edge/verify-certificate).
class CertificateCard extends StatefulWidget {
  const CertificateCard({super.key, required this.result});
  final GradeResult result;

  @override
  State<CertificateCard> createState() => _CertificateCardState();
}

class _CertificateCardState extends State<CertificateCard> {
  Map<String, dynamic>? _check;
  bool _busy = false;

  Future<void> _verify() async {
    setState(() => _busy = true);
    final res = await guarded(context, () => Api.post('/edge/verify-certificate', {'cert_id': widget.result.certId}));
    if (mounted) {
      setState(() {
        _busy = false;
        if (res is Map) _check = res.cast<String, dynamic>();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.result;
    final theme = Theme.of(context);
    final ok = _check != null && _check!['signature_valid'] == true && _check!['payload_hash_valid'] == true && _check!['tampered'] != true;
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.verified_rounded, color: Tone.green.fg(context)),
          const SizedBox(width: 8),
          Expanded(child: Text(t('ডিজিটাল মান সনদ', 'Digital quality certificate'), style: theme.textTheme.titleMedium)),
        ]),
        const SizedBox(height: 8),
        InkWell(
          onTap: () {
            Clipboard.setData(ClipboardData(text: r.certId));
            snack(context, t('সনদ নম্বর কপি হয়েছে', 'Certificate number copied'), icon: Icons.copy_rounded);
          },
          borderRadius: BorderRadius.circular(8),
          child: InfoRow(t('সনদ নম্বর', 'Certificate'), r.certId, mono: true),
        ),
        InfoRow(t('সময়', 'Issued'), '${clock(r.issuedAt)} · ${ago(r.issuedAt)}'),
        InfoRow(t('পরিদর্শক মডেল', 'Inspector model'), r.modelVersion),
        InfoRow(t('স্বাক্ষর', 'Signature'), 'HMAC-SHA256 ${shortId(r.signature, keep: 8)}', mono: true),
        const SizedBox(height: 10),
        AnimatedSwitcher(
          duration: Motion.of(context, Motion.medium),
          child: _check == null
              ? SizedBox(
                  key: const ValueKey('verify'),
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _busy ? null : _verify,
                    icon: _busy ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.shield_outlined),
                    label: Text(t('সনদটি যাচাই করুন', 'Verify this certificate')),
                  ),
                )
              : Pill(
                  key: const ValueKey('result'),
                  ok ? t('যাচাই হয়েছে: স্বাক্ষর ও তথ্য ঠিক আছে', 'Verified: signature and data intact')
                     : t('যাচাই হয়নি: সনদ বদলানো বা অজানা', 'Not verified: changed or unknown certificate'),
                  tone: ok ? Tone.green : Tone.rose,
                  icon: ok ? Icons.check_circle_rounded : Icons.gpp_bad_rounded,
                ),
        ),
      ]),
    );
  }
}
