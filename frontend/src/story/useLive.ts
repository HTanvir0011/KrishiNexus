import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import type { SourceStatus } from "./data";

export interface Live<T> {
  data: T | null;
  status: SourceStatus;
  /** Round trip of the live call. */
  ms: number | null;
  error: string | null;
}

/**
 * Run `fetcher` whenever `key` changes and time it. A network or 5xx failure shows `fallback()` (a dated snapshot) as
 * "cached"; a 4xx is a real error and is reported, never masked.
 */
export function useLive<T>(key: string, fetcher: () => Promise<T>, fallback: () => T | null): Live<T> {
  const [state, setState] = useState<Live<T>>({ data: null, status: "loading", ms: null, error: null });

  useEffect(() => {
    let active = true;
    setState((s) => ({ ...s, status: "loading", error: null }));
    const started = performance.now();
    fetcher()
      .then((data) => active && setState({ data, status: "live", ms: performance.now() - started, error: null }))
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status < 500) {
          setState({ data: null, status: "live", ms: null, error: error.message });
          return;
        }
        setState({ data: fallback(), status: "cached", ms: null, error: null });
      });
    return () => {
      active = false;
    };
    // `key` captures everything the fetcher depends on.
  }, [key]);

  return state;
}
