import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:krishinexus/core/api.dart';
import 'package:krishinexus/core/live.dart';
import 'package:krishinexus/core/models.dart';
import 'package:krishinexus/core/state.dart';

/// Every event a stream's text holds, read line by line as the app reads the socket.
(List<SseEvent>, SseParser) parse(String stream) {
  final parser = SseParser();
  return ([for (final line in const LineSplitter().convert(stream)) ?parser.line(line)], parser);
}

Map<String, dynamic> lot(String id, {String farmer = 'FARM-1', String status = 'OPEN', List<Map<String, dynamic>> bids = const [], Map<String, dynamic>? delivery, List<Map<String, dynamic>> disputes = const []}) => {
      'lot_id': id,
      'farmer_id': farmer,
      'farmer_name': 'Rahim Mia',
      'crop': 'Cardinal Potato',
      'weight_kg': 400,
      'status': status,
      'bids': bids,
      'accepted_bid_id': bids.where((b) => b['status'] == 'ACCEPTED').map((b) => b['bid_id']).firstOrNull,
      'delivery': delivery,
      'disputes': disputes,
    };

Map<String, dynamic> bid(String id, String buyer, double price, {String status = 'ACTIVE'}) =>
    {'bid_id': id, 'buyer_id': buyer, 'buyer_name': 'Buyer $buyer', 'price_tk_per_kg': price, 'status': status};

void main() {
  setUp(() => app.lang = 'en');

  test('the node\'s stream: retry, ids, named events and pings', () {
    final (events, parser) = parse('retry: 5000\n\n'
        'id: 1731990000101\nevent: market\ndata: {"seq": 1731990000101, "kind": "bid_placed", "lot_id": "LOT-1"}\n\n'
        ': ping\n\n'
        'id: 1731990000102\nevent: market\ndata: {"seq": 1731990000102, "kind": "lot_sold", "lot_id": "LOT-1"}\n\n');
    expect(parser.retry, 5000);
    expect(events.map((e) => e.id), ['1731990000101', '1731990000102']);
    expect(events.every((e) => e.event == 'market'), isTrue);
    final first = MarketEvent((jsonDecode(events.first.data) as Map).cast<String, dynamic>());
    expect((first.seq, first.kind, first.lotId, first.quiet), (1731990000101, 'bid_placed', 'LOT-1', false));
  });

  test('server-sent event edge cases follow the spec', () {
    final (events, parser) = parse('﻿data:first\r\ndata:  second\r\n\r\n' // CRLF, no space after the colon, one space kept
        'event: market\nunknown: x\n\n' // no data: nothing to dispatch, and the type resets
        'id: 7\ndata\n\n' // a bare field name is an empty value
        'data: after\n\n' // the last id carries over
        'retry: soon\n\n'); // not digits: ignored
    expect(events.map((e) => (e.id, e.event, e.data)), [('', 'message', 'first\n second'), ('7', 'message', ''), ('7', 'message', 'after')]);
    expect(parser.retry, isNull);
  });

  test('a jump in event numbers (missed events) asks every screen to reload; repeats are dropped', () async {
    final stream = MarketStream();
    final seen = <String>[];
    stream.events.listen((e) => seen.add('${e.kind}${e.seq > 0 ? ' ${e.seq}' : ''}'));
    for (final seq in [1795089801222, 1795089801223, 1795089801230, 1795089801230]) {
      stream.take(MarketEvent({'seq': seq, 'kind': 'bid_placed', 'lot_id': 'LOT-1'}));
    }
    await Future<void>.delayed(Duration.zero);
    expect(seen, ['bid_placed 1795089801222', 'bid_placed 1795089801223', 'resync', 'bid_placed 1795089801230']);
    expect(MarketStream.resync.lotId, isNull); // so lot screens take it as theirs too
  });

  test('a delivery places the truck by the distance it has covered', () {
    Delivery at(double? left) => Delivery({'status': 'PICKED_UP', 'distance_km': 200, 'position': left == null ? null : {'km_to_destination': left}});
    expect(at(150).progress, 0.25);
    expect(at(260).progress, 0.0); // still driving to the farm
    expect(at(null).progress, isNull);
  });

  test('banners: a bid on my lot, outbid, a new job, my own report and my own sale stay quiet', () {
    final farmer = User({'user_id': 'FARM-1', 'role': 'farmer'});
    final buyer = User({'user_id': 'BUY-1', 'role': 'buyer'});
    final driver = User({'user_id': 'DRV-1', 'role': 'driver'});
    final before = {
      'LOT-1': Lot(lot('LOT-1', bids: [bid('B1', 'BUY-1', 20)])),
      'LOT-2': Lot(lot('LOT-2', bids: [bid('B2', 'BUY-2', 18)])),
    };
    final after = [
      Lot(lot('LOT-1', bids: [bid('B1', 'BUY-1', 20), bid('B3', 'BUY-2', 21.5)])),
      Lot(lot('LOT-2', status: 'SOLD', bids: [bid('B2', 'BUY-2', 18, status: 'ACCEPTED')],
          delivery: {'status': 'AWAITING_DRIVER', 'origin_district': 'Rangpur', 'destination_district': 'Dhaka'})),
    ];
    Api.lastWrite = '';
    expect(notices(farmer, before, after).map((n) => n.text), [
      'New bid on your Cardinal potato lot: Tk 21.50/kg from Buyer BUY-2',
      'Sold: your Cardinal potato lot; the bank holds the payment',
    ]);
    expect(notices(buyer, before, after).single.text, 'Outbid on the Cardinal potato lot: the highest bid is now Tk 21.50/kg');
    expect(notices(driver, before, after).single.text, 'New delivery job: Cardinal potato, 400 kg, Rangpur to Dhaka');

    // The farmer accepted that bid on this phone a moment ago: no banner for it.
    Api.lastWrite = '/market/lots/LOT-2/accept';
    Api.lastWriteAt = DateTime.now();
    expect(notices(farmer, before, after).map((n) => n.text), isNot(contains(startsWith('Sold'))));

    final reported = [Lot(lot('LOT-1', disputes: [{'dispute_id': 'D1', 'raised_by': 'FARM-1', 'kind': 'OTHER', 'status': 'OPEN'}]))];
    expect(notices(farmer, {'LOT-1': Lot(lot('LOT-1'))}, reported), isEmpty);
    expect(notices(User({'user_id': 'BANK-1', 'role': 'bank'}), {'LOT-1': Lot(lot('LOT-1'))}, reported).single.text,
        'New dispute on the Cardinal potato lot: Other problem');
  });
}
