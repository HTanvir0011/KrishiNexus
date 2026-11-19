/// Thin, typed views over the node's JSON (shapes in frontend/src/api/client.ts and the backend's Pydantic models).
library;

double numOf(Object? v) => v is num ? v.toDouble() : 0;
double? numOrNull(Object? v) => v is num ? v.toDouble() : null;
Map<String, dynamic>? mapOf(Object? v) => v is Map ? v.cast<String, dynamic>() : null;
List<Map<String, dynamic>> mapsOf(Object? v) =>
    v is List ? v.whereType<Map>().map((m) => m.cast<String, dynamic>()).toList() : const [];
List<String> stringsOf(Object? v) => v is List ? v.whereType<String>().toList() : const [];

class User {
  User(this.j);
  final Map<String, dynamic> j;
  String get id => j['user_id'] as String;
  String get name => j['name'] as String? ?? '';
  String get role => j['role'] as String? ?? '';
  String get district => j['district'] as String? ?? '';
  String get title => j['title'] as String? ?? '';
  bool get active => j['active'] as bool? ?? true;
}

class Box {
  Box(this.j);
  final Map<String, dynamic> j;
  List<double> get rect => (j['box'] as List).map(numOf).toList(); // [x, y, w, h] in frame pixels
  String get label => j['class_label'] as String? ?? 'uniform_A';
  double get confidence => numOf(j['confidence']);
  double get diameterMm => numOf(j['diameter_mm']);
  double get defectPct => numOf(j['defect_area_pct']);
}

class GradeResult {
  GradeResult(this.j);
  final Map<String, dynamic> j;
  String get crop => j['crop'] as String;
  String? get district => j['district'] as String?;
  String get source => j['source'] as String? ?? '';
  bool get fromPhoto => source == 'uploaded_image';
  String get backend => j['inference_backend'] as String? ?? '';
  String get modelVersion => j['inspector_model_version'] as String? ?? '';
  double get frameW => numOf((j['frame_size'] as List?)?.first);
  double get frameH => numOf((j['frame_size'] as List?)?.last);
  List<Box> get boxes => mapsOf(j['bounding_boxes']).map(Box.new).toList();
  Map<String, dynamic> get metrics => mapOf(j['metrics']) ?? const {};
  String get grade => j['grade_letter'] as String? ?? 'C';
  String get gradeLabel => j['assigned_grade'] as String? ?? '';
  List<String> get reasons => stringsOf(j['grading_reasons']);
  List<String> get warnings => stringsOf(j['warnings']);
  double get premiumPct => numOf(j['price_premium_pct']);
  String get premiumBasis => j['premium_basis'] as String? ?? '';
  Map<String, dynamic> get certificate => mapOf(j['digital_certificate']) ?? const {};
  String get certId => certificate['cert_id'] as String? ?? '';
  String get issuedAt => certificate['issued_at'] as String? ?? '';
  String get signature => certificate['verification_hash'] as String? ?? '';
  double get latencyMs => numOf(j['latency_ms']);
}

class Bid {
  Bid(this.j);
  final Map<String, dynamic> j;
  String get id => j['bid_id'] as String;
  String get buyerId => j['buyer_id'] as String? ?? '';
  String get buyerName => j['buyer_name'] as String? ?? '';
  String get buyerDistrict => j['buyer_district'] as String? ?? '';
  double get price => numOf(j['price_tk_per_kg']);
  String get note => j['note'] as String? ?? '';
  String get placedAt => j['placed_at'] as String? ?? '';
  String get status => j['status'] as String? ?? 'ACTIVE';
}

class DeliveryEvent {
  DeliveryEvent(this.j);
  final Map<String, dynamic> j;
  String get at => j['at'] as String? ?? '';
  String get kind => j['kind'] as String? ?? '';
  String get detail => j['detail'] as String? ?? '';
}

class Delivery {
  Delivery(this.j);
  final Map<String, dynamic> j;
  String get status => j['status'] as String? ?? 'AWAITING_DRIVER';
  String get origin => j['origin_district'] as String? ?? '';
  String get destination => j['destination_district'] as String? ?? '';
  double get km => numOf(j['distance_km']);
  double get etaHours => numOf(j['eta_hours']);
  String? get driverId => j['driver_id'] as String?;
  String? get driverName => j['driver_name'] as String?;
  double? get lastTemp => numOrNull(j['last_temp_c']);
  double? get lastRh => numOrNull(j['last_rh_pct']);
  double? get shelfLifeHours => numOrNull(j['shelf_life_hours']);
  bool get atRisk => j['at_risk'] as bool? ?? false;
  List<DeliveryEvent> get events => mapsOf(j['events']).map(DeliveryEvent.new).toList();
}

class Dispute {
  Dispute(this.j);
  final Map<String, dynamic> j;
  String get id => j['dispute_id'] as String;
  String get lotId => j['lot_id'] as String? ?? '';
  String get raisedBy => j['raised_by'] as String? ?? '';
  String get raisedByName => j['raised_by_name'] as String? ?? '';
  String get raisedByRole => j['raised_by_role'] as String? ?? '';
  String get kind => j['kind'] as String? ?? 'OTHER';
  String get note => j['note'] as String? ?? '';
  String get status => j['status'] as String? ?? 'OPEN';
  String get openedAt => j['opened_at'] as String? ?? '';
  String? get resolution => j['resolution'] as String?;
  String get resolutionNote => j['resolution_note'] as String? ?? '';
}

class Escrow {
  Escrow(this.j);
  final Map<String, dynamic> j;
  String get id => j['escrow_id'] as String? ?? '';
  double get amount => numOf(j['amount_tk']);
  String get wallet => j['wallet'] as String? ?? '';
  String get walletMasked => j['wallet_masked'] as String? ?? '';
  String get status => j['status'] as String? ?? 'HELD';
  String get lockedAt => j['locked_at'] as String? ?? '';
}

class Lot {
  Lot(this.j);
  final Map<String, dynamic> j;
  String get id => j['lot_id'] as String;
  String get farmerId => j['farmer_id'] as String? ?? '';
  String get farmerName => j['farmer_name'] as String? ?? '';
  String get crop => j['crop'] as String? ?? '';
  String get grade => j['grade'] as String? ?? 'B';
  double get kg => numOf(j['weight_kg']);
  String get district => j['district'] as String? ?? '';
  String get upazila => j['upazila'] as String? ?? '';
  double? get asking => numOrNull(j['asking_price_tk_per_kg']);
  double get floor => numOf(j['floor_tk_per_kg']);
  String? get certId => j['certificate_id'] as String?;
  String get note => j['note'] as String? ?? '';
  String get listedAt => j['listed_at'] as String? ?? '';
  String get status => j['status'] as String? ?? 'OPEN';
  List<Bid> get bids => mapsOf(j['bids']).map(Bid.new).toList();
  List<Bid> get activeBids => bids.where((b) => b.status == 'ACTIVE').toList()..sort((a, b) => b.price.compareTo(a.price));
  Bid? get best => activeBids.firstOrNull;
  String? get acceptedBidId => j['accepted_bid_id'] as String?;
  Bid? get acceptedBid => bids.where((b) => b.id == acceptedBidId).firstOrNull;
  Escrow? get escrow => mapOf(j['escrow']) == null ? null : Escrow(mapOf(j['escrow'])!);
  Delivery? get delivery => mapOf(j['delivery']) == null ? null : Delivery(mapOf(j['delivery'])!);
  List<Dispute> get disputes => mapsOf(j['disputes']).map(Dispute.new).toList();
  int get openDisputes => disputes.where((d) => d.status == 'OPEN').length;
}

/// POST /edge/voice-interact's answer, with the agents' plan (orchestration.state) unpacked.
class VoiceResult {
  VoiceResult(this.j);
  final Map<String, dynamic> j;
  String get status => j['status'] as String? ?? 'COMPLETED';
  bool get needsClarification => status == 'NEEDS_CLARIFICATION';
  Map<String, dynamic> get transcription => mapOf(j['transcription']) ?? const {};
  String get rawTranscript => transcription['raw_transcript'] as String? ?? '';
  String get scrubbedTranscript => transcription['scrubbed_transcript'] as String? ?? '';
  String get dialect => transcription['dialect'] as String? ?? '';
  int get piiHidden => (transcription['pii_entities'] as List?)?.length ?? 0;
  Map<String, dynamic> get entities => mapOf(transcription['entities']) ?? const {};
  String get intent => entities['intent'] as String? ?? '';
  double? get quantityKg => numOrNull(entities['quantity_kg']);
  String get spoken => j['spoken_response_bn'] as String? ?? '';
  String? get followUp => j['follow_up_question_bn'] as String?;
  Map<String, dynamic>? get orchestration => mapOf(j['orchestration']);
  Map<String, dynamic>? get state => mapOf(orchestration?['state']);
  List<String> get graphPath => stringsOf(orchestration?['graph_path']);
  double get latencyMs => numOf(orchestration?['latency_ms']);

  String get sessionId => state?['session_id'] as String? ?? '';
  String get farmerId => state?['farmer_id'] as String? ?? '';
  String get crop => state?['crop'] as String? ?? '';
  String get district => state?['district'] as String? ?? '';
  String get upazila => state?['upazila'] as String? ?? '';
  double get qty => numOf(state?['quantity_kg']);
  Map<String, dynamic>? get syndicate => mapOf(state?['syndicate_bypass_plan']);
  Map<String, dynamic>? get cold => mapOf(state?['cold_storage_arbitrage_plan']);
  Map<String, dynamic>? get breaker => mapOf(cold?['circuit_breaker']);
  Map<String, dynamic>? get credit => mapOf(state?['climate_credit_report']);
  Map<String, dynamic>? get qualityCert => mapOf(state?['optical_grade_cert']);
  Map<String, dynamic>? get pool => mapOf(syndicate?['pool']);
  double? get offer => numOrNull(state?['farmer_offer_tk_per_kg']) ?? numOrNull(syndicate?['farmer_offer_tk_per_kg']);
  bool get storeFirst => (cold?['decision'] as String? ?? '').startsWith('STORE');
  bool get saleBlocked => cold?['distress_sale_blocked'] as bool? ?? false;
  double? get pooledValue => numOrNull(syndicate?['lot_value_b2b_tk']);
  double? get storeValue => numOrNull(breaker?['storage_branch_value_bdt']);
  double? get spotValue => numOrNull(breaker?['spot_branch_value_bdt']) ?? (offer == null ? null : offer! * qty);
  bool get floodAlert => (credit?['flood_applicable'] as bool? ?? false) && credit?['flood_breach_probability_pct'] != null;
  bool get loanEligible => credit?['loan_eligible'] as bool? ?? false;
  String get marketGrade => qualityCert?['market_grade'] as String? ?? 'B';
}
