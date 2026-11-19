import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// Team Heat Wave, from the website's /team/team.json; offline (or on an older site) from the copy bundled with the
/// app, with its photos. A website photo that fails falls back to the bundled one too.
class TeamScreen extends StatefulWidget {
  const TeamScreen({super.key});

  @override
  State<TeamScreen> createState() => _TeamScreenState();
}

class _TeamScreenState extends State<TeamScreen> {
  late Future<(List<Map<String, dynamic>>, bool)> _team = _load();

  // The members, and whether they came from the website (whose photos then load from it).
  Future<(List<Map<String, dynamic>>, bool)> _load() async {
    try {
      final members = mapsOf(
        mapOf(
          await Api.get('/team/team.json', timeout: const Duration(seconds: 6)),
        )?['members'],
      );
      if (members.isNotEmpty) return (members, true);
    } catch (_) {
      // Offline, an older website, or a page instead of JSON: the bundled copy.
    }
    return (
      mapsOf(
        mapOf(
          jsonDecode(await rootBundle.loadString('assets/team/team.json')),
        )?['members'],
      ),
      false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final header = HeaderBand(
      title: t('টিম হিট ওয়েভ', 'Team Heat Wave'),
      subtitle: t(
        'কৃষিনেক্সাস ওএস যাঁরা বানাচ্ছেন',
        'The people building KrishiNexus OS',
      ),
      showHelp: false,
      trailing: IconButton(
        tooltip: t('বন্ধ করুন', 'Close'),
        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
        icon: const Icon(Icons.close_rounded, color: Colors.white, size: 26),
        onPressed: () => Navigator.of(context).maybePop(),
      ),
    );
    return Scaffold(
      body: FutureBuilder(
        future: _team,
        builder: (context, snap) {
          if (snap.data == null) {
            return Column(
              children: [
                header,
                Expanded(
                  child: snap.hasError
                      ? ErrorState(
                          error: snap.error!,
                          onRetry: () => setState(() => _team = _load()),
                        )
                      : const SkeletonList(count: 2, height: 260),
                ),
              ],
            );
          }
          final (members, online) = snap.data!;
          return LayoutBuilder(
            builder: (context, box) {
              final columns = box.maxWidth >= 1000
                  ? 4
                  : box.maxWidth >= 640
                  ? 3
                  : 2;
              return ListView(
                padding: EdgeInsets.only(
                  bottom: 32 + MediaQuery.paddingOf(context).bottom,
                ),
                children: [
                  header,
                  const SizedBox(height: 16),
                  // Rows of equal-height cards: a fixed 4:5 photo, then name, role, bio and links.
                  for (var i = 0; i < members.length; i += columns)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                      child: IntrinsicHeight(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            for (var c = 0; c < columns; c++) ...[
                              if (c > 0) const SizedBox(width: 12),
                              Expanded(
                                child: i + c < members.length
                                    ? _MemberCard(
                                        member: members[i + c],
                                        online: online,
                                      )
                                    : const SizedBox(),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                  const SizedBox(height: 8),
                  Center(
                    child: TextButton.icon(
                      onPressed: () => openWeb(context, '/team/'),
                      icon: const Icon(Icons.open_in_new_rounded),
                      label: Text(
                        t(
                          'ওয়েবসাইটে টিমের পাতা',
                          'The team page on the website',
                        ),
                      ),
                    ),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}

/// A field in the app's language ({"bn": ..., "en": ...}).
String _pick(Object? field) =>
    field is Map ? '${field[app.lang] ?? field['en'] ?? ''}' : '${field ?? ''}';

class _MemberCard extends StatelessWidget {
  const _MemberCard({required this.member, required this.online});
  final Map<String, dynamic> member;
  final bool online;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final name = _pick(member['name']);
    final bundled = Image.asset(
      'assets/team/${member['slug']}.jpg',
      fit: BoxFit.cover,
      excludeFromSemantics: true,
      errorBuilder: (_, _, _) => _Initials(name: name),
    );
    final photo = member['photo'] as String?;
    final links = mapsOf(
      member['links'],
    ).where((l) => _linkUri(l) != null).toList();
    return AppCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AspectRatio(
            aspectRatio: 4 / 5,
            child: online && photo != null
                ? Image.network(
                    photo.startsWith('http') ? photo : '${Api.base}$photo',
                    fit: BoxFit.cover,
                    excludeFromSemantics: true,
                    errorBuilder: (_, _, _) => bundled,
                  )
                : bundled,
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: theme.textTheme.titleMedium),
                const SizedBox(height: 2),
                Text(
                  _pick(member['role']),
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: Tone.green.fg(context),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _pick(member['bio']),
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const Spacer(),
          if (links.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 0, 4, 4),
              child: Wrap(
                children: [
                  for (final l in links)
                    IconButton(
                      constraints: const BoxConstraints(
                        minWidth: 48,
                        minHeight: 48,
                      ),
                      onPressed: () => openLink(context, _linkUri(l)!),
                      icon: Icon(_linkIcon('${l['type']}')),
                      // The tooltip is also what a screen reader says.
                      tooltip: _linkLabel('${l['type']}', name),
                    ),
                ],
              ),
            )
          else
            const SizedBox(height: 6),
        ],
      ),
    );
  }
}

/// Only web and mail links open; anything else in the file is left out.
String? _linkUri(Map<String, dynamic> link) {
  final url = '${link['url'] ?? ''}'.trim();
  if (link['type'] == 'email') {
    return url.isEmpty
        ? null
        : (url.startsWith('mailto:') ? url : 'mailto:$url');
  }
  final scheme = Uri.tryParse(url)?.scheme;
  return scheme == 'https' || scheme == 'http' ? url : null;
}

IconData _linkIcon(String type) => switch (type) {
  'github' => Icons.code_rounded,
  'linkedin' => Icons.work_outline_rounded,
  'facebook' => Icons.facebook_rounded,
  'email' => Icons.mail_outline_rounded,
  'website' => Icons.language_rounded,
  _ => Icons.link_rounded,
};

String _linkLabel(String type, String name) => switch (type) {
  'github' => t('GitHub-এ $name', '$name on GitHub'),
  'linkedin' => t('LinkedIn-এ $name', '$name on LinkedIn'),
  'facebook' => t('Facebook-এ $name', '$name on Facebook'),
  'email' => t('$name-কে ইমেইল করুন', 'Email $name'),
  'website' => t('$name-এর ওয়েবসাইট', '$name\'s website'),
  _ => t('$name-এর লিংক', 'A link from $name'),
};

class _Initials extends StatelessWidget {
  const _Initials({required this.name});
  final String name;

  @override
  Widget build(BuildContext context) {
    final words = name
        .split(RegExp(r'[\s.]+'))
        .where((w) => w.isNotEmpty)
        .toList();
    final initials = words
        .skip(math.max(0, words.length - 2))
        .map((w) => w.characters.first)
        .join();
    return ColoredBox(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: Center(
        child: Text(
          initials,
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
            color: Theme.of(context).colorScheme.onPrimaryContainer,
          ),
        ),
      ),
    );
  }
}
