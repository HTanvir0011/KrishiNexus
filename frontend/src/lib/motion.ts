import { useEffect, useRef, useState } from "react";

/**
 * True for `ms` after `value` turns into `target` during this session (never on first render), so a milestone such
 * as a released payment is acknowledged once, when it happens, and not every time the page polls or re-renders.
 */
export function useBecame<T>(value: T, target: T, ms = 1800): boolean {
  const previous = useRef(value);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const became = previous.current !== target && value === target;
    previous.current = value;
    if (!became) return;
    setOn(true);
    const timer = window.setTimeout(() => setOn(false), ms);
    return () => window.clearTimeout(timer);
  }, [value, target, ms]);
  return on;
}

/** The current time, re-read every `ms`, for labels such as "updated 30 s ago". */
export function useNow(ms: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(timer);
  }, [ms]);
  return now;
}

/** Ids that appeared since the last render (none on the first), held for `ms`, so polled lists can mark what is new. */
export function useFreshIds(ids: string[], ms = 1800): Set<string> {
  const known = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(() => new Set());
  const signature = ids.join("|");
  useEffect(() => {
    const added = known.current ? ids.filter((id) => !known.current!.has(id)) : [];
    known.current = new Set(ids);
    if (added.length === 0) return;
    setFresh(new Set(added));
    const timer = window.setTimeout(() => setFresh(new Set()), ms);
    return () => window.clearTimeout(timer);
    // `signature` stands for `ids`.
  }, [signature, ms]);
  return fresh;
}
