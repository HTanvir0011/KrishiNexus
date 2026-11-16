import { useCallback, useEffect, useState } from "react";

import { pushAlert } from "../state/store";

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

/** One admin page's data, plus `run` for its actions: each reports its outcome, then reloads the page's data. */
export function useAdmin<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setData(await load());
    } catch (error) {
      pushAlert("danger", "Could not load", message(error));
    }
  }, [load]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const run = async (key: string, action: () => Promise<unknown>, done: string) => {
    setBusy(key);
    try {
      await action();
      pushAlert("success", done);
      await reload();
    } catch (error) {
      pushAlert("danger", "Action failed", message(error));
    } finally {
      setBusy(null);
    }
  };

  return { data, busy, reload, run };
}

export const TABLE = "w-full min-w-[640px] border-collapse text-left text-[13.5px]";
export const TH = "px-2 py-2 text-[12px] font-medium text-slate-500";
export const TD = "px-2 py-2 align-middle";
export const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
