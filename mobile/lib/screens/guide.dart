import 'package:flutter/material.dart';

import '../core/format.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// "How to use KrishiNexus" in plain words: what the app does, each role step by step, accounts and the data kept,
/// live tracking, offline mode and a short FAQ, with links to the website's own pages.
class GuideScreen extends StatelessWidget {
  const GuideScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: ListView(
        padding: EdgeInsets.only(
          bottom: 40 + MediaQuery.paddingOf(context).bottom,
        ),
        children: [
          HeaderBand(
            title: t('কীভাবে ব্যবহার করবেন', 'How to use KrishiNexus'),
            showHelp: false,
            trailing: IconButton(
              tooltip: t('বন্ধ করুন', 'Close'),
              constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
              icon: const Icon(
                Icons.close_rounded,
                color: Colors.white,
                size: 26,
              ),
              onPressed: () => Navigator.of(context).maybePop(),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _Section(
                  icon: Icons.eco_rounded,
                  title: t('অ্যাপটি কী করে', 'What the app does'),
                  top: 24,
                  body: [
                    t(
                      'কৃষিনেক্সাস কৃষককে ন্যায্য দাম পেতে সাহায্য করে। বাংলায় মুখে প্রশ্ন করুন, ফসলের ছবি তুলে সই করা গ্রেড নিন, আর সরাসরি ক্রেতার কাছে বেচুন। '
                          'ক্রেতার টাকা মাল পৌঁছানো পর্যন্ত ব্যাংকে জমা থাকে, একজন ট্রাক চালক মাল পৌঁছে দেন। দর, বিক্রি আর ডেলিভারির খবর সাথে সাথে আসে।',
                      'KrishiNexus helps farmers get a fair price. Ask in Bangla by voice, photograph the harvest for a signed grade, and sell '
                          'straight to buyers. The buyer\'s money stays with the bank until the produce arrives, and a truck driver delivers it. '
                          'Bids, sales and deliveries show up as they happen.',
                    ),
                  ],
                ),
                _Role(
                  icon: Icons.agriculture_rounded,
                  title: t('কৃষক', 'Farmer'),
                  steps: [
                    t(
                      'জিজ্ঞাসা: মাইক চেপে বাংলায় প্রশ্ন বলুন, বা লিখুন। উত্তর পড়ে শোনানো হয়।',
                      'Ask: tap the microphone and say your question in Bangla, or type it. The answer is read aloud.',
                    ),
                    t(
                      'স্ক্যান: ফসল বাছুন, দিনের আলোয় উপর থেকে ছবি তুলুন। গ্রেড আর সই করা সনদ পাবেন।',
                      'Scan: choose the crop and photograph it from above in daylight. You get a grade and a signed certificate.',
                    ),
                    t(
                      'বাজার → নতুন লট: কেজি বা মণে পরিমাণ দিন। ক্রেতারা খোলাখুলি দর দেন।',
                      'Market → List a lot: enter the amount in kg or maund. Buyers bid in the open.',
                    ),
                    t(
                      'যে দর পছন্দ, "গ্রহণ" চাপুন ও ওয়ালেট বাছুন। ক্রেতার টাকা ব্যাংকে জমা হয়।',
                      'Tap Accept on the bid you want and choose your wallet. The buyer\'s money is held by the bank.',
                    ),
                    t(
                      'চালক মাল তুলে পৌঁছে দিলে টাকা আপনার ওয়ালেটে ছাড়া হয়।',
                      'When the driver delivers, the payment is released to your wallet.',
                    ),
                    t(
                      'সমস্যা হলে লটটি খুলে "সমস্যা জানান" চাপুন; ব্যাংক দেখবে।',
                      'Something wrong? Open the lot and tap Report a problem; the bank looks into it.',
                    ),
                  ],
                ),
                _Role(
                  icon: Icons.storefront_rounded,
                  title: t('ক্রেতা', 'Buyer'),
                  steps: [
                    t(
                      'বাজার: ফসল ধরে খোলা লট দেখুন। সবুজ সনদ-চিহ্ন মানে ক্যামেরায় গ্রেড যাচাই হয়েছে।',
                      'Market: browse open lots by crop. The green certificate mark means the grade was checked by camera.',
                    ),
                    t(
                      'দর দিন: +০.২৫, +০.৫০, +১.০০ দিয়ে বাড়ান বা নিজে লিখুন। আপনি এগিয়ে না পিছিয়ে, সাথে সাথে দেখবেন।',
                      'Bid: raise by +0.25, +0.50 or +1.00, or type your price. You see at once whether you lead or were outbid.',
                    ),
                    t(
                      'কেনা: জেতা লট, টাকা আর ডেলিভারি; ট্রাক কোথায় তাও দেখবেন।',
                      'Purchases: lots you won, the payment and the delivery, with the truck on its way.',
                    ),
                    t(
                      'যাচাই: যেকোনো সনদ নম্বর দিয়ে দেখুন সেটি আসল কিনা।',
                      'Verify: enter any certificate number to check it is genuine.',
                    ),
                  ],
                ),
                _Role(
                  icon: Icons.local_shipping_rounded,
                  title: t('ট্রাক চালক', 'Truck driver'),
                  steps: [
                    t(
                      'কাজ: চালকের অপেক্ষায় থাকা একটি কাজ নিন।',
                      'Jobs: take a job that is waiting for a driver.',
                    ),
                    t(
                      'চলতি: কৃষকের কাছে মাল তুলে "মাল তুলেছি" চাপুন।',
                      'On the road: at the farm, tap I picked it up.',
                    ),
                    t(
                      'ট্রাকের ভেতরের তাপমাত্রা জমা দিন; অ্যাপ দেখে নেয় পথে মাল টিকবে কিনা।',
                      'Log the temperature inside the truck; the app checks the produce will last the drive.',
                    ),
                    t(
                      'চাইলে লাইভ লোকেশন চালু করুন: ক্রেতা ও কৃষক ট্রাকের আনুমানিক অবস্থান দেখবেন।',
                      'If you like, turn on Share live location: the buyer and the farmer see roughly where the truck is.',
                    ),
                    t(
                      'পৌঁছে "পৌঁছে দিয়েছি" চাপুন; ব্যাংক কৃষকের টাকা ছেড়ে দেয়।',
                      'On arrival, tap I delivered it; the bank releases the farmer\'s payment.',
                    ),
                  ],
                ),
                _Role(
                  icon: Icons.account_balance_rounded,
                  title: t(
                    'সমবায়, হিমাগার ও ব্যাংক',
                    'Co-op, cold storage and bank',
                  ),
                  steps: [
                    t(
                      'সমবায় দেখে ট্রাক পুল কতটা ভরেছে; হিমাগার দেখে চেম্বারের সতর্কতা।',
                      'The co-op sees how full its truck pools are; cold storage sees chamber alerts.',
                    ),
                    t(
                      'ব্যাংক অভিযোগের মীমাংসা করে (টাকা ছাড়া, ফেরত বা আটকে রাখা) আর সব লেনদেন দেখে।',
                      'The bank settles disputes (release, refund or keep holding) and sees every payment.',
                    ),
                    t(
                      'পুরো ডেস্ক খোলে ওয়েবসাইটে।',
                      'The full desks open on the website.',
                    ),
                  ],
                ),
                _Section(
                  icon: Icons.person_add_alt_1_rounded,
                  title: t(
                    'অ্যাকাউন্ট খোলা ও কী তথ্য রাখা হয়',
                    'Creating an account and what is kept',
                  ),
                  body: [
                    t(
                      'লগইন পাতায় "নতুন অ্যাকাউন্ট খুলুন" চাপুন। কৃষক, ক্রেতা ও ট্রাক চালকের অ্যাকাউন্ট সাথে সাথে চালু হয়; সমবায়, হিমাগার ও ব্যাংকের অ্যাকাউন্ট অ্যাডমিন দেখে চালু করেন।',
                      'On the login screen, tap Create an account. Farmer, buyer and truck driver accounts open at once; co-op, cold-storage and bank accounts open after an admin checks them.',
                    ),
                    t(
                      'লাগে: নাম, মোবাইল নম্বর, জাতীয় পরিচয়পত্র, জেলা, একটি মোবাইল ব্যাংকিং ওয়ালেট (বিকাশ, নগদ, রকেট বা উপায়) আর পাসওয়ার্ড।',
                      'You give your name, mobile number, national ID, district, a mobile-banking wallet (bKash, Nagad, Rocket or Upay) and a password.',
                    ),
                    t(
                      'জাতীয় পরিচয়পত্র, ফোন ও ওয়ালেটের নম্বর হ্যাশ করে রাখা হয়: অ্যাপে শুধু শেষ কয়েকটি অঙ্ক দেখা যায়, পুরো নম্বর আর কখনো দেখানো হয় না। পাসওয়ার্ডও হ্যাশ করা থাকে।',
                      'The national ID, phone and wallet numbers are kept hashed: the app shows only their last digits and never the full number again. The password is hashed too.',
                    ),
                    t(
                      'টাকা যায় শুধু নিবন্ধিত ওয়ালেটে। অ্যাকাউন্ট আইডিটি মনে রাখুন: আইডি ও পাসওয়ার্ড দিয়েই লগইন করবেন (আমি ট্যাবে দেখা যায়)।',
                      'Payouts go only to the registered wallet. Keep your account ID: you log in with it and your password (the Me tab shows it).',
                    ),
                  ],
                ),
                _Section(
                  icon: Icons.sensors_rounded,
                  title: t(
                    'লাইভ খবর ও ট্রাক কোথায়',
                    'Live updates and where the truck is',
                  ),
                  body: [
                    t(
                      'দর, বিক্রি, মাল তোলা আর পৌঁছানো সাথে সাথে দেখায়। উপরে সবুজ বিন্দু ও "লাইভ" মানে সংযোগ আছে।',
                      'Bids, sales, pickups and deliveries appear as they happen. The green dot and Live at the top mean the connection is on.',
                    ),
                    t(
                      'আপনার লটে দর এলে, কেউ আপনাকে ছাড়িয়ে গেলে, লট বিক্রি, তোলা বা পৌঁছালে ছোট বার্তা আসে।',
                      'A short message tells you when someone bids on your lot, outbids you, buys your lot, picks it up or delivers it.',
                    ),
                    t(
                      'চালক লোকেশন জানালে রাস্তার দাগে ট্রাক এগোয়, সাথে বাকি দূরত্ব ও সময়। সংযোগ কাটলে অ্যাপ নিজে আবার যুক্ত হয় আর ততক্ষণ নিজেই খোঁজ নেয়।',
                      'When the driver shares location, the truck moves along the route with the distance and time left. If the connection drops, the app reconnects by itself and keeps checking meanwhile.',
                    ),
                  ],
                ),
                _Section(
                  icon: Icons.cloud_off_rounded,
                  title: t('অফলাইন মোড', 'Offline mode'),
                  body: [
                    t(
                      'আমি → অফলাইন এজ মোড: উত্তর আসে গ্রামের কিয়স্কের নিজস্ব মডেল থেকে, ইন্টারনেট ছাড়া; অনলাইন কণ্ঠ বন্ধ থাকে।',
                      'Me → Offline edge mode: answers come from the village kiosk\'s own model, without the internet; the online voice stays off.',
                    ),
                    t(
                      'বাজারের জন্য নোডের সাথে সংযোগ লাগে: গ্রামের কিয়স্ক (একই নেটওয়ার্কে) বা অনলাইন সার্ভার। আমি → সার্ভার থেকে বদলানো যায়।',
                      'The market needs the node: the village kiosk on the same network, or the online server. Change it under Me → Server.',
                    ),
                  ],
                ),
                SectionTitle(
                  t('প্রায়ই যা জানতে চান', 'Questions people ask'),
                  top: 28,
                ),
                AppCard(
                  padding: EdgeInsets.zero,
                  child: Column(
                    children: [
                      for (final (q, a) in [
                        (
                          t('আসল টাকা কি লেনদেন হয়?', 'Does real money move?'),
                          t(
                            'না। এই ডেমোতে ব্যাংকের এসক্রো অনুকরণ করা; কোনো আসল টাকা নড়ে না।',
                            'No. In this demo the bank\'s escrow is simulated: no real money moves.',
                          ),
                        ),
                        (
                          t(
                            'গ্রেড A, B, C মানে কী?',
                            'What do grades A, B and C mean?',
                          ),
                          t(
                            'A: রপ্তানি ও সুপারশপ; B: সাধারণ পাইকারি; C: প্রক্রিয়াজাত শিল্প।',
                            'A: export and supermarkets; B: standard wholesale; C: agro-processing.',
                          ),
                        ),
                        (
                          t('আমার লোকেশন কে দেখে?', 'Who sees my location?'),
                          t(
                            'চালক নিজে চালু করলে শুধু সেই বিক্রির ক্রেতা ও কৃষক, আর ব্যাংক, বিচারক ও অ্যাডমিন ডেস্ক, প্রায় ১ কিমি পর্যন্ত আনুমানিক অবস্থান দেখেন। বন্ধ করলে, পৌঁছে দিলে বা স্ক্রিন ছাড়লে থেমে যায়।',
                            'Only when the driver turns it on: the buyer and the farmer of that sale, and the bank, judge and admin desks, as a rough position (to about 1 km). It stops when switched off, on delivery, or when the driver leaves the screen.',
                          ),
                        ),
                        (
                          t(
                            'অ্যাকাউন্ট আইডি ভুলে গেছি।',
                            'I forgot my account ID.',
                          ),
                          t(
                            'লগইন থাকা অবস্থায় আমি ট্যাবে দেখা যায়। লগআউট হয়ে গেলে নোডের অ্যাডমিনের সাহায্য নিন।',
                            'The Me tab shows it while you are logged in. If you are logged out, ask the node\'s admin for help.',
                          ),
                        ),
                        (
                          t(
                            'ইন্টারনেট ছাড়া চলে?',
                            'Does it work without internet?',
                          ),
                          t(
                            'প্রশ্ন-উত্তর অফলাইন এজ মোডে চলে; বাজারের জন্য গ্রামের কিয়স্ক বা অনলাইন সার্ভার লাগে।',
                            'Questions work in Offline edge mode; the market needs the village kiosk or the online server.',
                          ),
                        ),
                      ])
                        ExpansionTile(
                          shape: const Border(),
                          collapsedShape: const Border(),
                          minTileHeight: 56,
                          leading: Icon(
                            Icons.help_outline_rounded,
                            color: Tone.green.fg(context),
                          ),
                          title: Text(
                            q,
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontSize: 16,
                            ),
                          ),
                          childrenPadding: const EdgeInsets.fromLTRB(
                            16,
                            0,
                            16,
                            14,
                          ),
                          expandedCrossAxisAlignment: CrossAxisAlignment.start,
                          children: [Text(a, style: theme.textTheme.bodyLarge)],
                        ),
                    ],
                  ),
                ),
                SectionTitle(
                  t('ওয়েবসাইটে আরও', 'More on the website'),
                  top: 28,
                ),
                AppCard(
                  padding: EdgeInsets.zero,
                  child: Column(
                    children: [
                      for (final (icon, label, path) in [
                        (
                          Icons.language_rounded,
                          t('ওয়েবসাইট', 'Website'),
                          '/',
                        ),
                        (
                          Icons.description_outlined,
                          t('ডকুমেন্টেশন', 'Documentation'),
                          '/docs',
                        ),
                        (
                          Icons.menu_book_rounded,
                          t('ব্যবহারের নির্দেশিকা', 'User guide'),
                          '/guide',
                        ),
                        (
                          Icons.groups_rounded,
                          t('টিম হিট ওয়েভ', 'Team Heat Wave'),
                          '/team/',
                        ),
                      ])
                        ListTile(
                          minTileHeight: 56,
                          leading: Icon(icon, color: Tone.green.fg(context)),
                          title: Text(label, style: theme.textTheme.bodyLarge),
                          trailing: const Icon(Icons.open_in_new_rounded),
                          onTap: () => openWeb(context, path),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A section heading: an icon in a tinted circle beside the title.
class _Heading extends StatelessWidget {
  const _Heading({required this.icon, required this.title, this.top = 28});
  final IconData icon;
  final String title;
  final double top;

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.only(top: top, bottom: 12),
    child: Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: Tone.green.bg(context),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, size: 24, color: Tone.green.fg(context)),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Semantics(
            header: true,
            child: Text(title, style: Theme.of(context).textTheme.titleLarge),
          ),
        ),
      ],
    ),
  );
}

/// One role's steps, numbered.
class _Role extends StatelessWidget {
  const _Role({required this.icon, required this.title, required this.steps});
  final IconData icon;
  final String title;
  final List<String> steps;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Heading(icon: icon, title: title),
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < steps.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 7),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 30,
                        height: 30,
                        alignment: Alignment.center,
                        decoration: const BoxDecoration(
                          color: Brand.green,
                          shape: BoxShape.circle,
                        ),
                        child: Text(
                          digits(i + 1),
                          style: theme.textTheme.labelLarge?.copyWith(
                            color: Colors.white,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(steps[i], style: theme.textTheme.bodyLarge),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.icon,
    required this.title,
    required this.body,
    this.top = 28,
  });
  final IconData icon;
  final String title;
  final List<String> body;
  final double top;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _Heading(icon: icon, title: title, top: top),
      AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final p in body)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Text(p, style: Theme.of(context).textTheme.bodyLarge),
              ),
          ],
        ),
      ),
    ],
  );
}
