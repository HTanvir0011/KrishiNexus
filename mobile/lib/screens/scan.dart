import 'dart:async';
import 'dart:convert';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart' show Geolocator;
import 'package:image_picker/image_picker.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/consent.dart';
import '../widgets/grade_view.dart';

/// How wide the photographed scene is. A photo carries no scale; "no ruler" judges sizes against the lot itself.
const _scales = [
  (0, 'মাপ ছাড়া: লট দেখে', 'No ruler: judge by the lot'),
  (150, 'কাছ থেকে, ১৫ সেমি', 'Close-up, 15 cm'),
  (300, 'এক মুঠো, ৩০ সেমি', 'Handful, 30 cm'),
  (600, 'ঝুড়ি, ৬০ সেমি', 'Crate, 60 cm'),
  (1500, 'স্তূপ, ১.৫ মিটার', 'Heap, 1.5 m'),
];

const _samples = [
  ('high_grade_harvest', 'ভালো মানের লট', 'High-grade lot', Icons.star_rounded),
  ('mixed_wholesale_lot', 'মিশ্র লট', 'Mixed wholesale lot', Icons.blur_on_rounded),
  ('blight_affected_lot', 'ধসা রোগের লট', 'Blight-affected lot', Icons.coronavirus_rounded),
  ('undersized_processing_lot', 'ছোট আকারের লট', 'Undersized lot', Icons.compress_rounded),
];

Route<T> fadeRoute<T>(Widget page) => PageRouteBuilder<T>(
  transitionDuration: const Duration(milliseconds: 420),
  reverseTransitionDuration: const Duration(milliseconds: 260),
  pageBuilder: (_, _, _) => page,
  transitionsBuilder: (context, animation, _, child) {
    if (Motion.reduced(context)) return child;
    final curved = CurvedAnimation(parent: animation, curve: Motion.expo);
    return FadeTransition(
      opacity: curved,
      child: ScaleTransition(scale: Tween(begin: 0.97, end: 1.0).animate(curved), child: child),
    );
  },
);

/// The Scan tab: pick the crop, then photograph it, choose a photo, or grade a recorded sample lot.
class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  String _crop = scanCrops.first;
  int _scaleMm = 0;

  Future<void> _openCamera() async {
    if (!await ensureConsent(context)) return;
    if (!mounted) return;
    await Navigator.of(context).push(fadeRoute(CameraScreen(crop: _crop, frameWidthMm: _scaleMm)));
  }

  Future<void> _fromGallery() async {
    if (!await ensureConsent(context)) return;
    final photo = await pickPhoto();
    if (photo == null || !mounted) return;
    await Navigator.of(context).push(fadeRoute(GradingScreen(crop: _crop, photo: photo, frameWidthMm: _scaleMm)));
  }

  Future<void> _sample() async {
    final preset = await showModalBottomSheet<String>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 4),
              child: Text(t('নমুনা লট বাছুন', 'Choose a sample lot'), style: Theme.of(context).textTheme.titleLarge),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
              child: Text(
                t(
                  'হাতে ফসল না থাকলে: নোডের রেকর্ড করা সর্টিং-ট্রে স্ক্যান।',
                  'No produce at hand? Grade one of the node\'s recorded sorting-tray sweeps.',
                ),
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
              ),
            ),
            for (final s in _samples)
              ListTile(leading: Icon(s.$4), title: Text(t(s.$2, s.$3)), minTileHeight: 56, onTap: () => Navigator.pop(context, s.$1)),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (preset == null || !mounted) return;
    await Navigator.of(context).push(fadeRoute(GradingScreen(crop: _crop, samplePreset: preset, frameWidthMm: _scaleMm)));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(t('ফসল স্ক্যান', 'Scan the harvest'))),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 32),
        children: [
          Text(
            t('ছবি তুলুন, গ্রেড ও সই করা সনদ নিন', 'Photograph the harvest, get a grade and a signed certificate'),
            style: theme.textTheme.headlineSmall,
          ),
          const SizedBox(height: 16),
          Text(t('কোন ফসল?', 'Which crop?'), style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final crop in scanCrops)
                ChoiceChip(label: Text(cropName(crop)), selected: _crop == crop, onSelected: (_) => setState(() => _crop = crop)),
            ],
          ),
          const SizedBox(height: 18),
          _CameraCard(onTap: _openCamera),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _fromGallery,
                  icon: const Icon(Icons.photo_library_rounded),
                  label: Text(t('গ্যালারি', 'Gallery')),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _sample,
                  icon: const Icon(Icons.science_rounded),
                  label: Text(t('নমুনা লট', 'Sample lot')),
                ),
              ),
            ],
          ),
          SectionTitle(t('ছবিতে কতটা জায়গা?', 'How much does the photo cover?')),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final s in _scales)
                ChoiceChip(label: Text(t(s.$2, s.$3)), selected: _scaleMm == s.$1, onSelected: (_) => setState(() => _scaleMm = s.$1)),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            t(
              'মাপ না জানলে "মাপ ছাড়া" রাখুন: তখন লটের নিজের আকারের সাথে তুলনা করে বিচার হয়।',
              'Unsure? Keep "no ruler": sizes are then judged against the lot itself, the way a grader eyeballs a crate.',
            ),
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          ListenableBuilder(
            listenable: app,
            builder: (context, _) => app.grades.isEmpty
                ? const SizedBox.shrink()
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      SectionTitle(t('এই সেশনের গ্রেড', 'Grades this session')),
                      for (final g in app.grades) ...[
                        _GradeRow(
                          entry: g,
                          onTap: () => Navigator.of(context).push(fadeRoute(GradeResultScreen(entry: g))),
                        ),
                        const SizedBox(height: 10),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

Future<Uint8List?> pickPhoto() async {
  final file = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 1600, maxHeight: 1600, imageQuality: 88);
  return file?.readAsBytes();
}

class _CameraCard extends StatelessWidget {
  const _CameraCard({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Pressable(
      child: Material(
        color: Brand.night,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: BorderSide(color: const Color(0xFF6EE7B7).withValues(alpha: 0.28)),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: SizedBox(
            height: 210,
            child: Stack(
              children: [
                const Positioned.fill(child: CustomPaint(painter: _ViewfinderPainter())),
                FractionallySizedBox(
                  widthFactor: 0.6,
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 56,
                          height: 56,
                          decoration: const BoxDecoration(color: Color(0xFF6EE7B7), shape: BoxShape.circle),
                          child: const Icon(Icons.photo_camera_rounded, color: Brand.night, size: 28),
                        ),
                        const Spacer(),
                        Text(t('ক্যামেরা খুলুন', 'Open the camera'), style: theme.textTheme.titleLarge?.copyWith(color: Brand.husk)),
                        const SizedBox(height: 4),
                        Text(
                          t('উপর থেকে, দিনের আলোয়, ফসল একস্তরে ছড়িয়ে তুলুন', 'From above, in daylight, produce spread in one layer'),
                          style: theme.textTheme.bodyMedium?.copyWith(color: Brand.silt),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ViewfinderPainter extends CustomPainter {
  const _ViewfinderPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final dots = Paint()..color = Brand.husk.withValues(alpha: 0.07);
    for (var x = 12.0; x < size.width; x += 18) {
      for (var y = 12.0; y < size.height; y += 18) {
        canvas.drawCircle(Offset(x, y), 1.1, dots);
      }
    }
    final b = Paint()
      ..color = const Color(0xFF6EE7B7).withValues(alpha: 0.7)
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    final r = Rect.fromLTWH(size.width * 0.58, 22, size.width * 0.36, size.height - 44);
    const l = 22.0;
    for (final (p, dx, dy) in [(r.topLeft, 1.0, 1.0), (r.topRight, -1.0, 1.0), (r.bottomLeft, 1.0, -1.0), (r.bottomRight, -1.0, -1.0)]) {
      canvas.drawLine(p, p + Offset(l * dx, 0), b);
      canvas.drawLine(p, p + Offset(0, l * dy), b);
    }
    final potato = Paint()..color = const Color(0xFFC7895E).withValues(alpha: 0.85);
    for (final (dx, dy, w, h) in [(0.18, 0.2, 0.34, 0.26), (0.56, 0.3, 0.3, 0.24), (0.3, 0.58, 0.32, 0.25)]) {
      canvas.drawOval(Rect.fromLTWH(r.left + r.width * dx, r.top + r.height * dy, r.width * w, r.height * h), potato);
    }
  }

  @override
  bool shouldRepaint(_ViewfinderPainter oldDelegate) => false;
}

class _GradeRow extends StatelessWidget {
  const _GradeRow({required this.entry, required this.onTap});
  final GradeEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final r = entry.result;
    return AppCard(
      padding: const EdgeInsets.all(10),
      onTap: onTap,
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: SizedBox.square(
              dimension: 56,
              child: entry.photo != null
                  ? Image.memory(entry.photo!, fit: BoxFit.cover, cacheWidth: 168)
                  : ColoredBox(
                      color: Brand.night,
                      child: Icon(Icons.science_rounded, color: Brand.silt),
                    ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${cropName(r.crop)} · ${gradeName(r.grade)}', style: theme.textTheme.titleSmall),
                Text(
                  '${entry.photo != null ? t('ছবি', 'Photo') : t('নমুনা লট', 'Sample lot')} · ${digits(r.boxes.length)} ${t('টি', 'pieces')} · ${ago(r.issuedAt)}',
                  style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
          GradeStamp(letter: r.grade, size: 44),
        ],
      ),
    );
  }
}

/// Full-screen viewfinder: framing guide, tap to focus, torch, gallery and the shutter.
class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key, required this.crop, required this.frameWidthMm});
  final String crop;
  final int frameWidthMm;

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> with WidgetsBindingObserver {
  CameraController? _controller;
  String? _error;
  bool _denied = false; // the camera permission is off: the phone's settings can turn it on
  bool _starting = false;
  bool _stopped = false; // the app went to the background and closed a running camera
  bool _capturing = false;
  bool _torch = false;
  Offset? _focus;
  int _focusTick = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _start();
  }

  Future<void> _start() async {
    // One start at a time: the permission prompt pauses and resumes the app while the first one is still running.
    if (_starting) return;
    _starting = true;
    _denied = false;
    if (_error != null) setState(() => _error = null);
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) throw CameraException('NoCamera', 'No camera on this device');
      final back = cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => cameras.first);
      final controller = CameraController(back, ResolutionPreset.veryHigh, enableAudio: false, imageFormatGroup: ImageFormatGroup.jpeg);
      await controller.initialize();
      try {
        await controller.setFlashMode(FlashMode.off);
      } catch (_) {
        // no flash unit
      }
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _torch = false;
      });
    } on CameraException catch (e) {
      if (!mounted) return;
      _denied = e.code.startsWith('CameraAccess');
      setState(
        () => _error = switch (e.code) {
          'CameraAccessDenied' || 'CameraAccessDeniedWithoutPrompt' || 'CameraAccessRestricted' => t(
            'ক্যামেরার অনুমতি নেই। ফোনের সেটিংসে KrishiNexus-কে ক্যামেরা ব্যবহারের অনুমতি দিন, অথবা গ্যালারি থেকে ছবি নিন।',
            'Camera permission is off. Allow it for KrishiNexus in the phone settings, or pick a photo from the gallery.',
          ),
          'NoCamera' || 'cameraNotFound' => t(
            'এই ডিভাইসে ক্যামেরা পাওয়া যায়নি। গ্যালারি থেকে ছবি নিন।',
            'No camera found on this device. Pick a photo from the gallery instead.',
          ),
          _ => t('ক্যামেরা চালু হলো না (${e.code})।', 'The camera did not start (${e.code}).'),
        },
      );
    } catch (_) {
      if (mounted) setState(() => _error = t('ক্যামেরা চালু হলো না।', 'The camera did not start.'));
    } finally {
      _starting = false;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Only a running camera stops and restarts: the permission prompt (and the gallery) also pause the app, and a
    // second start then would open the camera twice or ask for the permission again.
    if (state == AppLifecycleState.inactive || state == AppLifecycleState.paused) {
      final controller = _controller;
      if (controller == null) return;
      _controller = null;
      _stopped = true;
      _torch = false;
      controller.dispose();
      if (mounted) setState(() {});
    } else if (state == AppLifecycleState.resumed && _stopped) {
      _stopped = false;
      _start();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _capture() async {
    final controller = _controller;
    if (controller == null || _capturing || controller.value.isTakingPicture) return;
    HapticFeedback.mediumImpact();
    setState(() => _capturing = true);
    try {
      final file = await controller.takePicture();
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      await Navigator.of(
        context,
      ).pushReplacement(fadeRoute(GradingScreen(crop: widget.crop, photo: bytes, frameWidthMm: widget.frameWidthMm)));
    } catch (e) {
      if (!mounted) return;
      setState(() => _capturing = false);
      snack(
        context,
        t('ছবি তোলা গেল না, আবার চেষ্টা করুন।', 'The photo could not be taken; try again.'),
        tone: Tone.rose,
        icon: Icons.error_outline_rounded,
      );
    }
  }

  Future<void> _gallery() async {
    final photo = await pickPhoto();
    if (photo == null || !mounted) return;
    await Navigator.of(
      context,
    ).pushReplacement(fadeRoute(GradingScreen(crop: widget.crop, photo: photo, frameWidthMm: widget.frameWidthMm)));
  }

  Future<void> _toggleTorch() async {
    final controller = _controller;
    if (controller == null) return;
    try {
      await controller.setFlashMode(_torch ? FlashMode.off : FlashMode.torch);
      HapticFeedback.selectionClick();
      setState(() => _torch = !_torch);
    } catch (_) {
      if (mounted) snack(context, t('এই ফোনে টর্চ নেই।', 'This phone has no torch.'));
    }
  }

  // [size] is the preview's own (the tap is read inside it), so the point is in the camera frame, not the cropped screen.
  Future<void> _focusAt(TapUpDetails d, Size size) async {
    final controller = _controller;
    if (controller == null) return;
    setState(() {
      _focus = d.globalPosition; // the viewfinder fills the screen from its top-left corner
      _focusTick++;
    });
    final point = Offset((d.localPosition.dx / size.width).clamp(0, 1), (d.localPosition.dy / size.height).clamp(0, 1));
    try {
      if (controller.value.focusPointSupported) await controller.setFocusPoint(point);
      if (controller.value.exposurePointSupported) await controller.setExposurePoint(point);
    } catch (_) {
      // the lens keeps its own focus
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    final size = MediaQuery.sizeOf(context);
    final ready = controller != null && controller.value.isInitialized;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(
          fit: StackFit.expand,
          children: [
            if (ready)
              ClipRect(
                child: Transform.scale(
                  scale: _coverScale(size, controller.value.aspectRatio),
                  child: Center(
                    child: CameraPreview(
                      controller,
                      child: LayoutBuilder(
                        builder: (context, box) => GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onTapUp: (d) => _focusAt(d, box.biggest),
                        ),
                      ),
                    ),
                  ),
                ),
              )
            else if (_error == null)
              const Center(child: CircularProgressIndicator(color: Colors.white)),
            if (ready) const IgnorePointer(child: CustomPaint(painter: _FramePainter())),
            if (_focus != null)
              Positioned(
                left: _focus!.dx - 36,
                top: _focus!.dy - 36,
                child: IgnorePointer(
                  child: TweenAnimationBuilder<double>(
                    key: ValueKey(_focusTick),
                    tween: Tween(begin: 1.4, end: 1),
                    duration: Motion.of(context, const Duration(milliseconds: 420)),
                    curve: Motion.expo,
                    builder: (_, s, _) => Transform.scale(
                      scale: s,
                      child: Container(
                        width: 72,
                        height: 72,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: Brand.mustard, width: 2),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            if (_error != null)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.no_photography_rounded, color: Brand.husk, size: 48),
                      const SizedBox(height: 16),
                      Text(
                        _error!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Brand.husk, fontSize: 16, height: 1.5),
                      ),
                      const SizedBox(height: 20),
                      if (_denied && !kIsWeb) ...[
                        FilledButton.icon(
                          // Opens this app's page in the phone settings (any permission, the camera's too).
                          onPressed: Geolocator.openAppSettings,
                          icon: const Icon(Icons.settings_rounded),
                          label: Text(t('ফোনের সেটিংস খুলুন', 'Open the phone settings')),
                        ),
                        const SizedBox(height: 10),
                      ],
                      FilledButton.icon(
                        onPressed: _gallery,
                        icon: const Icon(Icons.photo_library_rounded),
                        label: Text(t('গ্যালারি থেকে নিন', 'Pick from the gallery')),
                      ),
                      TextButton(
                        onPressed: _start,
                        child: Text(t('আবার চেষ্টা', 'Try again'), style: const TextStyle(color: Brand.husk)),
                      ),
                    ],
                  ),
                ),
              ),
            SafeArea(
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(8, 4, 8, 0),
                    child: Row(
                      children: [
                        IconButton(
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.close_rounded, color: Colors.white),
                          tooltip: t('বন্ধ', 'Close'),
                        ),
                        const Spacer(),
                        _GlassChip(icon: Icons.eco_rounded, label: cropName(widget.crop)),
                        const Spacer(),
                        IconButton(
                          onPressed: ready ? _toggleTorch : null,
                          icon: Icon(
                            _torch ? Icons.flashlight_on_rounded : Icons.flashlight_off_rounded,
                            color: _torch ? Brand.mustard : Colors.white,
                          ),
                          tooltip: t('টর্চ', 'Torch'),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  if (ready)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 32),
                      child: Text(
                        t(
                          'ফসল ফ্রেমের ভেতরে একস্তরে ছড়িয়ে রাখুন, উপর থেকে তুলুন',
                          'Spread the produce in one layer inside the frame; shoot from above',
                        ),
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.4, shadows: [Shadow(blurRadius: 8)]),
                      ),
                    ),
                  const SizedBox(height: 20),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(28, 0, 28, 20),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _RoundButton(icon: Icons.photo_library_rounded, label: t('গ্যালারি', 'Gallery'), onTap: _gallery),
                        _Shutter(onTap: ready ? _capture : null, busy: _capturing),
                        _RoundButton(
                          icon: Icons.straighten_rounded,
                          label: widget.frameWidthMm == 0
                              ? t('মাপ ছাড়া', 'No ruler')
                              : '${digits(widget.frameWidthMm ~/ 10)} ${t('সেমি', 'cm')}',
                          onTap: null,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // The preview fills the screen (cover); the photo keeps the camera's full frame.
  double _coverScale(Size screen, double previewAspect) {
    final scale = screen.aspectRatio * previewAspect;
    return scale < 1 ? 1 / scale : scale;
  }
}

class _FramePainter extends CustomPainter {
  const _FramePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width * 0.86;
    final h = (w * 1.2).clamp(0, size.height * 0.58).toDouble();
    final guide = Rect.fromCenter(center: Offset(size.width / 2, size.height * 0.45), width: w, height: h);
    final outer = Path()..addRect(Offset.zero & size);
    final inner = Path()..addRRect(RRect.fromRectAndRadius(guide, const Radius.circular(24)));
    canvas.drawPath(Path.combine(PathOperation.difference, outer, inner), Paint()..color = Colors.black.withValues(alpha: 0.38));
    final b = Paint()
      ..color = Colors.white
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    const l = 30.0;
    for (final (p, dx, dy) in [
      (guide.topLeft, 1.0, 1.0),
      (guide.topRight, -1.0, 1.0),
      (guide.bottomLeft, 1.0, -1.0),
      (guide.bottomRight, -1.0, -1.0),
    ]) {
      canvas.drawLine(p + Offset(0, 12 * dy), p + Offset(0, l * dy), b);
      canvas.drawLine(p + Offset(12 * dx, 0), p + Offset(l * dx, 0), b);
    }
  }

  @override
  bool shouldRepaint(_FramePainter oldDelegate) => false;
}

class _GlassChip extends StatelessWidget {
  const _GlassChip({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
    decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.45), borderRadius: BorderRadius.circular(999)),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: const Color(0xFF6EE7B7)),
        const SizedBox(width: 6),
        Text(
          label,
          style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
        ),
      ],
    ),
  );
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 72,
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Material(
          color: Colors.white.withValues(alpha: 0.16),
          shape: const CircleBorder(),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: onTap,
            child: SizedBox.square(dimension: 52, child: Icon(icon, color: Colors.white)),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: Colors.white, fontSize: 12),
        ),
      ],
    ),
  );
}

class _Shutter extends StatefulWidget {
  const _Shutter({required this.onTap, required this.busy});
  final VoidCallback? onTap;
  final bool busy;

  @override
  State<_Shutter> createState() => _ShutterState();
}

class _ShutterState extends State<_Shutter> {
  bool _down = false;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    label: t('ছবি তুলুন', 'Take the photo'),
    child: GestureDetector(
      onTapDown: (_) => setState(() => _down = true),
      onTapCancel: () => setState(() => _down = false),
      onTapUp: (_) {
        setState(() => _down = false);
        widget.onTap?.call();
      },
      child: Container(
        width: 84,
        height: 84,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 4),
        ),
        padding: const EdgeInsets.all(6),
        child: AnimatedScale(
          scale: _down ? 0.86 : 1,
          duration: Motion.of(context, const Duration(milliseconds: 120)),
          child: Container(
            decoration: BoxDecoration(shape: BoxShape.circle, color: widget.onTap == null ? Colors.white38 : Colors.white),
            child: widget.busy
                ? const Padding(
                    padding: EdgeInsets.all(20),
                    child: CircularProgressIndicator(strokeWidth: 3, color: Brand.green),
                  )
                : null,
          ),
        ),
      ),
    ),
  );
}

/// Sends the photo (or a sample preset) to POST /edge/grade-crop while a light sweeps it, then shows the grade.
class GradingScreen extends StatefulWidget {
  const GradingScreen({super.key, required this.crop, this.photo, this.samplePreset, this.frameWidthMm = 0});
  final String crop;
  final Uint8List? photo;
  final String? samplePreset;
  final int frameWidthMm;

  @override
  State<GradingScreen> createState() => _GradingScreenState();
}

class _GradingScreenState extends State<GradingScreen> {
  Object? _error;
  bool _reduced = false;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = Motion.reduced(context);
    if (!_started) {
      _started = true;
      _run();
    }
  }

  Future<void> _run() async {
    if (_error != null) setState(() => _error = null);
    final user = app.user;
    final district = user?.district ?? '';
    final body = <String, dynamic>{
      'crop': widget.crop,
      if (district.isNotEmpty) 'district': district,
      if (user?.role == 'farmer') 'farmer_id': user!.id,
      if (widget.photo != null) ...{
        'image_base64': 'data:image/jpeg;base64,${base64Encode(widget.photo!)}',
        if (widget.frameWidthMm > 0) 'frame_width_mm': widget.frameWidthMm,
      } else
        'sample_preset': widget.samplePreset,
    };
    try {
      // Let the sweep cross the photo at least once, so a fast answer still reads as an inspection.
      final results = await Future.wait([
        Api.post('/edge/grade-crop', body, const Duration(seconds: 120)),
        Future<void>.delayed(_reduced ? Duration.zero : const Duration(milliseconds: 1300)),
      ]);
      final result = GradeResult((results.first as Map).cast<String, dynamic>());
      app.addGrade(result, widget.photo);
      if (!mounted) return;
      HapticFeedback.heavyImpact();
      await Navigator.of(context).pushReplacement(fadeRoute(GradeResultScreen(entry: app.grades.first)));
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      backgroundColor: Brand.night,
      appBar: AppBar(backgroundColor: Brand.night, foregroundColor: Brand.husk, systemOverlayStyle: SystemUiOverlayStyle.light),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(
            children: [
              Expanded(
                child: Center(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(24),
                    child: Stack(
                      children: [
                        if (widget.photo != null)
                          Image.memory(widget.photo!, fit: BoxFit.contain, gaplessPlayback: true)
                        else
                          const AspectRatio(
                            aspectRatio: 4 / 3,
                            child: ColoredBox(
                              color: Color(0xFF1E2B24),
                              child: Center(child: Icon(Icons.science_rounded, size: 56, color: Brand.silt)),
                            ),
                          ),
                        if (_error == null) const Positioned.fill(child: ScanSweep()),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              if (_error == null) ...[
                Text(t('গ্রেড করা হচ্ছে…', 'Grading…'), style: theme.textTheme.headlineSmall?.copyWith(color: Brand.husk)),
                const SizedBox(height: 6),
                Text(
                  t(
                    'আকার, দাগ, পচন আর আর্দ্রতা মাপা হচ্ছে; তারপর সনদে সই হবে।',
                    'Measuring size, bruising, rot and moisture, then signing the certificate.',
                  ),
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(color: Brand.silt),
                ),
              ] else ...[
                const Icon(Icons.error_outline_rounded, color: Brand.sunRed, size: 36),
                const SizedBox(height: 10),
                Text(
                  friendlyError(_error!),
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyLarge?.copyWith(color: Brand.husk),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.of(context).pop(),
                        style: OutlinedButton.styleFrom(foregroundColor: Brand.husk),
                        child: Text(t('ফিরে যান', 'Go back')),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(onPressed: _run, child: Text(t('আবার চেষ্টা', 'Try again'))),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// The grade: photo with every piece outlined, the stamped letter, measurements, reasons and the signed certificate.
class GradeResultScreen extends StatelessWidget {
  const GradeResultScreen({super.key, required this.entry});
  final GradeEntry entry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final r = entry.result;
    final farmer = app.user?.role == 'farmer';
    return Scaffold(
      appBar: AppBar(title: Text('${cropName(r.crop)} · ${t('গ্রেড', 'Grade')} ${r.grade}')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
        children: [
          GradeCanvas(result: r, photo: entry.photo),
          const SizedBox(height: 10),
          GradeLegend(result: r),
          const SizedBox(height: 4),
          Text(
            t('কোনো টুকরোতে ট্যাপ করে তার মাপ দেখুন', 'Tap a piece to see its size and defect'),
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              GradeStamp(letter: r.grade),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(gradeName(r.grade), style: theme.textTheme.titleLarge),
                    const SizedBox(height: 4),
                    if (r.premiumPct != 0)
                      Pill(
                        r.premiumPct > 0
                            ? t(
                                'দামে +${digits(r.premiumPct.toStringAsFixed(0))}% বাড়তি',
                                '+${r.premiumPct.toStringAsFixed(0)}% price premium',
                              )
                            : t('দামে ${digits(r.premiumPct.toStringAsFixed(0))}%', '${r.premiumPct.toStringAsFixed(0)}% on price'),
                        tone: r.premiumPct > 0 ? Tone.green : Tone.amber,
                        icon: Icons.trending_up_rounded,
                      ),
                    const SizedBox(height: 6),
                    Text(
                      '${r.backend} · ${digits(r.latencyMs.toStringAsFixed(0))} ms',
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ],
          ),
          for (final w in r.warnings) ...[
            const SizedBox(height: 12),
            AppCard(
              tone: Tone.amber,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.warning_amber_rounded, color: Tone.amber.fg(context)),
                  const SizedBox(width: 10),
                  Expanded(child: Text(w, style: theme.textTheme.bodyMedium)),
                ],
              ),
            ),
          ],
          if (r.reasons.isNotEmpty) ...[
            SectionTitle(t('কেন এই গ্রেড', 'Why this grade')),
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final reason in r.reasons)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Container(
                              width: 6,
                              height: 6,
                              decoration: BoxDecoration(color: theme.colorScheme.primary, shape: BoxShape.circle),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(child: Text(reason, style: theme.textTheme.bodyMedium)),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 16),
          GradeMetrics(result: r),
          const SizedBox(height: 16),
          CertificateCard(result: r),
          const SizedBox(height: 20),
          if (farmer && marketCrops.contains(r.crop)) ...[
            FilledButton.icon(
              onPressed: () {
                Navigator.of(context).popUntil((route) => route.isFirst);
                app.sellLot({'crop': r.crop, 'grade': r.grade, 'certificate_id': r.certId, 'district': app.user?.district ?? ''});
              },
              icon: const Icon(Icons.storefront_rounded),
              label: Text(t('এই লট বাজারে বেচুন', 'Sell this lot on the market')),
            ),
            const SizedBox(height: 10),
          ],
          if (app.user?.role != 'buyer')
            OutlinedButton.icon(
              onPressed: () {
                Navigator.of(context).popUntil((route) => route.isFirst);
                app.askWith(r.certId);
              },
              icon: const Icon(Icons.mic_rounded),
              label: Text(t('এই গ্রেড দিয়ে পরামর্শ নিন', 'Ask for advice with this grade')),
            ),
        ],
      ),
    );
  }
}
