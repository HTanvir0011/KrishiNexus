import { Download } from "lucide-react";

import site from "../data/site.json";
import { bnDigits, cn } from "../lib/format";
import { useCopy } from "../lib/i18n";

const COPY = {
  en: {
    get: "Get the Android app",
    meta: `About ${site.apk_size_mb} MB · Android ${site.android_min} or newer`,
    older: "For older phones (32-bit)",
  },
  bn: {
    get: "অ্যান্ড্রয়েড অ্যাপ নিন",
    meta: `প্রায় ${bnDigits(site.apk_size_mb)} এমবি · অ্যান্ড্রয়েড ${bnDigits(site.android_min)} বা নতুন`,
    older: "পুরোনো ফোনের জন্য (৩২-বিট)",
  },
};

/** "Get the Android app": the APK from the latest GitHub release, with the 32-bit build for older phones beside it. */
export function AppDownload({ className, quiet = false }: { className?: string; quiet?: boolean }) {
  const c = useCopy(COPY);
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1", className)}>
      <a href={site.apk} className={cn("inline-flex min-h-11 items-center gap-2 rounded-lg px-4 text-[15px] font-semibold no-underline transition-colors",
        quiet ? "bg-white text-slate-800 ring-1 ring-inset ring-slate-300 hover:bg-slate-50" : "bg-emerald-700 text-white shadow-sm hover:bg-emerald-800")}>
        <Download className="size-4" aria-hidden /> {c.get}
      </a>
      <span className="flex flex-wrap items-center gap-x-2 text-[13px] text-slate-600">
        <span>{c.meta}</span>
        <a href={site.apk_armv7} className="inline-flex min-h-11 items-center font-medium text-emerald-700 hover:text-emerald-800">{c.older}</a>
      </span>
    </div>
  );
}
