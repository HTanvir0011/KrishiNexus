import { lazy, Suspense, useEffect } from "react";

import { api, connectAgentTrace } from "./api/client";
import { Navbar } from "./components/Navbar";
import { Alerts } from "./components/shell/Alerts";
import { routeOf, useLocation, type Route } from "./lib/router";
import { pushTraces, refreshPools, refreshQuota, refreshTelemetry, setState, useAppState } from "./state/store";

// Each page is its own chunk: only the live OS loads Three.js (the cold-storage twin).
const StoryPage = lazy(() => import("./story/StoryPage"));
const OsPage = lazy(() => import("./os/OsPage"));
const DocsShell = lazy(() => import("./os/DocsShell"));

const TITLES: Record<Route["page"], string> = {
  story: "KrishiNexus OS: fair prices, open cold storage and flood alerts for Bangladeshi farmers",
  os: "KrishiNexus OS · live operations workspace",
  docs: "KrishiNexus OS · technical whitepaper",
};

/** Health and the live agent trace everywhere; the OS also polls pools, chambers and quota. */
function useBackendBootstrap(page: Route["page"]) {
  useEffect(() => {
    const stopTrace = connectAgentTrace(pushTraces, (traceStatus) => setState({ traceStatus }));
    const health = () =>
      api.health()
        .then((h) => setState({ backendLive: true, health: { mcpServers: h.mcp_servers, tools: h.tools } }))
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

export default function App() {
  const route = routeOf(useLocation());
  const lang = useAppState((s) => s.lang);
  useBackendBootstrap(route.page);

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
        {route.page === "os" && <OsPage view={route.view} />}
        {route.page === "docs" && <DocsShell />}
      </Suspense>
      <Alerts />
    </>
  );
}
