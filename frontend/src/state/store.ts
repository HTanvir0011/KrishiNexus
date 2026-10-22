/**
 * Minimal global store (useSyncExternalStore) shared by every pane, so an action in the Farmer app
 * immediately updates the Command Center, Truck Pool Map, 3D Twin and Bank Portal.
 */

import { useSyncExternalStore } from "react";

import {
  api,
  type ChamberTelemetry,
  type GradeCropResult,
  type PoolView,
  type QuotaResult,
  type SarFloodReport,
  type TraceConnection,
  type TraceEvent,
  type VoiceInteractResponse,
} from "../api/client";

export type AlertTone = "info" | "success" | "warn" | "danger";

export interface AlertItem {
  id: number;
  tone: AlertTone;
  title: string;
  detail?: string;
}

export interface FocusChamber {
  facilityId: string;
  chamberId: string;
  district: string;
}

export interface AppState {
  backendLive: boolean | null;
  traceStatus: TraceConnection;
  offlineMode: boolean;
  traces: TraceEvent[];
  activeSessionId: string | null;
  lastVoice: VoiceInteractResponse | null;
  lastGrade: GradeCropResult | null;
  pools: PoolView[];
  focusPoolId: string;
  focusChamber: FocusChamber;
  telemetry: ChamberTelemetry | null;
  quota: QuotaResult | null;
  chamberAlarm: boolean;
  floodReport: SarFloodReport | null;
  reservationPulse: number;
  alerts: AlertItem[];
}

const MAX_TRACES = 600;
let alertSeq = 0;

let state: AppState = {
  backendLive: null,
  traceStatus: "connecting",
  offlineMode: false,
  traces: [],
  activeSessionId: null,
  lastVoice: null,
  lastGrade: null,
  pools: [],
  focusPoolId: "POOL-BOGURA-01",
  focusChamber: { facilityId: "BCSA-BOG-05", chamberId: "CH-01", district: "Bogura" },
  telemetry: null,
  quota: null,
  chamberAlarm: false,
  floodReport: null,
  reservationPulse: 0,
  alerts: [],
};

const listeners = new Set<() => void>();

export function getState(): AppState {
  return state;
}

export function setState(patch: Partial<AppState> | ((s: AppState) => Partial<AppState>)): void {
  state = { ...state, ...(typeof patch === "function" ? patch(state) : patch) };
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Select a slice of state. Selectors must return existing references (derive with useMemo). */
export function useAppState<T>(selector: (s: AppState) => T): T {
  return useSyncExternalStore(subscribe, () => selector(state));
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export function pushTraces(events: TraceEvent[]): void {
  if (!events.length) return;
  setState((s) => {
    const seen = new Set(s.traces.map((e) => `${e.session_id}#${e.seq}`));
    const fresh = events.filter((e) => !seen.has(`${e.session_id}#${e.seq}`));
    if (!fresh.length) return {};
    const latest = fresh[fresh.length - 1];
    return { traces: [...s.traces, ...fresh].slice(-MAX_TRACES), activeSessionId: latest.session_id };
  });
}

export function pushAlert(tone: AlertTone, title: string, detail?: string): void {
  const id = ++alertSeq;
  setState((s) => ({ alerts: [...s.alerts, { id, tone, title, detail }].slice(-5) }));
  window.setTimeout(() => setState((s) => ({ alerts: s.alerts.filter((a) => a.id !== id) })), 7_000);
}

export async function refreshPools(): Promise<void> {
  const result = await api.truckPools();
  setState({ pools: result.data, backendLive: result.live });
}

export async function refreshTelemetry(): Promise<void> {
  const { facilityId, chamberId } = state.focusChamber;
  const result = await api.chamberTelemetry(facilityId, chamberId);
  setState({
    telemetry: result.data,
    backendLive: result.live,
    chamberAlarm: result.data.power_source === "OUTAGE" || result.data.relative_humidity_pct > 95,
  });
}

export async function refreshQuota(): Promise<void> {
  const result = await api.coldStorageQuota(state.focusChamber.district);
  setState({ quota: result.data });
}
