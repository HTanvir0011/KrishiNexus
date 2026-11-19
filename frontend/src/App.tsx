import { lazy, Suspense, useEffect, type ReactNode } from "react";

import { api, connectAgentTrace } from "./api/client";
import { Navbar } from "./components/Navbar";
import { Alerts } from "./components/shell/Alerts";
import { homeOf } from "./lib/roles";
import { Link, routeOf, useLocation, type Route } from "./lib/router";
import { connectMarketStream } from "./state/marketStream";
import { pushTraces, refreshPools, refreshQuota, refreshTelemetry, restoreSession, setState, useAppState } from "./state/store";

// Each page is its own chunk: only the live OS loads Three.js (the cold-storage twin).
const StoryPage = lazy(() => import("./story/StoryPage"));
const OsPage = lazy(() => import("./os/OsPage"));
const DocsShell = lazy(() => import("./os/DocsShell"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const SignupPage = lazy(() => import("./pages/SignupPage"));
const GuidePage = lazy(() => import("./pages/GuidePage"));
const AdminPage = lazy(() => import("./admin/AdminPage"));

const TITLES: Record<Route["page"], string> = {
  story: "KrishiNexus OS: fair prices, open cold storage and flood alerts for Bangladeshi farmers",
  os: "KrishiNexus OS · live operations workspace",
  docs: "KrishiNexus OS · technical whitepaper",
  login: "KrishiNexus OS · log in",
  signup: "KrishiNexus OS · create an account",
  guide: "KrishiNexus OS · user guide",
  admin: "KrishiNexus OS · admin panel",
};

/** Health and the live agent trace everywhere; the OS also polls pools, chambers and quota. */
function useBackendBootstrap(page: Route["page"]) {
  useEffect(() => {
    void restoreSession();
    const stopTrace = connectAgentTrace(pushTraces, (traceStatus) => setState({ traceStatus }));
    const health = () =>
      api.health()
        .then((h) => setState({ backendLive: true, health: { mcpServers: h.mcp_servers, tools: h.tools, speechToText: h.speech_to_text ?? true } }))
        .catch(() => setState({ backendLive: false }));
    void health();
    const timer = window.setInterval(health, 10_000);
    return () => {
      stopTrace();
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (page !== "os") return;
    void refreshPools();
    void refreshTelemetry();
    void refreshQuota();
    const timers = [
      window.setInterval(() => void refreshTelemetry(), 6_000),
      window.setInterval(() => void refreshPools(), 9_000),
    ];
    return () => timers.forEach((t) => window.clearInterval(t));
  }, [page]);
}

function PageLoading() {
  return <div className="grid min-h-[60vh] place-items-center text-[15px] text-slate-500" role="status">Loading…</div>;
}

/** The workspace and the admin panel need a logged-in account; the admin panel needs the admin role. */
function Gate({ adminOnly = false, children }: { adminOnly?: boolean; children: ReactNode }) {
  const user = useAppState((s) => s.user);
  const authChecked = useAppState((s) => s.authChecked);
  if (!authChecked) return <PageLoading />;
  if (!user) return <LoginPage />;
  if (adminOnly && user.role !== "admin") {
    return (
      <main className="mx-auto max-w-[640px] px-4 pt-16 text-center">
        <p className="m-0 text-[15px] text-slate-700">The admin panel is for admin accounts.</p>
        <Link to={homeOf(user.role)} className="mt-3 inline-block text-[14px] font-semibold text-emerald-700">Go to my workspace</Link>
      </main>
    );
  }
  return <>{children}</>;
}

export default function App() {
  const route = routeOf(useLocation());
  const lang = useAppState((s) => s.lang);
  const userId = useAppState((s) => s.user?.user_id);
  useBackendBootstrap(route.page);

  // Live market events for a signed-in account (the stream is public, but only an account has lots, bids or jobs).
  useEffect(() => (userId ? connectMarketStream() : undefined), [userId]);

  useEffect(() => {
    document.title = TITLES[route.page];
  }, [route.page]);

  useEffect(() => {
    document.documentElement.lang = lang === "bn" ? "bn" : "en";
  }, [lang]);

  return (
    <>
      <Navbar />
      <Suspense fallback={<PageLoading />}>
        {route.page === "story" && <StoryPage />}
        {route.page === "login" && <LoginPage />}
        {route.page === "signup" && <SignupPage />}
        {route.page === "guide" && <GuidePage />}
        {route.page === "os" && <Gate><OsPage view={route.view} /></Gate>}
        {route.page === "admin" && <Gate adminOnly><AdminPage section={route.section} /></Gate>}
        {route.page === "docs" && <DocsShell />}
      </Suspense>
      <Alerts />
    </>
  );
}
