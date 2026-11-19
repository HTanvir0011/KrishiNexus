import 'package:flutter_test/flutter_test.dart';
import 'package:krishinexus/core/format.dart';
import 'package:krishinexus/core/models.dart';
import 'package:krishinexus/core/state.dart';

void main() {
  test('grouped uses the South Asian grouping the website uses', () {
    expect(grouped(0), '0');
    expect(grouped(999), '999');
    expect(grouped(1000), '1,000');
    expect(grouped(123456), '1,23,456');
    expect(grouped(12345678.5, decimals: 2), '1,23,45,678.50');
    expect(grouped(-2500), '-2,500');
  });

  test('money and digits follow the app language', () {
    app.lang = 'en';
    expect(money(12345), 'Tk 12,345');
    expect(perKg(22.5), 'Tk 22.50/kg');
    app.lang = 'bn';
    expect(money(12345), '৳১২,৩৪৫');
    expect(kg(500), '৫০০ কেজি');
    app.lang = 'en';
  });

  test('a lot ranks active bids and finds the accepted one', () {
    final lot = Lot({
      'lot_id': 'LOT-1',
      'crop': 'Cardinal Potato',
      'grade': 'A',
      'weight_kg': 500,
      'floor_tk_per_kg': 15,
      'status': 'SOLD',
      'accepted_bid_id': 'MB-B',
      'bids': [
        {'bid_id': 'MB-A', 'buyer_id': 'BUY-1', 'price_tk_per_kg': 21, 'status': 'ACTIVE'},
        {'bid_id': 'MB-B', 'buyer_id': 'BUY-2', 'price_tk_per_kg': 24.5, 'status': 'ACCEPTED'},
        {'bid_id': 'MB-C', 'buyer_id': 'BUY-3', 'price_tk_per_kg': 23, 'status': 'ACTIVE'},
      ],
      'escrow': {'escrow_id': 'ESC-1', 'amount_tk': 12250, 'status': 'HELD'},
      'delivery': null,
      'disputes': [],
    });
    expect(lot.activeBids.map((b) => b.id), ['MB-C', 'MB-A']);
    expect(lot.best?.id, 'MB-C');
    expect(lot.acceptedBid?.buyerId, 'BUY-2');
    expect(lot.escrow?.amount, 12250);
    expect(lot.delivery, isNull);
  });

  test('a voice answer unpacks the agents\' plan', () {
    final r = VoiceResult({
      'status': 'COMPLETED',
      'spoken_response_bn': 'হিমাগারে রাখুন',
      'transcription': {'raw_transcript': 'x', 'scrubbed_transcript': 'x', 'dialect': 'Rangpuri', 'pii_entities': ['PHONE'], 'entities': {'intent': 'sell_or_store', 'quantity_kg': 400}},
      'orchestration': {
        'graph_path': ['pii_guardrail', 'supervisor'],
        'state': {
          'crop': 'Cardinal Potato',
          'quantity_kg': 400,
          'farmer_offer_tk_per_kg': 12,
          'cold_storage_arbitrage_plan': {
            'decision': 'STORE_AND_FINANCE',
            'distress_sale_blocked': true,
            'circuit_breaker': {'storage_branch_value_bdt': 9000, 'spot_branch_value_bdt': 4800},
          },
        },
      },
    });
    expect(r.storeFirst, isTrue);
    expect(r.saleBlocked, isTrue);
    expect(r.storeValue, 9000);
    expect(r.spotValue, 4800);
    expect(r.offer, 12);
    expect(r.piiHidden, 1);
    expect(r.quantityKg, 400);
    expect(r.graphPath, hasLength(2));
  });
}
