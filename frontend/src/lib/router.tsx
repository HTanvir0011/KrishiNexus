/** Minimal history router: `/` story, `/login`, `/os[/field|/coop|/himagar|/trade|/driver|/market]` live OS, `/admin[/section]`, `/docs` whitepaper. */

import { useSyncExternalStore, type AnchorHTMLAttributes, type MouseEvent } from "react";

export type OsView = "judge" | "field" | "coop" | "himagar" | "trade" | "driver" | "market";
export type AdminSection = "overview" | "accounts" | "pools" | "escrows" | "anomalies" | "activity" | "feedback";
export type Route = { page: "story" } | { page: "login" } | { page: "admin"; section: AdminSection } | { page: "os"; view: OsView } | { page: "docs" };

const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("popstate", listener);
  };
}

const currentLocation = () => `${location.pathname.replace(/\/+$/, "") || "/"}${location.hash}`;

export function useLocation(): string {
  return useSyncExternalStore(subscribe, currentLocation);
}

export function routeOf(locationText: string): Route {
  const [path, hash = ""] = locationText.split("#");
  if (path === "/docs" || hash === "docs") return { page: "docs" };
  if (path === "/login") return { page: "login" };
  if (path === "/admin") return { page: "admin", section: "overview" };
  const admin = /^\/admin\/(accounts|pools|escrows|anomalies|activity|feedback)$/.exec(path);
  if (admin) return { page: "admin", section: admin[1] as AdminSection };
  if (path === "/os") return { page: "os", view: "judge" };
  const os = /^\/os\/(field|coop|himagar|trade|driver|market)$/.exec(path);
  if (os) return { page: "os", view: os[1] as OsView };
  return { page: "story" };
}

export function navigate(to: string): void {
  if (currentLocation() === to) return;
  history.pushState(null, "", to);
  notify();
  const hash = to.split("#")[1];
  if (hash) requestAnimationFrame(() => document.getElementById(hash)?.scrollIntoView({ behavior: "smooth" }));
  else window.scrollTo({ top: 0 });
}

/** A real link (open-in-new-tab still works) that navigates in place on a plain click. */
export function Link({ to, onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) {
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to);
  };
  return <a href={to} onClick={handle} {...props} />;
}
