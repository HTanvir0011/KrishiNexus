import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'login.dart' show roleIcon;

/// Accounts that open at once, and those an admin approves first (POST /auth/register answers PENDING_REVIEW).
const openRoles = ['farmer', 'buyer', 'driver'];
const reviewedRoles = ['coop', 'storage', 'bank'];

// The node's rules (backend auth.Registration), checked on the phone first. Bangla digits count as digits.
String _plain(String s) => asciiDigits(s).replaceAll(RegExp(r'[\s-]'), '');

String? nameError(String v) => v.trim().length < 2 || v.trim().length > 60
    ? t('২ থেকে ৬০ অক্ষরে নাম লিখুন', 'Enter a name of 2 to 60 letters')
    : null;

String? mobileError(String v) => isBdMobile(bdMobile(v))
    ? null
    : t(
        '০১ দিয়ে শুরু ১১ অঙ্কের নম্বর দিন',
        'Enter an 11-digit number starting 01',
      );

String? nidError(String v) =>
    RegExp(r'^(\d{10}|\d{13}|\d{17})$').hasMatch(_plain(v))
    ? null
    : t(
        'জাতীয় পরিচয়পত্রের ১০, ১৩ বা ১৭ অঙ্ক দিন',
        'Enter the 10, 13 or 17 digits of the national ID',
      );

String? upazilaError(String v) => v.trim().length > 40
    ? t('৪০ অক্ষরের মধ্যে লিখুন', 'Keep it within 40 letters')
    : null;

String? organizationError(String role, String v) {
  final s = v.trim();
  if (s.length > 80) {
    return t('৮০ অক্ষরের মধ্যে লিখুন', 'Keep it within 80 letters');
  }
  if (reviewedRoles.contains(role) && s.length < 2) {
    return t('প্রতিষ্ঠানের নাম দিন', 'Enter the organization\'s name');
  }
  return null;
}

String? passwordError(String v) => v.length < 8
    ? t('কমপক্ষে ৮ অক্ষর দিন', 'Use at least 8 characters')
    : v.length > 128
    ? t('১২৮ অক্ষরের বেশি নয়', 'Use at most 128 characters')
    : null;

String? confirmError(String password, String v) => v == password
    ? null
    : t('দুটি পাসওয়ার্ড মেলেনি', 'The two passwords do not match');

/// The POST /auth/register body from the form as typed: digits in ASCII, mobile numbers in their 01XXXXXXXXX form.
Map<String, dynamic> registerBody({
  required String role,
  required String name,
  required String phone,
  required String nid,
  required String district,
  String upazila = '',
  String organization = '',
  required String walletProvider,
  required String walletNumber,
  required String password,
}) => {
  'name': name.trim(),
  'role': role,
  'district': district,
  if (upazila.trim().isNotEmpty) 'upazila': upazila.trim(),
  if (organization.trim().isNotEmpty) 'organization': organization.trim(),
  'phone': bdMobile(phone),
  'nid': _plain(nid),
  'wallet_provider': walletProvider,
  'wallet_number': bdMobile(walletNumber),
  'password': password,
  'consent': true,
};

/// Create an account: farmers, buyers and drivers sign in at once; co-op, cold-storage and bank accounts wait for an
/// admin. The national ID, phone and wallet go to the node, which keeps them only as hashes and shows masked digits.
class SignUpScreen extends StatefulWidget {
  const SignUpScreen({super.key});

  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _nid = TextEditingController();
  final _upazila = TextEditingController();
  final _org = TextEditingController();
  final _walletNumber = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  String _role = 'farmer';
  String? _district;
  String _wallet = 'bKash';
  bool _busy = false;
  User? _pending;

  bool get _reviewed => reviewedRoles.contains(_role);

  @override
  void dispose() {
    for (final c in [
      _name,
      _phone,
      _nid,
      _upazila,
      _org,
      _walletNumber,
      _password,
      _confirm,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    FocusManager.instance.primaryFocus?.unfocus();
    if (!_form.currentState!.validate()) {
      snack(
        context,
        t('লাল চিহ্নিত ঘরগুলো ঠিক করুন।', 'Fix the fields marked in red.'),
        icon: Icons.error_outline_rounded,
        tone: Tone.amber,
      );
      return;
    }
    setState(() => _busy = true);
    try {
      final res = mapOf(
        await Api.post(
          '/auth/register',
          registerBody(
            role: _role,
            name: _name.text,
            phone: _phone.text,
            nid: _nid.text,
            district: _district!,
            upazila: _upazila.text,
            organization: _reviewed || _role == 'buyer' ? _org.text : '',
            walletProvider: _wallet,
            walletNumber: _walletNumber.text,
            password: _password.text,
          ),
        ),
      );
      if (!mounted) return;
      final session = mapOf(res?['session']);
      final user = mapOf(res?['user']);
      if (res?['status'] == 'ACTIVE' && session != null) {
        final messenger = ScaffoldMessenger.of(context);
        Navigator.of(context).popUntil((route) => route.isFirst);
        await app.signIn(session);
        final id = app.user?.id ?? '';
        messenger.showSnackBar(
          SnackBar(
            duration: const Duration(seconds: 8),
            content: Text(
              t(
                'স্বাগতম! আপনার অ্যাকাউন্ট আইডি $id; পাসওয়ার্ডের সাথে এটি দিয়ে লগইন করবেন (আমি ট্যাবে দেখা যায়)।',
                'Welcome! Your account ID is $id: you log in with it and your password (the Me tab shows it).',
              ),
            ),
          ),
        );
      } else if (user != null) {
        setState(() => _pending = User(user));
      }
    } on ApiError catch (e) {
      if (!mounted) return;
      final message = switch (e.status) {
        429 => t(
          'এই নোডে এখন নতুন অ্যাকাউন্ট খোলা বন্ধ। পরে চেষ্টা করুন।',
          'Sign-ups are paused on this node. Try again later.',
        ),
        409 => t(
          e.message.contains('phone')
              ? 'এই মোবাইল নম্বরে আগেই একটি অ্যাকাউন্ট আছে।'
              : 'এই জাতীয় পরিচয়পত্রে আগেই একটি অ্যাকাউন্ট আছে।',
          e.message,
        ),
        _ => friendlyError(e),
      };
      snack(
        context,
        message,
        icon: Icons.error_outline_rounded,
        tone: Tone.rose,
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        _pending == null
            ? t('নতুন অ্যাকাউন্ট', 'Create an account')
            : t('অনুমোদনের অপেক্ষায়', 'Waiting for approval'),
      ),
    ),
    body: SafeArea(
      child: _pending == null
          ? _formView(context)
          : _pendingView(context, _pending!),
    ),
  );

  Widget _roles(String label, List<String> roles) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        label,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
      const SizedBox(height: 8),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final r in roles)
            ChoiceChip(
              showCheckmark:
                  false, // the fill marks the choice; a check over the icon muddies it
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14),
              avatar: Icon(roleIcon(r), size: 22),
              label: Text(
                roleName(r),
                style: Theme.of(context).textTheme.labelLarge,
              ),
              selected: _role == r,
              onSelected: (_) => setState(() => _role = r),
            ),
        ],
      ),
    ],
  );

  /// A numbered step heading: the form is four short groups, one after the other.
  Widget _step(int n, String title, {double top = 32}) {
    final theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(top: top, bottom: 14),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: const BoxDecoration(
              color: Brand.green,
              shape: BoxShape.circle,
            ),
            child: Text(
              digits(n),
              style: theme.textTheme.labelLarge?.copyWith(color: Colors.white),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Semantics(
              header: true,
              child: Text(title, style: theme.textTheme.titleLarge),
            ),
          ),
        ],
      ),
    );
  }

  /// A lock and a plain promise next to a field that holds private numbers.
  Widget _privacy(String text) => Padding(
    padding: const EdgeInsets.only(top: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          Icons.lock_outline_rounded,
          size: 20,
          color: Tone.green.fg(context),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ],
    ),
  );

  // A Column, not a lazy list: every field stays built, so the form checks all of them.
  Widget _formView(BuildContext context) {
    final theme = Theme.of(context);
    const gap = SizedBox(height: 12);
    return Form(
      key: _form,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _step(1, t('আপনি কে?', 'Who are you?'), top: 8),
            _roles(t('এখনই চালু হয়', 'Opens at once'), openRoles),
            const SizedBox(height: 14),
            _roles(
              t(
                'অ্যাডমিন অনুমোদন দিলে চালু হয়',
                'Opens after an admin approves it',
              ),
              reviewedRoles,
            ),
            if (_reviewed) ...[
              const SizedBox(height: 12),
              AppCard(
                tone: Tone.amber,
                padding: const EdgeInsets.all(12),
                child: Text(
                  t(
                    'সমবায়, হিমাগার ও ব্যাংকের অ্যাকাউন্ট একজন অ্যাডমিন যাচাই করে চালু করেন। ততক্ষণ লগইন করা যাবে না।',
                    'An admin checks co-op, cold-storage and bank accounts before they open. Until then the account cannot log in.',
                  ),
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ],
            _step(2, t('আপনার তথ্য', 'About you')),
            TextFormField(
              controller: _name,
              textCapitalization: TextCapitalization.words,
              autofillHints: const [AutofillHints.name],
              decoration: InputDecoration(
                labelText: t('পুরো নাম', 'Full name'),
              ),
              validator: (v) => nameError(v ?? ''),
            ),
            gap,
            TextFormField(
              controller: _phone,
              keyboardType: TextInputType.phone,
              autofillHints: const [AutofillHints.telephoneNumber],
              decoration: InputDecoration(
                labelText: t('মোবাইল নম্বর', 'Mobile number'),
                hintText: '01XXXXXXXXX',
              ),
              validator: (v) => mobileError(v ?? ''),
            ),
            gap,
            TextFormField(
              controller: _nid,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: t(
                  'জাতীয় পরিচয়পত্র (এনআইডি) নম্বর',
                  'National ID (NID) number',
                ),
                helperText: t('১০, ১৩ বা ১৭ অঙ্ক', '10, 13 or 17 digits'),
              ),
              validator: (v) => nidError(v ?? ''),
            ),
            _privacy(
              t(
                'আপনার এনআইডি নিরাপদ। শুধু যাচাইয়ের জন্য; অ্যাপে শুধু শেষ কয়েকটি অঙ্ক দেখা যাবে।',
                'Your NID is safe. It is only used to check who you are; the app shows just the last digits.',
              ),
            ),
            gap,
            DropdownButtonFormField<String>(
              initialValue: _district,
              isExpanded: true,
              menuMaxHeight: 420,
              decoration: InputDecoration(labelText: t('জেলা', 'District')),
              items: [
                for (final (en, bn) in districts)
                  DropdownMenuItem(value: en, child: Text(t(bn, en))),
              ],
              onChanged: (v) => setState(() => _district = v),
              validator: (v) => v == null
                  ? t('আপনার জেলা বাছুন', 'Choose your district')
                  : null,
            ),
            gap,
            TextFormField(
              controller: _upazila,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(
                labelText: t('উপজেলা (ঐচ্ছিক)', 'Upazila (optional)'),
              ),
              validator: (v) => upazilaError(v ?? ''),
            ),
            if (_reviewed || _role == 'buyer') ...[
              gap,
              TextFormField(
                controller: _org,
                textCapitalization: TextCapitalization.words,
                decoration: InputDecoration(
                  labelText: _reviewed
                      ? t('প্রতিষ্ঠান', 'Organization')
                      : t('প্রতিষ্ঠান (ঐচ্ছিক)', 'Organization (optional)'),
                  hintText: t(
                    'যেমন: শিবগঞ্জ ইউনিয়ন সমবায়',
                    'e.g. Shibganj Union Co-op',
                  ),
                ),
                validator: (v) => organizationError(_role, v ?? ''),
              ),
            ],
            _step(3, t('টাকা পাওয়ার ওয়ালেট', 'Payout wallet')),
            Text(
              t(
                'বিক্রির টাকা শুধু এই ওয়ালেটেই যাবে।',
                'Money from your sales goes only to this wallet.',
              ),
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              showSelectedIcon: false,
              style: const ButtonStyle(
                minimumSize: WidgetStatePropertyAll(Size(0, 52)),
              ),
              segments: [
                for (final w in walletProviders)
                  ButtonSegment(value: w, label: Text(w)),
              ],
              selected: {_wallet},
              onSelectionChanged: (s) => setState(() => _wallet = s.first),
            ),
            gap,
            TextFormField(
              controller: _walletNumber,
              keyboardType: TextInputType.phone,
              decoration: InputDecoration(
                labelText: t('$_wallet নম্বর', '$_wallet number'),
                hintText: '01XXXXXXXXX',
              ),
              validator: (v) => mobileError(v ?? ''),
            ),
            _privacy(
              t(
                'ওয়ালেট নম্বর নিরাপদ থাকে। অ্যাপে শুধু শেষ কয়েকটি অঙ্ক দেখা যাবে।',
                'Your wallet number stays safe. The app shows just the last digits.',
              ),
            ),
            _step(4, t('পাসওয়ার্ড', 'Password')),
            TextFormField(
              controller: _password,
              obscureText: true,
              autofillHints: const [AutofillHints.newPassword],
              decoration: InputDecoration(
                labelText: t('পাসওয়ার্ড', 'Password'),
                helperText: t('কমপক্ষে ৮ অক্ষর', 'At least 8 characters'),
              ),
              validator: (v) => passwordError(v ?? ''),
            ),
            gap,
            TextFormField(
              controller: _confirm,
              obscureText: true,
              decoration: InputDecoration(
                labelText: t('আবার পাসওয়ার্ড', 'Password again'),
              ),
              validator: (v) => confirmError(_password.text, v ?? ''),
            ),
            const SizedBox(height: 16),
            FormField<bool>(
              initialValue: false,
              validator: (v) => v == true
                  ? null
                  : t('চালিয়ে যেতে সম্মতি দিন', 'Tick the box to continue'),
              builder: (field) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CheckboxListTile(
                    value: field.value ?? false,
                    onChanged: field.didChange,
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                      t(
                        'আমি রাজি: কৃষিনেক্সাস আমার জাতীয় পরিচয়পত্র, ফোন ও ওয়ালেটের নম্বর শুধু হ্যাশ করে রাখবে (এক দিকে বদলানো, ফেরত পড়া যায় না)। '
                            'অ্যাপে শুধু শেষ কয়েকটি অঙ্ক দেখা যাবে; পুরো নম্বর আর কখনো দেখানো হবে না। আমার নাম, জেলা ও ভূমিকা লেনদেনের অপর পক্ষ দেখবেন।',
                        'I agree: KrishiNexus keeps my national ID, phone and wallet numbers only as hashes (scrambled one way, never read back). '
                            'The app shows only their last digits and never the full numbers again. The people I trade with see my name, district and role.',
                      ),
                      style: theme.textTheme.bodyMedium,
                    ),
                  ),
                  if (field.hasError)
                    Padding(
                      padding: const EdgeInsets.only(left: 12),
                      child: Text(
                        field.errorText!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.error,
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _busy ? null : _submit,
              icon: _busy
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.person_add_alt_1_rounded),
              label: Text(t('অ্যাকাউন্ট খুলুন', 'Create the account')),
            ),
          ],
        ),
      ),
    );
  }

  Widget _pendingView(BuildContext context, User user) {
    final theme = Theme.of(context);
    final kyc = user.kyc;
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 40),
      children: [
        Icon(
          Icons.hourglass_top_rounded,
          size: 56,
          color: Tone.amber.fg(context),
        ),
        const SizedBox(height: 16),
        Text(
          t(
            'আপনার অ্যাকাউন্ট অনুমোদনের অপেক্ষায়',
            'Your account is waiting for approval',
          ),
          textAlign: TextAlign.center,
          style: theme.textTheme.headlineSmall,
        ),
        const SizedBox(height: 10),
        Text(
          t(
            'সমবায়, হিমাগার ও ব্যাংকের অ্যাকাউন্ট একজন অ্যাডমিন যাচাই করে চালু করেন। চালু হলে নিচের অ্যাকাউন্ট আইডি ও আপনার পাসওয়ার্ড দিয়ে লগইন করুন; তার আগে লগইন করলে অপেক্ষার কথাই বলবে।',
            'An admin checks co-op, cold-storage and bank accounts before they open. Once yours is approved, log in with the account ID below and your password; until then, logging in says it is still waiting.',
          ),
          textAlign: TextAlign.center,
          style: theme.textTheme.bodyLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 20),
        AppCard(
          child: Column(
            children: [
              InfoRow(
                t('অ্যাকাউন্ট আইডি', 'Account ID'),
                user.id,
                mono: true,
                strong: true,
              ),
              InfoRow(t('ভূমিকা', 'Role'), roleName(user.role)),
              if (user.title.isNotEmpty)
                InfoRow(t('পরিচয়', 'Listed as'), user.title),
              if (kyc != null) ...[
                InfoRow(t('ফোন', 'Phone'), digits(kyc.phoneMasked)),
                InfoRow(
                  t('জাতীয় পরিচয়পত্র', 'National ID'),
                  '…${digits(kyc.nidLast4)}',
                ),
                InfoRow(
                  t('টাকা পাওয়ার ওয়ালেট', 'Payout wallet'),
                  '${kyc.walletProvider} ${digits(kyc.walletMasked)}',
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 20),
        FilledButton.icon(
          onPressed: () => Navigator.of(context).pop(),
          icon: const Icon(Icons.login_rounded),
          label: Text(t('লগইন পাতায় ফিরুন', 'Back to the login screen')),
        ),
      ],
    );
  }
}
