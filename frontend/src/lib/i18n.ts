import { useAppState, type Lang } from "../state/store";

/** Pick a component's copy for the navbar language toggle. Copy objects live next to the component that uses them. */
export function useCopy<T>(copy: Record<Lang, T>): T {
  return copy[useAppState((s) => s.lang)];
}
