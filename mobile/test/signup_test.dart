import 'package:flutter_test/flutter_test.dart';
import 'package:krishinexus/core/format.dart';
import 'package:krishinexus/core/state.dart';
import 'package:krishinexus/screens/signup.dart';

void main() {
  setUp(() => app.lang = 'en');

  test('numbers typed with Bangla digits, spaces, dashes or +88 are read as the node expects', () {
    expect(asciiDigits('০১৭১২৩৪৫৬৭৮'), '01712345678');
    expect(bdMobile('+880 1712-345678'), '01712345678');
    expect(bdMobile('০১৭১১-২২৩ ৩৪৪'), '01711223344');
    expect(mobileError('০১৭১২৩৪৫৬৭৮'), isNull);
    expect(mobileError('01212345678'), isNotNull); // 012 is not a mobile operator
    expect(mobileError('0171234567'), isNotNull); // ten digits
  });

  test('a national ID has 10, 13 or 17 digits', () {
    expect(nidError('1234567890'), isNull);
    expect(nidError('১২৩৪ ৫৬৭ ৮৯০'), isNull);
    expect(nidError('1234567890123'), isNull);
    expect(nidError('12345678901234567'), isNull);
    expect(nidError('12345678901'), isNotNull);
    expect(nidError('12345abcde'), isNotNull);
  });

  test('name, organization, upazila and password rules match the node', () {
    expect(nameError(' A '), isNotNull);
    expect(nameError('Rahim Mia'), isNull);
    expect(nameError('x' * 61), isNotNull);
    expect(organizationError('coop', ' '), isNotNull); // co-op, cold storage and bank name their organization
    expect(organizationError('bank', 'Krishi Bank, Bogura'), isNull);
    expect(organizationError('farmer', ''), isNull);
    expect(organizationError('buyer', 'x' * 81), isNotNull);
    expect(upazilaError('x' * 41), isNotNull);
    expect(passwordError('1234567'), isNotNull);
    expect(passwordError('12345678'), isNull);
    expect(passwordError('x' * 129), isNotNull);
    expect(confirmError('krishi-2026', 'krishi-2026'), isNull);
    expect(confirmError('krishi-2026', 'krishi2026'), isNotNull);
  });

  test('the register body is normalized and sends only the contract\'s fields', () {
    expect(
      registerBody(
        role: 'farmer',
        name: '  Rahim Mia ',
        phone: '০১৭১২-৩৪৫৬৭৮',
        nid: '১২৩৪ ৫৬৭ ৮৯০',
        district: 'Rangpur',
        upazila: ' ',
        walletProvider: 'Rocket',
        walletNumber: '+8801812345678',
        password: 'krishi-2026',
      ),
      {
        'name': 'Rahim Mia',
        'role': 'farmer',
        'district': 'Rangpur',
        'phone': '01712345678',
        'nid': '1234567890',
        'wallet_provider': 'Rocket',
        'wallet_number': '01812345678',
        'password': 'krishi-2026',
        'consent': true,
      },
    );
    expect(districts, hasLength(64));
    expect(walletProviders, ['bKash', 'Nagad', 'Rocket', 'Upay']);
  });
}
