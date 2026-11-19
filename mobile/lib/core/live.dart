import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api.dart';
import 'format.dart';
import 'models.dart';
import 'state.dart';
import 'theme.dart';

/// One Server-Sent Event: its id, its type ("message" unless the stream names one) and its data.
class SseEvent {
  const SseEvent(this.id, this.event, this.data);
  final String id;
  final String event;
  final String data;
}

/// Reads an event stream line by line (WHATWG HTML, server-sent events): a blank line ends an event that has data;
/// comments such as ": ping" and unknown fields are skipped; "retry" sets [retry]. The id carries over to later events.
class SseParser {
  String _id = '';
  String _event = '';
  final _data = StringBuffer();
  bool _hasData = false;
  int? retry;

  SseEvent? line(String line) {
    if (line.startsWith('﻿')) line = line.substring(1);
    if (line.isEmpty) {
      final event = _hasData ? SseEvent(_id, _event.isEmpty ? 'message' : _event, _data.toString()) : null;
      _event = '';
      _data.clear();
      _hasData = false;
      return event;
    }
    if (line.startsWith(':')) return null;
    final colon = line.indexOf(':');
    final field = colon < 0 ? line : line.substring(0, colon);
    var value = colon < 0 ? '' : line.substring(colon + 1);
    if (value.startsWith(' ')) value = value.substring(1);
    switch (field) {
      case 'event':
        _event = value;
      case 'data':
        if (_hasData) _data.write('\n');
        _data.write(value);
        _hasData = true;
      case 'id':
        if (!value.contains('\u0000')) _id = value;
      case 'retry':
        if (RegExp(r'^\d+$').hasMatch(value)) retry = int.parse(value);
    }
    return null;
  }
}

/// Live market events. Phones stream GET /market/stream (server-sent events) and reconnect with backoff and
/// Last-Event-ID; the browser build, and a phone the node turns away when its feed is full (503), poll
/// GET /market/events every 5 s. [connected] drives the live dot; screens refresh on [events].
class MarketStream extends ChangeNotifier {
  final _events = StreamController<MarketEvent>.broadcast();
  Stream<MarketEvent> get events => _events.stream;

  /// Sent when events were missed (more than the node replays, or it restarted): every screen reloads.
  static final resync = MarketEvent(const {'kind': 'resync'});

  bool connected = false;
  bool _on = false;
  int _gen = 0; // bumped by stop(), so a connection from before it stays quiet
  int? _seq; // the last event's number: sent back to catch up on what was missed
  String _base = '';
  int _failures = 0;
  int _retryMs = 5000;
  http.Client? _client;
  Timer? _timer;
  Timer? _watchdog;

  void start() {
    if (_on) return;
    _on = true;
    if (_base != Api.base) {
      _base = Api.base;
      _seq = null; // another node numbers its own events
    }
    kIsWeb ? _poll(++_gen) : _stream(++_gen);
  }

  void stop() {
    _on = false;
    _gen++;
    _timer?.cancel();
    _watchdog?.cancel();
    _client?.close();
    _client = null;
    _set(false);
  }

  void _set(bool value) {
    if (connected == value) return;
    connected = value;
    notifyListeners();
  }

  /// Events are numbered one by one: a jump means some were lost, so everything reloads first.
  @visibleForTesting
  void take(MarketEvent e) {
    final last = _seq;
    if (last != null && e.seq <= last) return; // already seen
    if (last != null && e.seq > last + 1) _events.add(resync);
    _seq = e.seq;
    _events.add(e);
  }

  Future<void> _stream(int gen) async {
    final client = _client = http.Client();
    final parser = SseParser();
    var full = false;
    try {
      final request = http.Request('GET', Uri.parse('${Api.base}/market/stream'))
        ..headers.addAll({'Accept': 'text/event-stream', 'Cache-Control': 'no-cache', 'Last-Event-ID': ?_seq?.toString()});
      final response = await client.send(request).timeout(const Duration(seconds: 20));
      full = response.statusCode == 503;
      if (response.statusCode != 200) throw ApiError(response.statusCode, 'The live feed answered ${response.statusCode}.');
      _failures = 0;
      _set(true);
      _guard(client);
      await for (final line in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
        if (gen != _gen) break;
        _guard(client);
        final event = parser.line(line);
        _retryMs = parser.retry ?? _retryMs;
        final json = event == null || event.event != 'market' ? null : _decode(event.data);
        if (json != null) take(MarketEvent(json));
      }
    } catch (_) {
      // Refused, dropped, or silent for too long: try again below.
    } finally {
      if (gen == _gen) _watchdog?.cancel(); // a newer connection's watchdog stays
      client.close();
    }
    if (gen != _gen) return;
    // The node's feed is full: poll its event list instead until the app next starts the feed.
    if (full) return _poll(gen);
    _set(false);
    _failures++;
    final wait = math.min(_retryMs << math.min(_failures - 1, 4), 60000);
    _timer = Timer(Duration(milliseconds: wait), () => _stream(gen));
  }

  // The node pings every 15 s: three missed pings mean a dead connection the network did not report.
  void _guard(http.Client client) {
    _watchdog?.cancel();
    _watchdog = Timer(const Duration(seconds: 45), client.close);
  }

  Future<void> _poll(int gen) async {
    try {
      final page = mapOf(await Api.get('/market/events?since=${_seq ?? 0}', timeout: const Duration(seconds: 10)));
      if (gen != _gen) return;
      if (page == null) throw const FormatException('Not an event page');
      final latest = numOf(page['seq']).toInt();
      final events = mapsOf(page['events']).map(MarketEvent.new).toList();
      if (_seq == null) {
        _seq = latest; // the first page is history the screens have just loaded: it only sets where to read from
      } else if (latest < _seq!) {
        _seq = latest; // the node counts from somewhere else now (restarted): reload everything
        _events.add(resync);
      } else {
        events.forEach(take);
      }
      _set(true);
    } catch (_) {
      if (gen != _gen) return;
      _set(false);
    }
    if (gen == _gen) _timer = Timer(const Duration(seconds: 5), () => _poll(gen));
  }

  static Map<String, dynamic>? _decode(String data) {
    try {
      return mapOf(jsonDecode(data));
    } on FormatException {
      return null;
    }
  }
}

final live = MarketStream();

class Notice {
  const Notice(this.text, this.icon, this.tone);
  final String text;
  final IconData icon;
  final Tone tone;
}

/// What the signed-in account should hear about, from how lots changed between two looks at GET /market/lots:
/// bids on a farmer's lot, a buyer outbid or winning, a job for drivers, pickup, delivery and payment, disputes.
/// What the user has just done on this phone is skipped (they saw it happen).
List<Notice> notices(User me, Map<String, Lot> before, List<Lot> after) {
  final out = <Notice>[];
  void add(String bn, String en, IconData icon, Tone tone) => out.add(Notice(t(bn, en), icon, tone));
  final justNow = DateTime.now().difference(Api.lastWriteAt) < const Duration(seconds: 20);
  for (final lot in after) {
    final was = before[lot.id];
    final d = lot.delivery;
    final crop = cropName(lot.crop);
    if (me.role == 'driver' && d != null && d.status == 'AWAITING_DRIVER' && was?.delivery?.status != 'AWAITING_DRIVER' &&
        lot.status != 'CANCELLED' && lot.escrow?.status != 'REFUNDED') {
      add('নতুন ডেলিভারির কাজ: $crop, ${kg(lot.kg)}, ${d.origin} থেকে ${d.destination}',
          'New delivery job: $crop, ${kg(lot.kg)}, ${d.origin} to ${d.destination}', Icons.local_shipping_rounded, Tone.sky);
    }
    if (was == null) continue; // new since the last look: nothing of this account's has changed on it yet
    final mine = lot.farmerId == me.id;
    final won = lot.acceptedBid?.buyerId == me.id;
    final bidOn = was.activeBids.any((b) => b.buyerId == me.id);
    final mineHere = justNow && Api.lastWrite.contains(lot.id);
    if (me.role == 'farmer' && mine && lot.status == 'OPEN') {
      final fresh = lot.activeBids.where((b) => !was.bids.any((x) => x.id == b.id)).firstOrNull;
      if (fresh != null) {
        add('নতুন দর: আপনার $crop লটে ${perKg(fresh.price)}, ${fresh.buyerName}', 'New bid on your $crop lot: ${perKg(fresh.price)} from ${fresh.buyerName}',
            Icons.gavel_rounded, Tone.green);
      }
    }
    if (me.role == 'buyer' && lot.status == 'OPEN' && was.best?.buyerId == me.id && lot.best != null && lot.best!.buyerId != me.id) {
      add('আপনাকে ছাড়িয়ে গেছে: $crop লটে এখন ${perKg(lot.best!.price)}', 'Outbid on the $crop lot: the highest bid is now ${perKg(lot.best!.price)}',
          Icons.trending_up_rounded, Tone.rose);
    }
    if (was.status == 'OPEN' && lot.status == 'SOLD') {
      if (mine && !mineHere) {
        add('বিক্রি হয়েছে: আপনার $crop লট, টাকা ব্যাংকে জমা', 'Sold: your $crop lot; the bank holds the payment', Icons.lock_rounded, Tone.green);
      } else if (me.role == 'buyer' && won) {
        add('আপনি পেয়েছেন: $crop লট ${perKg(lot.acceptedBid!.price)} দরে, টাকা ব্যাংকে জমা',
            'You won the $crop lot at ${perKg(lot.acceptedBid!.price)}; the payment is held in escrow', Icons.check_circle_rounded, Tone.green);
      } else if (me.role == 'buyer' && bidOn) {
        add('$crop লট অন্য ক্রেতার কাছে বিক্রি হয়েছে', 'The $crop lot was sold to another buyer', Icons.info_outline_rounded, Tone.slate);
      }
    }
    if (me.role == 'buyer' && bidOn && was.status == 'OPEN' && lot.status == 'CANCELLED') {
      add('কৃষক $crop লটটি বাতিল করেছেন', 'The farmer cancelled the $crop lot', Icons.block_rounded, Tone.slate);
    }
    if ((me.role == 'farmer' && mine) || (me.role == 'buyer' && won)) {
      final now = d?.status, then = was.delivery?.status;
      if (now == 'PICKED_UP' && then != 'PICKED_UP') {
        add('মাল তোলা হয়েছে: $crop এখন পথে', 'Picked up: the $crop is on the road', Icons.local_shipping_rounded, Tone.sky);
      }
      if (now == 'DELIVERED' && then != 'DELIVERED' && mine) {
        add('পৌঁছেছে: $crop; টাকা আপনার ${lot.escrow?.wallet ?? ''} ওয়ালেটে ছাড়া হয়েছে',
            'Delivered: the $crop; your payment is released to ${lot.escrow?.wallet ?? 'your wallet'}', Icons.payments_rounded, Tone.green);
      } else if (now == 'DELIVERED' && then != 'DELIVERED') {
        add('পৌঁছেছে: আপনার $crop', 'Delivered: your $crop has arrived', Icons.where_to_vote_rounded, Tone.green);
      }
    }
    final party = mine || won || d?.driverId == me.id;
    for (final x in lot.disputes) {
      final old = was.disputes.where((y) => y.id == x.id).firstOrNull;
      if (old == null && x.raisedBy != me.id && (party || me.role == 'bank')) {
        add('$crop লটে নতুন অভিযোগ: ${disputeKind(x.kind)}', 'New dispute on the $crop lot: ${disputeKind(x.kind)}', Icons.report_rounded, Tone.amber);
      }
      if (old != null && old.status == 'OPEN' && x.status != 'OPEN' && party && me.role != 'bank') {
        add('ব্যাংকের সিদ্ধান্ত, $crop লট: ${resolutionName(x.resolution ?? '')}', 'The bank decided on the $crop lot: ${resolutionName(x.resolution ?? '')}',
            Icons.gavel_rounded, Tone.violet);
      }
    }
  }
  return out;
}
