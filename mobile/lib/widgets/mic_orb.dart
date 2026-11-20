import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme.dart';

enum OrbState { idle, listening, thinking }

/// The voice button: a mustard orb at rest (mustard is the voice colour); while listening it turns red, swells with the
/// voice and sends rings outward; while the agents work a green arc runs around it.
class MicOrb extends StatefulWidget {
  const MicOrb({
    super.key,
    required this.state,
    required this.level,
    required this.onTap,
    this.size = 148,
    required this.label,
  });
  final OrbState state;
  final ValueListenable<double> level;
  final VoidCallback? onTap;
  final double size;
  final String label;

  @override
  State<MicOrb> createState() => _MicOrbState();
}

class _MicOrbState extends State<MicOrb> with SingleTickerProviderStateMixin {
  late final _clock = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  );
  double _smoothed = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sync();
  }

  @override
  void didUpdateWidget(MicOrb old) {
    super.didUpdateWidget(old);
    if (old.state != widget.state) _sync();
  }

  void _sync() {
    final moving = widget.state != OrbState.idle && !Motion.reduced(context);
    if (moving && !_clock.isAnimating) _clock.repeat();
    if (!moving && _clock.isAnimating) _clock.stop();
  }

  @override
  void dispose() {
    _clock.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final listening = widget.state == OrbState.listening;
    final thinking = widget.state == OrbState.thinking;
    final core = listening ? Tone.rose.fg(context) : Brand.voice;
    final iconColor = listening ? Colors.white : Brand.ink;
    return Semantics(
      button: true,
      label: widget.label,
      child: GestureDetector(
        onTap: widget.onTap == null
            ? null
            : () {
                HapticFeedback.mediumImpact();
                widget.onTap!();
              },
        child: SizedBox.square(
          dimension: widget.size * 1.7,
          child: AnimatedBuilder(
            animation: Listenable.merge([_clock, widget.level]),
            builder: (context, _) {
              // Ease the raw level so the orb breathes with the voice instead of flickering.
              _smoothed += (widget.level.value - _smoothed) * 0.35;
              final breathe = listening && widget.level.value == 0
                  ? 0.08 * (0.5 + 0.5 * math.sin(_clock.value * math.pi * 4))
                  : 0.0;
              final swell = listening ? 1 + 0.16 * _smoothed + breathe : 1.0;
              return CustomPaint(
                painter: _OrbPainter(
                  t: _clock.value,
                  listening: listening,
                  thinking: thinking,
                  level: _smoothed,
                  core: core,
                  ring: core,
                  arc: scheme.primary,
                  reduced: Motion.reduced(context),
                ),
                child: Center(
                  child: Transform.scale(
                    scale: swell,
                    child: AnimatedContainer(
                      duration: Motion.of(context, Motion.medium),
                      curve: Motion.expo,
                      width: widget.size,
                      height: widget.size,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(
                          center: const Alignment(-0.3, -0.35),
                          colors: [Color.lerp(core, Colors.white, 0.22)!, core],
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: core.withValues(alpha: 0.32),
                            blurRadius: 28,
                            offset: const Offset(0, 12),
                          ),
                        ],
                      ),
                      child: AnimatedSwitcher(
                        duration: Motion.of(context, Motion.short),
                        child: Icon(
                          thinking
                              ? Icons.auto_awesome_rounded
                              : listening
                              ? Icons.stop_rounded
                              : Icons.mic_rounded,
                          key: ValueKey(widget.state),
                          size: widget.size * 0.4,
                          color: iconColor,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _OrbPainter extends CustomPainter {
  _OrbPainter({
    required this.t,
    required this.listening,
    required this.thinking,
    required this.level,
    required this.core,
    required this.ring,
    required this.arc,
    required this.reduced,
  });

  final double t;
  final bool listening;
  final bool thinking;
  final double level;
  final Color core;
  final Color ring;
  final Color arc;
  final bool reduced;

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.width / 1.7 / 2;
    if (listening && !reduced) {
      // Three rings travel outward and fade; the voice level widens them.
      for (var i = 0; i < 3; i++) {
        final p = (t * 1.5 + i / 3) % 1.0;
        final radius = r * (1.0 + p * (0.55 + 0.25 * level));
        canvas.drawCircle(
          c,
          radius,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2.5
            ..color = ring.withValues(alpha: (1 - p) * 0.45),
        );
      }
    } else if (!thinking) {
      canvas.drawCircle(
        c,
        r * 1.18,
        Paint()..color = ring.withValues(alpha: 0.10),
      );
    }
    if (thinking) {
      final rect = Rect.fromCircle(center: c, radius: r * 1.2);
      canvas.drawCircle(
        c,
        r * 1.2,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 5
          ..color = arc.withValues(alpha: 0.16),
      );
      final start = reduced ? -math.pi / 2 : t * math.pi * 2 * 1.5;
      canvas.drawArc(
        rect,
        start,
        math.pi * 0.75,
        false,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 5
          ..strokeCap = StrokeCap.round
          ..color = arc,
      );
    }
  }

  @override
  bool shouldRepaint(_OrbPainter old) =>
      old.t != t ||
      old.level != level ||
      old.listening != listening ||
      old.thinking != thinking ||
      old.core != core;
}
