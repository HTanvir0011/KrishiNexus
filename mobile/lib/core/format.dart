import 'state.dart';

const _bnDigits = '০১২৩৪৫৬৭৮৯';

/// Bangla numerals when the app speaks Bangla.
String digits(Object value) {
  final s = '$value';
  if (app.lang != 'bn') return s;
  return s.replaceAllMapped(RegExp('[0-9]'), (m) => _bnDigits[int.parse(m[0]!)]);
}

/// 1,23,456.50: the South Asian grouping the website uses (en-IN).
String grouped(num value, {int decimals = 0}) {
  final negative = value < 0;
  final fixed = value.abs().toStringAsFixed(decimals);
  final parts = fixed.split('.');
  var whole = parts[0];
  if (whole.length > 3) {
    final last3 = whole.substring(whole.length - 3);
    var rest = whole.substring(0, whole.length - 3);
    final groups = <String>[];
    while (rest.length > 2) {
      groups.insert(0, rest.substring(rest.length - 2));
      rest = rest.substring(0, rest.length - 2);
    }
    if (rest.isNotEmpty) groups.insert(0, rest);
    whole = '${groups.join(',')},$last3';
  }
  return '${negative ? '-' : ''}$whole${parts.length > 1 ? '.${parts[1]}' : ''}';
}

String money(num? value, {int decimals = 0}) {
  if (value == null || value.isNaN) return '–';
  final n = grouped(value, decimals: decimals);
  return app.lang == 'bn' ? '৳${digits(n)}' : 'Tk $n';
}

String perKg(num? value) => value == null ? '–' : '${money(value, decimals: 2)}/${t('কেজি', 'kg')}';

String kg(num value) => '${digits(grouped(value))} ${t('কেজি', 'kg')}';

String pct(num? value, {int decimals = 1}) => value == null ? '–' : '${digits(value.toStringAsFixed(decimals))}%';

String num1(num value, {int decimals = 0}) => digits(grouped(value, decimals: decimals));

const _crops = {
  'Cardinal Potato': ('কার্ডিনাল আলু', 'Cardinal potato'),
  'Diamant Potato': ('ডায়মন্ড আলু', 'Diamant potato'),
  'Green Chili': ('কাঁচা মরিচ', 'Green chili'),
  'Brinjal': ('বেগুন', 'Brinjal'),
  'Boro Rice': ('বোরো ধান', 'Boro rice'),
  'Mango': ('আম', 'Mango'),
  'Banana': ('কলা', 'Banana'),
};

String cropName(String crop) {
  final names = _crops[crop];
  return names == null ? crop : t(names.$1, names.$2);
}

/// Crops a farmer can list on the direct market (backend schemas Crop) and those the camera grades.
const marketCrops = ['Cardinal Potato', 'Diamant Potato', 'Green Chili', 'Brinjal', 'Boro Rice'];
const scanCrops = ['Cardinal Potato', 'Diamant Potato', 'Green Chili', 'Brinjal'];

String gradeName(String letter) => switch (letter) {
      'A' => t('রপ্তানি ও সুপারশপ', 'Export and supermarket'),
      'B' => t('সাধারণ পাইকারি', 'Standard wholesale'),
      _ => t('প্রক্রিয়াজাত শিল্প', 'Agro-processing'),
    };

String roleName(String role) => switch (role) {
      'farmer' => t('কৃষক', 'Farmer'),
      'buyer' => t('ক্রেতা', 'Buyer'),
      'driver' => t('ট্রাক চালক', 'Truck driver'),
      'coop' => t('সমবায়', 'Co-op'),
      'storage' => t('হিমাগার', 'Cold storage'),
      'bank' => t('ব্যাংক', 'Bank'),
      'judge' => t('বিচারক', 'Judge'),
      'admin' => t('অ্যাডমিন', 'Admin'),
      _ => role,
    };

String lotStatus(String status) => switch (status) {
      'OPEN' => t('দর চলছে', 'Open for bids'),
      'SOLD' => t('বিক্রি হয়েছে', 'Sold'),
      'IN_TRANSIT' => t('পথে', 'On the road'),
      'DELIVERED' => t('পৌঁছেছে', 'Delivered'),
      'CANCELLED' => t('বাতিল', 'Cancelled'),
      _ => status,
    };

String deliveryStatus(String status) => switch (status) {
      'AWAITING_DRIVER' => t('চালকের অপেক্ষায়', 'Waiting for a driver'),
      'ASSIGNED' => t('চালক নিয়েছেন', 'Driver assigned'),
      'PICKED_UP' => t('মাল তোলা হয়েছে', 'Picked up'),
      'DELIVERED' => t('পৌঁছে দেওয়া হয়েছে', 'Delivered'),
      _ => status,
    };

String escrowStatus(String status) => switch (status) {
      'HELD' => t('ব্যাংকে জমা আছে', 'Held by the bank'),
      'RELEASED' => t('কৃষককে দেওয়া হয়েছে', 'Paid to the farmer'),
      'REFUNDED' => t('ক্রেতাকে ফেরত', 'Refunded to the buyer'),
      _ => status,
    };

const disputeKinds = ['PAYMENT_NOT_RECEIVED', 'WRONG_AMOUNT', 'DELIVERY_PROBLEM', 'QUALITY_MISMATCH', 'OTHER'];

String disputeKind(String kind) => switch (kind) {
      'PAYMENT_NOT_RECEIVED' => t('টাকা পাইনি', 'Payment not received'),
      'WRONG_AMOUNT' => t('ভুল পরিমাণ টাকা', 'Wrong amount'),
      'DELIVERY_PROBLEM' => t('ডেলিভারিতে সমস্যা', 'Delivery problem'),
      'QUALITY_MISMATCH' => t('মান মেলেনি', 'Quality does not match'),
      _ => t('অন্য সমস্যা', 'Other problem'),
    };

String resolutionName(String resolution) => switch (resolution) {
      'RELEASE_TO_FARMER' => t('কৃষককে টাকা দিন', 'Release to the farmer'),
      'REFUND_TO_BUYER' => t('ক্রেতাকে ফেরত দিন', 'Refund the buyer'),
      'KEEP_HOLDING' => t('আটকে রাখুন', 'Keep holding'),
      _ => t('কোনো পরিবর্তন নয়', 'No change'),
    };

/// "5 min ago" from the node's ISO timestamps (Asia/Dhaka offsets included).
String ago(String iso) {
  final at = DateTime.tryParse(iso);
  if (at == null) return '';
  final d = DateTime.now().difference(at);
  if (d.inSeconds < 60) return t('এইমাত্র', 'just now');
  if (d.inMinutes < 60) return t('${digits(d.inMinutes)} মিনিট আগে', '${d.inMinutes} min ago');
  if (d.inHours < 24) return t('${digits(d.inHours)} ঘণ্টা আগে', '${d.inHours} h ago');
  return t('${digits(d.inDays)} দিন আগে', '${d.inDays} d ago');
}

String clock(String iso) {
  final at = DateTime.tryParse(iso)?.toLocal();
  if (at == null) return '';
  return digits('${at.hour.toString().padLeft(2, '0')}:${at.minute.toString().padLeft(2, '0')}');
}

/// The certificate's id without its date and hash middle, for small spaces.
String shortId(String id, {int keep = 10}) => id.length > keep * 2 ? '${id.substring(0, keep)}…${id.substring(id.length - 6)}' : id;
