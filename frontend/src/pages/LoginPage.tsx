import { ArrowRight, Eye, EyeOff, Gavel, KeyRound, Landmark, LogIn, LogOut, ShieldCheck, ShoppingCart, Snowflake, Sprout, Truck, Warehouse, type LucideIcon } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { api, ApiError, type AuthUser, type Role } from "../api/client";
import { Wordmark } from "../components/Navbar";
import { Badge, Button, Panel, Spinner } from "../components/ui";
import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { homeOf, ROLE_LABEL, ROLE_TONE } from "../lib/roles";
import { navigate } from "../lib/router";
import { loginAs, logout, pushAlert, useAppState } from "../state/store";

const ROLE_ORDER: Role[] = ["farmer", "coop", "storage", "buyer", "bank", "driver", "judge", "admin"];
const ROLE_ICON: Record<Role, LucideIcon> = {
  farmer: Sprout, coop: Warehouse, storage: Snowflake, buyer: ShoppingCart, bank: Landmark, driver: Truck, judge: Gavel, admin: ShieldCheck,
};
const DEMO_PASSWORD = "krishi2026"; // backend/auth.py DEMO_PASSWORD
const FIELD = "min-h-11 w-full rounded-lg bg-white px-3 text-[15px] text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-700 focus:outline-none";

const COPY = {
  en: {
    title: "Log in",
    lede: "Sign in to your KrishiNexus OS workspace.",
    accountId: "Account ID",
    accountHint: "e.g. FARM-RAN-001",
    password: "Password",
    show: "Show password",
    hide: "Hide password",
    submit: "Log in",
    demo: (pw: string) => `Demo accounts use the password ${pw}. Account IDs are listed under Quick login.`,
    quick: "Quick login",
    quickLede: "Demo only: one click logs you in as that account, no password needed.",
    roleHint: {
      farmer: "Ask in your own dialect, grade a crop, get a store-or-sell decision, join a truck pool.",
      coop: "Watch cold chambers, quota and truck pools; run the live agent trace.",
      storage: "Run your himagar: chamber health, smallholder quota, signed slot bookings and shelf life.",
      buyer: "Bid directly on farmers' lots, see graded loads, verify quality certificates.",
      driver: "Take a delivery, report the load's temperature on the road, confirm delivery to release the farmer's money.",
      bank: "Verify certificates and underwrite warehouse-receipt credit.",
      judge: "Every seat side by side, with the anomaly buttons.",
      admin: "Manage accounts and the demo state.",
    },
    login: "Log in",
    signedIn: (name: string) => `You are logged in as ${name}.`,
    continue: "Go to my workspace",
    logout: "Log out",
    loading: "Loading demo accounts…",
    down: "The backend is not reachable, so login is unavailable. Start the backend and reload.",
    failed: "Login failed",
  },
  bn: {
    title: "লগইন",
    lede: "আপনার কৃষিনেক্সাস ওএস কাজের জায়গায় প্রবেশ করুন।",
    accountId: "অ্যাকাউন্ট আইডি",
    accountHint: "যেমন FARM-RAN-001",
    password: "পাসওয়ার্ড",
    show: "পাসওয়ার্ড দেখুন",
    hide: "পাসওয়ার্ড লুকান",
    submit: "লগইন",
    demo: (pw: string) => `ডেমো অ্যাকাউন্টের পাসওয়ার্ড ${pw}। অ্যাকাউন্ট আইডি নিচে দ্রুত লগইনে আছে।`,
    quick: "দ্রুত লগইন",
    quickLede: "শুধু ডেমোর জন্য: এক ক্লিকে সেই অ্যাকাউন্টে প্রবেশ, পাসওয়ার্ড লাগে না।",
    roleHint: {
      farmer: "নিজের ভাষায় প্রশ্ন, ফসল গ্রেডিং, রাখবেন না বেচবেন সিদ্ধান্ত, ট্রাক পুলে যোগ।",
      coop: "হিমাগার চেম্বার, কোটা ও ট্রাক পুল দেখুন; লাইভ এজেন্ট ট্রেস চালান।",
      storage: "আপনার হিমাগার চালান: চেম্বারের অবস্থা, কৃষকের কোটা, স্বাক্ষরিত বুকিং ও সংরক্ষণকাল।",
      buyer: "কৃষকের লটে সরাসরি দর দিন, গ্রেড করা লট দেখুন, মান সনদ যাচাই করুন।",
      driver: "ডেলিভারি নিন, পথে মালের তাপমাত্রা জানান, পৌঁছে দিয়ে কৃষকের টাকা ছাড় করুন।",
      bank: "সনদ যাচাই করে গুদাম-রসিদ ঋণ দিন।",
      judge: "সব আসন পাশাপাশি, অস্বাভাবিক ঘটনার বোতাম সহ।",
      admin: "অ্যাকাউন্ট ও ডেমো অবস্থা পরিচালনা।",
    },
    login: "লগইন",
    signedIn: (name: string) => `আপনি ${name} হিসেবে লগইন করেছেন।`,
    continue: "আমার কাজের জায়গা",
    logout: "লগআউট",
    loading: "ডেমো অ্যাকাউন্ট লোড হচ্ছে…",
    down: "ব্যাকএন্ডে পৌঁছানো যাচ্ছে না, তাই লগইন বন্ধ। ব্যাকএন্ড চালু করে আবার লোড করুন।",
    failed: "লগইন হয়নি",
  },
};

/** A centred sign-in form (account ID and password), with the demo quick-login accounts below it. */
export function LoginPage() {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  const user = useAppState((s) => s.user);
  const [accounts, setAccounts] = useState<AuthUser[] | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [accountId, setAccountId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.demoUsers().then(setAccounts).catch(() => setDown(true));
  }, []);

  const enter = async (key: string, userId: string, pw?: string) => {
    setBusy(key);
    setError(null);
    try {
      const signedIn = await loginAs(userId, pw);
      navigate(homeOf(signedIn.role));
    } catch (failure) {
      const text = failure instanceof ApiError ? failure.message : c.down;
      // An account that needs a password (admin on the hosted demo): move it into the form instead of a toast.
      const needsPassword = failure instanceof ApiError && failure.status === 401;
      if (key === "form" || needsPassword) {
        setAccountId(userId);
        setError(text);
        if (needsPassword) window.scrollTo({ top: 0, behavior: "smooth" });
      } else pushAlert("danger", c.failed, text);
    } finally {
      setBusy(null);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void enter("form", accountId, password);
  };

  return (
    <main className="mx-auto max-w-[1100px] px-4 pb-16 sm:px-6">
      <section aria-labelledby="login-heading" className="flex min-h-[calc(100vh-150px)] items-center justify-center py-10">
        <div className="w-full max-w-[400px]">
          <div className="mb-5 flex justify-center"><Wordmark /></div>
          <div className="surface rounded-2xl p-6 sm:p-7">
            <h1 id="login-heading" className="m-0 text-[22px] font-semibold tracking-[-0.02em] text-slate-900">{c.title}</h1>
            <p className="m-0 mt-1 text-[14px] text-slate-600">{c.lede}</p>

            {user ? (
              <div className="mt-5 grid gap-2">
                <p className="m-0 rounded-lg bg-emerald-50 p-3 text-[14px] text-emerald-900 ring-1 ring-inset ring-emerald-700/15">{c.signedIn(user.name)}</p>
                <Button variant="primary" className="min-h-11" onClick={() => navigate(homeOf(user.role))}>{c.continue} <ArrowRight className="size-4" aria-hidden /></Button>
                <Button variant="ghost" className="min-h-11" onClick={logout}><LogOut className="size-4" aria-hidden /> {c.logout}</Button>
              </div>
            ) : (
              <form onSubmit={submit} className="mt-5 grid gap-4" noValidate={false}>
                <label className="grid gap-1.5 text-[13.5px] font-medium text-slate-700">{c.accountId}
                  <input required autoComplete="username" autoCapitalize="characters" spellCheck={false} value={accountId}
                    onChange={(e) => setAccountId(e.target.value)} placeholder={c.accountHint} className={cn(FIELD, "font-mono uppercase placeholder:normal-case")} />
                </label>
                <label className="grid gap-1.5 text-[13.5px] font-medium text-slate-700">{c.password}
                  <span className="relative">
                    <input required type={showPassword ? "text" : "password"} autoComplete="current-password" value={password}
                      onChange={(e) => setPassword(e.target.value)} className={cn(FIELD, "pr-11")} />
                    <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? c.hide : c.show}
                      className="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-lg text-slate-500 hover:text-slate-800">
                      {showPassword ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
                    </button>
                  </span>
                </label>
                {error && <p role="alert" className="m-0 rounded-lg bg-rose-50 px-3 py-2 text-[13.5px] text-rose-700 ring-1 ring-inset ring-rose-600/20">{error}</p>}
                <Button variant="primary" type="submit" className="min-h-11 text-[15px]" disabled={busy !== null || down}>
                  {busy === "form" ? <Spinner /> : <LogIn className="size-4" aria-hidden />} {c.submit}
                </Button>
                <p className="m-0 flex gap-2 text-[12.5px] text-slate-500">
                  <KeyRound className="mt-0.5 size-3.5 shrink-0" aria-hidden /> <span>{c.demo(DEMO_PASSWORD)}</span>
                </p>
              </form>
            )}
          </div>
        </div>
      </section>

      <section aria-labelledby="quick-heading" className="border-t border-slate-200 pt-8">
        <h2 id="quick-heading" className="m-0 text-[18px] font-semibold text-slate-900">{c.quick}</h2>
        <p className="m-0 mt-1 text-[14px] text-slate-600">{c.quickLede}</p>

        {down && <p role="alert" className="mt-5 rounded-xl bg-amber-100 p-3 text-[14px] text-amber-900 ring-1 ring-inset ring-amber-600/25">{c.down}</p>}
        {!accounts && !down && <p className="mt-5 flex items-center gap-2 text-[14px] text-slate-600" role="status"><Spinner /> {c.loading}</p>}

        {accounts && (
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {ROLE_ORDER.filter((role) => accounts.some((a) => a.role === role)).map((role) => {
              const Icon = ROLE_ICON[role];
              return (
                <Panel key={role} title={ROLE_LABEL[lang][role]} icon={<Icon className="size-4 text-slate-600" aria-hidden />}>
                  <p className="m-0 mb-3 text-[13px] text-slate-600">{c.roleHint[role]}</p>
                  <ul className="m-0 grid list-none gap-2 p-0">
                    {accounts.filter((a) => a.role === role).map((account) => (
                      <li key={account.user_id}>
                        <button type="button" onClick={() => void enter(account.user_id, account.user_id)} disabled={busy !== null}
                          className={cn("flex min-h-14 w-full items-center gap-3 rounded-xl bg-white px-3 py-2 text-left ring-1 ring-inset ring-slate-200 transition-colors hover:bg-slate-50 disabled:opacity-60",
                            user?.user_id === account.user_id && "ring-emerald-700/40")}>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-[14.5px] font-semibold text-slate-900">{account.name}</span>
                            <span className="block truncate text-[12.5px] text-slate-600">
                              <span className="font-mono">{account.user_id}</span>{account.district ? ` · ${account.district}` : ""}
                            </span>
                          </span>
                          {busy === account.user_id ? <Spinner className="text-emerald-700" />
                            : <Badge tone={ROLE_TONE[role]}>{c.login}</Badge>}
                        </button>
                      </li>
                    ))}
                  </ul>
                </Panel>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}

export default LoginPage;
