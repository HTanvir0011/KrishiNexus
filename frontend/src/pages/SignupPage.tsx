import { ArrowRight, Eye, EyeOff, Hourglass, Landmark, LogOut, ShieldCheck, ShoppingCart, Snowflake, Sprout, Truck, UserPlus, Warehouse, type LucideIcon } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { api, ApiError, WALLET_PROVIDERS, type AuthUser, type FieldError, type RegisterBody, type SignupRole, type Wallet } from "../api/client";
import { Wordmark } from "../components/Navbar";
import { Badge, Button, Segmented, Spinner } from "../components/ui";
import { cn, kycLine, latinDigits } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { homeOf, ROLE_LABEL } from "../lib/roles";
import { Link, navigate } from "../lib/router";
import { logout, pushAlert, startSession, useAppState } from "../state/store";

// Farmers, buyers and drivers start at once; co-ops, cold stores and banks act for many people, so an admin approves them.
const ROLES: { role: SignupRole; icon: LucideIcon; review: boolean }[] = [
  { role: "farmer", icon: Sprout, review: false },
  { role: "buyer", icon: ShoppingCart, review: false },
  { role: "driver", icon: Truck, review: false },
  { role: "coop", icon: Warehouse, review: true },
  { role: "storage", icon: Snowflake, review: true },
  { role: "bank", icon: Landmark, review: true },
];
const FIELD = "min-h-11 w-full rounded-lg bg-white px-3 text-[15px] text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-700 focus:outline-none aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-rose-600";
const MOBILE = /^01[3-9]\d{8}$/;

type Field = "role" | "name" | "district" | "upazila" | "organization" | "phone" | "nid" | "wallet_number" | "password" | "confirm" | "consent";

const COPY = {
  en: {
    title: "Create an account",
    lede: "Farmers, buyers and truck drivers can start at once. Co-ops, cold stores and banks start after an admin's approval.",
    who: "Who are you?",
    about: "About you",
    ids: "Phone, ID and payouts",
    secret: "Password",
    roleHint: {
      farmer: "Ask, grade your crop, sell directly and get paid on delivery.",
      buyer: "Bid on graded lots from farmers; your payment waits in escrow.",
      driver: "Take delivery jobs; the farmer is paid when you deliver.",
      coop: "Pool members' harvests into full trucks.",
      storage: "Run your cold store's chambers, quota and bookings.",
      bank: "Hold payments, settle disputes and give credit.",
    },
    instant: "Active at once",
    review: "Needs an admin's approval",
    name: "Full name", district: "District", upazila: "Upazila (optional)", organization: "Organisation",
    orgHint: "The co-op, cold store or bank you act for.",
    phone: "Mobile number", phoneHint: "11 digits, starting 01. Bangla digits are fine.",
    nid: "National ID (NID) number", nidHint: "10, 13 or 17 digits. Kept only as a hash; shown later as …1234.",
    wallet: "Payout wallet", walletNo: "Wallet number", walletHint: "Payouts go only to this wallet.",
    password: "Password", passwordHint: "At least 8 characters.", confirm: "Type the password again",
    show: "Show password", hide: "Hide password",
    consent: "I agree that KrishiNexus keeps my national ID, phone and wallet numbers only as a one-way hash and a masked form (such as bKash 017••••5678 and NID …1234). They are used to stop duplicate accounts and to send payouts only to my registered wallet, and they are never shown in full again, not even to an admin.",
    submit: "Create account",
    have: "Already have an account?", login: "Log in",
    err: {
      role: "Choose who you are.",
      name: "Write your name (2 to 60 letters).",
      district: "Write your district (2 to 40 letters).",
      upazila: "Keep the upazila under 40 letters.",
      organization: "Write the organisation's name (2 to 80 letters).",
      phone: "Write an 11-digit mobile number starting 013 to 019.",
      nid: "A national ID has 10, 13 or 17 digits.",
      wallet_number: "Write the wallet's 11-digit number, starting 013 to 019.",
      password: "Use 8 to 128 characters.",
      confirm: "The two passwords do not match.",
      consent: "Tick the box to agree; the account cannot be made without it.",
    } satisfies Record<Field, string>,
    fix: "Some answers need a look; they are marked below.",
    duplicate: "An account with this national ID or phone number already exists. Log in instead, or ask an admin.",
    paused: "Sign-ups are paused for a while. Please try again later.",
    down: "The server is not reachable. Check the connection and try again.",
    created: "Account created",
    createdDetail: (id: string) => `Your account ID is ${id}. Log in with it and your password.`,
    pendingTitle: "Your account is waiting for approval",
    pendingText: (role: string) => `An admin checks ${role} accounts before first use. You can log in as soon as it is approved.`,
    accountId: "Account ID", keep: "Keep it: you log in with it and your password.",
    payouts: "Payouts and ID",
    home: "Back to the overview",
    signedIn: (name: string) => `You are logged in as ${name}. Log out first to create another account.`,
    workspace: "Go to my workspace", logout: "Log out",
  },
  bn: {
    title: "অ্যাকাউন্ট খুলুন",
    lede: "কৃষক, ক্রেতা ও ট্রাকচালক সাথে সাথে শুরু করতে পারেন। সমবায়, হিমাগার ও ব্যাংক শুরু করেন অ্যাডমিনের অনুমোদনের পর।",
    who: "আপনি কে?",
    about: "আপনার পরিচয়",
    ids: "ফোন, পরিচয়পত্র ও টাকা পাওয়া",
    secret: "পাসওয়ার্ড",
    roleHint: {
      farmer: "প্রশ্ন করুন, ফসল গ্রেড করুন, সরাসরি বেচুন, ডেলিভারিতে টাকা পান।",
      buyer: "কৃষকের গ্রেড করা লটে দর দিন; আপনার টাকা এসক্রোতে থাকে।",
      driver: "ডেলিভারির কাজ নিন; পৌঁছে দিলে কৃষক টাকা পান।",
      coop: "সদস্যদের ফসল মিলিয়ে পূর্ণ ট্রাক পাঠান।",
      storage: "হিমাগারের চেম্বার, কোটা ও বুকিং চালান।",
      bank: "টাকা আটকে রাখা, অভিযোগের মীমাংসা ও ঋণ।",
    },
    instant: "সাথে সাথে চালু",
    review: "অ্যাডমিনের অনুমোদন লাগে",
    name: "পুরো নাম", district: "জেলা", upazila: "উপজেলা (ঐচ্ছিক)", organization: "প্রতিষ্ঠান",
    orgHint: "যে সমবায়, হিমাগার বা ব্যাংকের হয়ে কাজ করবেন।",
    phone: "মোবাইল নম্বর", phoneHint: "০১ দিয়ে শুরু ১১ অঙ্ক। বাংলা অঙ্কেও লেখা যায়।",
    nid: "জাতীয় পরিচয়পত্র (এনআইডি) নম্বর", nidHint: "১০, ১৩ বা ১৭ অঙ্ক। শুধু হ্যাশ করে রাখা হয়; পরে দেখাবে …১২৩৪ রূপে।",
    wallet: "টাকা পাওয়ার ওয়ালেট", walletNo: "ওয়ালেট নম্বর", walletHint: "টাকা যাবে শুধু এই ওয়ালেটে।",
    password: "পাসওয়ার্ড", passwordHint: "অন্তত ৮ অক্ষর।", confirm: "পাসওয়ার্ড আবার লিখুন",
    show: "পাসওয়ার্ড দেখুন", hide: "পাসওয়ার্ড লুকান",
    consent: "আমি রাজি যে কৃষিনেক্সাস আমার জাতীয় পরিচয়পত্র, ফোন ও ওয়ালেট নম্বর রাখবে শুধু এক-মুখী হ্যাশ আর ঢাকা রূপে (যেমন bKash 017••••5678 ও NID …1234)। এগুলো দিয়ে একই মানুষের দুটি অ্যাকাউন্ট ঠেকানো হয় আর টাকা শুধু আমার নিবন্ধিত ওয়ালেটে পাঠানো হয়; পুরো নম্বর আর কখনো দেখানো হয় না, অ্যাডমিনকেও না।",
    submit: "অ্যাকাউন্ট খুলুন",
    have: "আগেই অ্যাকাউন্ট আছে?", login: "লগইন",
    err: {
      role: "আপনি কে, বেছে নিন।",
      name: "আপনার নাম লিখুন (২ থেকে ৬০ অক্ষর)।",
      district: "জেলার নাম লিখুন (২ থেকে ৪০ অক্ষর)।",
      upazila: "উপজেলা ৪০ অক্ষরের মধ্যে লিখুন।",
      organization: "প্রতিষ্ঠানের নাম লিখুন (২ থেকে ৮০ অক্ষর)।",
      phone: "০১৩ থেকে ০১৯ দিয়ে শুরু ১১ অঙ্কের মোবাইল নম্বর লিখুন।",
      nid: "জাতীয় পরিচয়পত্রে ১০, ১৩ বা ১৭ অঙ্ক থাকে।",
      wallet_number: "ওয়ালেটের ১১ অঙ্কের নম্বর লিখুন, ০১৩ থেকে ০১৯ দিয়ে শুরু।",
      password: "৮ থেকে ১২৮ অক্ষর দিন।",
      confirm: "দুটি পাসওয়ার্ড মেলেনি।",
      consent: "রাজি থাকলে টিক দিন; না হলে অ্যাকাউন্ট খোলা যাবে না।",
    } satisfies Record<Field, string>,
    fix: "কিছু উত্তর ঠিক করতে হবে; নিচে চিহ্নিত আছে।",
    duplicate: "এই জাতীয় পরিচয়পত্র বা ফোন নম্বরে আগেই একটি অ্যাকাউন্ট আছে। লগইন করুন, বা অ্যাডমিনকে জানান।",
    paused: "নতুন নিবন্ধন কিছুক্ষণের জন্য বন্ধ। পরে আবার চেষ্টা করুন।",
    down: "সার্ভারে পৌঁছানো যাচ্ছে না। সংযোগ দেখে আবার চেষ্টা করুন।",
    created: "অ্যাকাউন্ট খোলা হয়েছে",
    createdDetail: (id: string) => `আপনার অ্যাকাউন্ট আইডি ${id}। এটি আর পাসওয়ার্ড দিয়ে লগইন করবেন।`,
    pendingTitle: "আপনার অ্যাকাউন্ট অনুমোদনের অপেক্ষায়",
    pendingText: (role: string) => `প্রথম ব্যবহারের আগে একজন অ্যাডমিন ${role} অ্যাকাউন্ট যাচাই করেন। অনুমোদন হলেই লগইন করতে পারবেন।`,
    accountId: "অ্যাকাউন্ট আইডি", keep: "এটি রেখে দিন: এটি আর পাসওয়ার্ড দিয়ে লগইন করবেন।",
    payouts: "টাকা পাওয়া ও পরিচয়",
    home: "সারসংক্ষেপে ফিরুন",
    signedIn: (name: string) => `আপনি ${name} হিসেবে লগইন করে আছেন। আরেকটি অ্যাকাউন্ট খুলতে আগে লগআউট করুন।`,
    workspace: "আমার কাজের জায়গা", logout: "লগআউট",
  },
};

/** Digits only: Bangla digits become 0-9, spaces and dashes go, and a +88 country code before 01 is dropped. */
const digits = (value: string) => latinDigits(value).replace(/[\s-]/g, "").replace(/^\+?88(?=01)/, "");

const EMPTY = { name: "", district: "", upazila: "", organization: "", phone: "", nid: "", wallet_number: "", password: "", confirm: "" };

/** Self sign-up (POST /auth/register). The national ID, phone and wallet number live only in this form's memory. */
export function SignupPage() {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  const user = useAppState((s) => s.user);
  const [role, setRole] = useState<SignupRole | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [provider, setProvider] = useState<Wallet>("bKash");
  const [consent, setConsent] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [tried, setTried] = useState(false);
  const [serverErrors, setServerErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<AuthUser | null>(null);

  const needsOrg = role === "coop" || role === "storage" || role === "bank";
  const set = (field: keyof typeof EMPTY, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
    setServerErrors((e) => ({ ...e, [field]: undefined }));
  };

  const local: Partial<Record<Field, string>> = {};
  if (!role) local.role = c.err.role;
  if (form.name.trim().length < 2 || form.name.trim().length > 60) local.name = c.err.name;
  if (form.district.trim().length < 2 || form.district.trim().length > 40) local.district = c.err.district;
  if (form.upazila.trim().length > 40) local.upazila = c.err.upazila;
  if (needsOrg && (form.organization.trim().length < 2 || form.organization.trim().length > 80)) local.organization = c.err.organization;
  if (!MOBILE.test(digits(form.phone))) local.phone = c.err.phone;
  if (!/^(\d{10}|\d{13}|\d{17})$/.test(digits(form.nid))) local.nid = c.err.nid;
  if (!MOBILE.test(digits(form.wallet_number))) local.wallet_number = c.err.wallet_number;
  if (form.password.length < 8 || form.password.length > 128) local.password = c.err.password;
  if (form.confirm !== form.password) local.confirm = c.err.confirm;
  if (!consent) local.consent = c.err.consent;
  const errors: Partial<Record<Field, string>> = { ...(tried ? local : {}), ...Object.fromEntries(Object.entries(serverErrors).filter(([, v]) => v)) };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setTried(true);
    setFormError(null);
    const first = (Object.keys(local) as Field[])[0];
    if (first || !role) {
      setFormError(c.fix);
      document.getElementById(`signup-${first ?? "role"}`)?.focus();
      return;
    }
    const body: RegisterBody = {
      name: form.name.trim(), role, district: form.district.trim(), upazila: form.upazila.trim() || undefined,
      organization: needsOrg ? form.organization.trim() : undefined,
      phone: digits(form.phone), nid: digits(form.nid), wallet_provider: provider, wallet_number: digits(form.wallet_number),
      password: form.password, consent: true,
    };
    setBusy(true);
    try {
      const result = await api.register(body);
      setForm(EMPTY);   // the numbers leave this page's memory as soon as the node has them
      if (result.status === "ACTIVE" && result.session) {
        const account = startSession(result.session);
        pushAlert("success", c.created, c.createdDetail(account.user_id));
        navigate(homeOf(account.role));
      } else {
        setPending(result.user);
        window.scrollTo({ top: 0 });
      }
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 422 && Array.isArray(failure.detail)) {
        // Our own words for each field the node rejected; its message (and the value it echoes) is never shown.
        const fields = Object.fromEntries((failure.detail as FieldError[]).map((e) => [String(e.loc.at(-1)), true]));
        const known = (Object.keys(c.err) as Field[]).filter((f) => fields[f]);
        setServerErrors(Object.fromEntries(known.map((f) => [f, c.err[f]])));
        setFormError(c.fix);
      } else if (failure instanceof ApiError && failure.status === 409) setFormError(c.duplicate);
      else if (failure instanceof ApiError && failure.status === 429) setFormError(c.paused);
      else setFormError(failure instanceof ApiError ? failure.message : c.down);
    } finally {
      setBusy(false);
    }
  };

  if (user && !pending) {
    return (
      <Shell>
        <div className="surface rounded-2xl p-6 sm:p-7">
          <h1 className="m-0 text-[22px] font-semibold tracking-[-0.02em] text-slate-900">{c.title}</h1>
          <p className="m-0 mt-3 rounded-lg bg-emerald-50 p-3 text-[14px] text-emerald-900 ring-1 ring-inset ring-emerald-700/15">{c.signedIn(user.name)}</p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Button variant="primary" className="min-h-11" onClick={() => navigate(homeOf(user.role))}>{c.workspace} <ArrowRight className="size-4" aria-hidden /></Button>
            <Button variant="ghost" className="min-h-11" onClick={logout}><LogOut className="size-4" aria-hidden /> {c.logout}</Button>
          </div>
        </div>
      </Shell>
    );
  }

  if (pending) {
    return (
      <Shell>
        <section className="surface rounded-2xl p-6 sm:p-7" aria-labelledby="pending-heading">
          <span className="grid size-11 place-items-center rounded-xl bg-amber-100 text-amber-700 ring-1 ring-inset ring-amber-600/20" aria-hidden>
            <Hourglass className="size-5" />
          </span>
          <h1 id="pending-heading" className="m-0 mt-4 text-[22px] font-semibold tracking-[-0.02em] text-slate-900">{c.pendingTitle}</h1>
          <p className="m-0 mt-2 text-[15px] text-slate-600">{c.pendingText(ROLE_LABEL[lang][pending.role])}</p>
          <dl className="m-0 mt-5 grid gap-3 rounded-xl bg-slate-50 p-4 ring-1 ring-inset ring-slate-200">
            <div>
              <dt className="text-[12.5px] text-slate-500">{c.accountId}</dt>
              <dd className="m-0 font-mono text-[17px] font-semibold text-slate-900">{pending.user_id}</dd>
              <dd className="m-0 text-[12.5px] text-slate-600">{c.keep}</dd>
            </div>
            {pending.kyc && (
              <div>
                <dt className="text-[12.5px] text-slate-500">{c.payouts}</dt>
                <dd className="m-0 text-[14px] text-slate-800">{kycLine(pending.kyc)}</dd>
              </div>
            )}
          </dl>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to="/login" className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-emerald-700 px-4 text-[15px] font-semibold text-white no-underline hover:bg-emerald-800">{c.login} <ArrowRight className="size-4" aria-hidden /></Link>
            <Link to="/" className="inline-flex min-h-11 items-center rounded-lg px-4 text-[15px] font-semibold text-slate-700 no-underline ring-1 ring-inset ring-slate-300 hover:bg-slate-50">{c.home}</Link>
          </div>
        </section>
      </Shell>
    );
  }

  const fieldProps = (field: Field) => ({
    id: `signup-${field}`,
    "aria-invalid": errors[field] ? true : undefined,
    "aria-describedby": `signup-${field}-note`,
  });
  const note = (field: Field, hint?: string) => (errors[field] || hint) && (
    <span id={`signup-${field}-note`} className={cn("text-[12.5px] font-normal", errors[field] ? "text-rose-700" : "text-slate-500")}>{errors[field] ?? hint}</span>
  );

  return (
    <Shell wide>
      <form method="post" noValidate onSubmit={(e) => void submit(e)} className="surface grid gap-7 rounded-2xl p-5 sm:p-7">
        <div>
          <h1 className="m-0 text-[24px] font-semibold tracking-[-0.02em] text-slate-900">{c.title}</h1>
          <p className="m-0 mt-1 text-[14.5px] text-slate-600">{c.lede}</p>
        </div>

        <fieldset className="m-0 grid gap-3 border-0 p-0" aria-describedby="signup-role-note">
          <legend className="mb-3 p-0 text-[16px] font-semibold text-slate-900">{c.who}</legend>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {ROLES.map(({ role: r, icon: Icon, review }, i) => (
              <label key={r} className={cn("flex cursor-pointer sm:min-h-[7.5rem] flex-col gap-1.5 rounded-xl bg-white p-3.5 ring-1 ring-inset ring-slate-300 transition-colors hover:bg-slate-50",
                "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-emerald-700",
                role === r && "bg-emerald-50/60 ring-2 ring-emerald-700 hover:bg-emerald-50/60")}>
                <input type="radio" name="role" value={r} checked={role === r} onChange={() => { setRole(r); setServerErrors((e) => ({ ...e, role: undefined })); }}
                  id={i === 0 ? "signup-role" : undefined} className="sr-only" />
                <span className="flex items-center gap-2 text-[15px] font-semibold text-slate-900">
                  <Icon className={cn("size-4", review ? "text-sky-600" : "text-emerald-700")} aria-hidden /> {ROLE_LABEL[lang][r]}
                </span>
                <span className="text-[13px] text-slate-600">{c.roleHint[r]}</span>
                <Badge tone={review ? "amber" : "emerald"} className="mt-auto self-start">{review ? c.review : c.instant}</Badge>
              </label>
            ))}
          </div>
          {note("role")}
        </fieldset>

        <fieldset className="m-0 grid gap-4 border-0 p-0 sm:grid-cols-2">
          <legend className="mb-3 p-0 text-[16px] font-semibold text-slate-900">{c.about}</legend>
          <Labelled label={c.name} className="sm:col-span-2">
            <input {...fieldProps("name")} required autoComplete="name" maxLength={60} value={form.name} onChange={(e) => set("name", e.target.value)} className={FIELD} />
            {note("name")}
          </Labelled>
          <Labelled label={c.district}>
            <input {...fieldProps("district")} required autoComplete="address-level2" maxLength={40} value={form.district} onChange={(e) => set("district", e.target.value)} className={FIELD} />
            {note("district")}
          </Labelled>
          <Labelled label={c.upazila}>
            <input {...fieldProps("upazila")} autoComplete="address-level3" maxLength={40} value={form.upazila} onChange={(e) => set("upazila", e.target.value)} className={FIELD} />
            {note("upazila")}
          </Labelled>
          {needsOrg && (
            <Labelled label={c.organization} className="sm:col-span-2">
              <input {...fieldProps("organization")} required autoComplete="organization" maxLength={80} value={form.organization} onChange={(e) => set("organization", e.target.value)} className={FIELD} />
              {note("organization", c.orgHint)}
            </Labelled>
          )}
        </fieldset>

        <fieldset className="m-0 grid gap-4 border-0 p-0 sm:grid-cols-2">
          <legend className="mb-3 p-0 text-[16px] font-semibold text-slate-900">{c.ids}</legend>
          <Labelled label={c.phone}>
            <input {...fieldProps("phone")} required type="tel" inputMode="numeric" autoComplete="tel" maxLength={16} placeholder="01XXXXXXXXX"
              value={form.phone} onChange={(e) => set("phone", latinDigits(e.target.value))} className={cn(FIELD, "font-mono")} />
            {note("phone", c.phoneHint)}
          </Labelled>
          {/* autocomplete off: the browser must not offer this number to anyone who uses the device later. */}
          <Labelled label={c.nid}>
            <input {...fieldProps("nid")} required inputMode="numeric" autoComplete="off" spellCheck={false} maxLength={20}
              value={form.nid} onChange={(e) => set("nid", latinDigits(e.target.value))} className={cn(FIELD, "font-mono")} />
            {note("nid", c.nidHint)}
          </Labelled>
          <div className="grid gap-1.5 text-[13.5px] font-medium text-slate-700 sm:col-span-2">
            <span>{c.wallet}</span>
            <Segmented label={c.wallet} value={provider} onChange={setProvider} className="w-fit"
              options={WALLET_PROVIDERS.map((w) => ({ value: w, label: w }))} />
          </div>
          <Labelled label={c.walletNo}>
            <input {...fieldProps("wallet_number")} required inputMode="numeric" autoComplete="off" maxLength={16} placeholder="01XXXXXXXXX"
              value={form.wallet_number} onChange={(e) => set("wallet_number", latinDigits(e.target.value))} className={cn(FIELD, "font-mono")} />
            {note("wallet_number", c.walletHint)}
          </Labelled>
        </fieldset>

        <fieldset className="m-0 grid gap-4 border-0 p-0 sm:grid-cols-2">
          <legend className="mb-3 p-0 text-[16px] font-semibold text-slate-900">{c.secret}</legend>
          <Labelled label={c.password}>
            <span className="relative block">
              <input {...fieldProps("password")} required type={showPassword ? "text" : "password"} autoComplete="new-password" maxLength={128}
                value={form.password} onChange={(e) => set("password", e.target.value)} className={cn(FIELD, "pr-11")} />
              <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? c.hide : c.show}
                className="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-lg text-slate-500 hover:text-slate-800">
                {showPassword ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
              </button>
            </span>
            {note("password", c.passwordHint)}
          </Labelled>
          <Labelled label={c.confirm}>
            <input {...fieldProps("confirm")} required type={showPassword ? "text" : "password"} autoComplete="new-password" maxLength={128}
              value={form.confirm} onChange={(e) => set("confirm", e.target.value)} className={FIELD} />
            {note("confirm")}
          </Labelled>
        </fieldset>

        <div className="grid gap-1.5">
          <label className={cn("flex cursor-pointer gap-3 rounded-xl bg-sky-50 p-3.5 ring-1 ring-inset", errors.consent ? "ring-rose-600" : "ring-sky-600/25")}>
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} {...fieldProps("consent")}
              className="mt-0.5 size-5 shrink-0 accent-emerald-700" />
            <span className="text-[13.5px] leading-relaxed text-slate-800">
              <ShieldCheck className="mr-1 inline size-4 align-[-3px] text-sky-700" aria-hidden />{c.consent}
            </span>
          </label>
          {note("consent")}
        </div>

        {formError && <p role="alert" className="m-0 rounded-lg bg-rose-50 px-3 py-2 text-[13.5px] text-rose-700 ring-1 ring-inset ring-rose-600/20">{formError}</p>}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="m-0 text-[14px] text-slate-600">{c.have} <Link to="/login" className="inline-flex min-h-11 items-center font-semibold text-emerald-700">{c.login}</Link></p>
          <Button variant="primary" type="submit" className="min-h-12 px-5 text-[15px] max-sm:w-full" disabled={busy}>
            {busy ? <Spinner /> : <UserPlus className="size-4" aria-hidden />} {c.submit}
          </Button>
        </div>
      </form>
    </Shell>
  );
}

function Labelled({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return <label className={cn("grid content-start gap-1.5 text-[13.5px] font-medium text-slate-700", className)}>{label}{children}</label>;
}

function Shell({ wide = false, children }: { wide?: boolean; children: ReactNode }) {
  return (
    <div className="relative isolate overflow-hidden">
      <div className="hero-ground" aria-hidden />
      <main className={cn("mx-auto px-4 pt-8 pb-16 sm:px-6", wide ? "max-w-[760px]" : "max-w-[480px]")}>
        <div className="mb-5 flex justify-center"><Wordmark /></div>
        <div className="animate-rise">{children}</div>
      </main>
    </div>
  );
}

export default SignupPage;
