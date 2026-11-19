import 'package:flutter/material.dart';

import '../core/state.dart';
import '../core/theme.dart';

/// Asks once, before the farmer's own voice, words or photo are used (recorded samples need none). Every claim matches
/// what the node does (website /docs#data): personal details hidden and erased within 24 hours, no audio or photo kept.
Future<bool> ensureConsent(BuildContext context) async {
  if (app.consent) return true;
  final agreed = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (context) {
      final theme = Theme.of(context);
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 20),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(Icons.shield_rounded, color: Tone.sky.fg(context), size: 28),
              const SizedBox(width: 10),
              Text(t('আপনার অনুমতি', 'Your consent'), style: theme.textTheme.titleLarge),
            ]),
            const SizedBox(height: 14),
            Text(
              'আপনার কথা ও ছবি শুধু এই পরামর্শের জন্য ব্যবহার হবে। নাম, ফোন ও এনআইডি নম্বর লুকানো থাকে এবং ২৪ ঘণ্টার মধ্যে '
              'মুছে যায়; কণ্ঠস্বর বা ছবি জমা রাখা হয় না। সিদ্ধান্ত আপনার।',
              style: voiceStyle(context, size: 18),
            ),
            const SizedBox(height: 10),
            Text(
              'Your words and photo are used only for this advice. Names, phone and NID numbers are hidden and erased within 24 '
              'hours; voice and photos are not saved. Online, the phone\'s speech service hears the question. The decision stays yours.',
              style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 20),
            Row(children: [
              Expanded(child: OutlinedButton(onPressed: () => Navigator.pop(context, false), child: Text(t('এখন না', 'Not now')))),
              const SizedBox(width: 12),
              Expanded(child: FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(t('রাজি', 'I agree')))),
            ]),
          ]),
        ),
      );
    },
  );
  if (agreed == true) await app.giveConsent();
  return agreed == true;
}
