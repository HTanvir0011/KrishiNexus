import { BarChart3, BookOpen, ExternalLink, FlaskConical, LayoutGrid, Plug, Sprout } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { DepthMatrixSection } from "../components/docs/DepthMatrixSection";
import { EconomicsSection } from "../components/docs/EconomicsSection";
import { EvalsSection } from "../components/docs/EvalsSection";
import { McpInspectorSection } from "../components/docs/McpInspectorSection";
import { ProvenanceSection } from "../components/docs/ProvenanceSection";
import { cn } from "../lib/format";

/** A real sequence: the sidebar numbers them; `nav` is the short name used in the sidebar and the mobile chips. */
const SECTIONS: { id: string; nav: string; title: string; icon: ReactNode; body: ReactNode }[] = [
  { id: "pitch", nav: "Provenance and formulas", title: "Macroeconomic provenance and the formulas", icon: <Sprout className="size-4" />, body: <ProvenanceSection /> },
  { id: "mcp", nav: "MCP protocol inspector", title: "Interactive 13-tool MCP protocol inspector", icon: <Plug className="size-4" />, body: <McpInspectorSection /> },
  { id: "matrix", nav: "AI depth matrix", title: "AI depth verification matrix (110-point rubric)", icon: <LayoutGrid className="size-4" />, body: <DepthMatrixSection /> },
  { id: "evals", nav: "Evaluation and regression", title: "Live computed evaluation and the 100-case regression runner", icon: <FlaskConical className="size-4" />, body: <EvalsSection /> },
  { id: "economics", nav: "Unit economics", title: "B2B unit economics and national impact simulator", icon: <BarChart3 className="size-4" />, body: <EconomicsSection /> },
];

const BACKEND_DOCS = `${import.meta.env.VITE_API_BASE ?? "http://localhost:8000"}/docs`;

export function DocsPage() {
  const [active, setActive] = useState(SECTIONS[0].id);
  const refs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -60% 0px" },
    );
    Object.values(refs.current).forEach((el) => el && observer.observe(el));
    // /docs#id deep link: this page is a lazy chunk, so the browser's own fragment scroll ran before the section existed.
    refs.current[location.hash.slice(1)]?.scrollIntoView({ block: "start" });
    return () => observer.disconnect();
  }, []);

  const jump = (id: string) => {
    refs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
    history.replaceState(null, "", `/docs#${id}`);
  };

  return (
    <div className="mx-auto grid w-full max-w-[1280px] grid-cols-1 gap-x-10 gap-y-6 pb-24 lg:grid-cols-[240px_minmax(0,1fr)]">
      <header className="min-w-0 max-w-[980px] border-b border-slate-200 pb-6 lg:col-start-2 lg:row-start-1">
        <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.01em] text-slate-900 sm:text-[34px]">KrishiNexus OS technical whitepaper</h1>
        <p className="mt-2 max-w-[680px] text-[16px] leading-relaxed text-slate-600">
          This page talks to the running backend: call any MCP tool, test each AI layer, recompute the metrics and run the regression suite live.
        </p>
      </header>

      <aside className="min-w-0 lg:sticky lg:top-[88px] lg:col-start-1 lg:row-[1/span_2] lg:self-start">
        <nav aria-label="Whitepaper sections">
          <div className="mb-3 hidden items-center gap-2 text-[13px] font-semibold text-slate-900 lg:flex">
            <BookOpen className="size-4 text-emerald-700" /> Whitepaper
          </div>
          {/* Phones: one horizontally scrolling row of chips. Desktop: a numbered list on a hairline rail. */}
          <ol className="scroll-thin flex gap-2 overflow-x-auto py-1 lg:flex-col lg:gap-0 lg:overflow-visible lg:border-l lg:border-slate-200 lg:py-0">
            {SECTIONS.map((s, i) => {
              const on = active === s.id;
              return (
                <li key={s.id} className="shrink-0">
                  <button type="button" onClick={() => jump(s.id)} aria-current={on ? "location" : undefined}
                    className={cn(
                      "flex min-h-10 items-center gap-2 whitespace-nowrap rounded-full px-3.5 text-[13.5px] font-medium ring-1 ring-inset transition-colors",
                      "lg:-ml-px lg:min-h-0 lg:w-full lg:rounded-none lg:border-l-2 lg:px-4 lg:py-2 lg:text-left lg:whitespace-normal lg:ring-0",
                      on
                        ? "bg-emerald-50 text-emerald-800 ring-emerald-700/25 lg:border-emerald-700 lg:bg-transparent lg:text-emerald-700"
                        : "bg-white text-slate-600 ring-slate-200 hover:text-slate-900 lg:border-transparent lg:bg-transparent lg:hover:border-slate-300",
                    )}>
                    <span className={cn("num w-3 shrink-0 text-[12.5px]", on ? "text-emerald-700" : "text-slate-500")}>{i + 1}</span>
                    {s.nav}
                  </button>
                </li>
              );
            })}
          </ol>
          <a href={BACKEND_DOCS} target="_blank" rel="noreferrer"
            className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-sky-700 hover:underline lg:mt-5 lg:flex lg:border-t lg:border-slate-200 lg:pt-4">
            FastAPI OpenAPI reference <ExternalLink className="size-3.5" />
          </a>
        </nav>
      </aside>

      <div className="min-w-0 max-w-[980px] space-y-16 lg:col-start-2 lg:row-start-2">
        {SECTIONS.map((s) => (
          <section key={s.id} id={s.id} ref={(el) => { refs.current[s.id] = el; }} className="scroll-mt-[88px]">
            <div className="mb-5 flex items-start gap-3">
              <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-700 ring-1 ring-emerald-700/15 ring-inset">{s.icon}</span>
              <h2 className="text-[22px] font-semibold leading-snug tracking-[-0.01em] text-slate-900">{s.title}</h2>
            </div>
            {s.body}
          </section>
        ))}
      </div>
    </div>
  );
}
