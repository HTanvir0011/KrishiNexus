import { BarChart3, BookOpen, ExternalLink, FlaskConical, LayoutGrid, Plug, Sprout } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { DepthMatrixSection } from "../components/docs/DepthMatrixSection";
import { EconomicsSection } from "../components/docs/EconomicsSection";
import { EvalsSection } from "../components/docs/EvalsSection";
import { McpInspectorSection } from "../components/docs/McpInspectorSection";
import { ProvenanceSection } from "../components/docs/ProvenanceSection";
import { cn } from "../lib/format";

const SECTIONS: { id: string; title: string; kicker: string; icon: ReactNode; body: ReactNode }[] = [
  { id: "pitch", kicker: "Section 1", title: "Executive pitch & data provenance", icon: <Sprout className="size-4" />, body: <ProvenanceSection /> },
  { id: "mcp", kicker: "Section 2", title: "Interactive 13-tool MCP protocol inspector", icon: <Plug className="size-4" />, body: <McpInspectorSection /> },
  { id: "matrix", kicker: "Section 3", title: "AI depth architecture matrix", icon: <LayoutGrid className="size-4" />, body: <DepthMatrixSection /> },
  { id: "evals", kicker: "Section 4", title: "Live metrics & 100-scenario regression runner", icon: <FlaskConical className="size-4" />, body: <EvalsSection /> },
  { id: "economics", kicker: "Section 5", title: "B2B unit economics & national impact simulator", icon: <BarChart3 className="size-4" />, body: <EconomicsSection /> },
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
    return () => observer.disconnect();
  }, []);

  const jump = (id: string) => {
    refs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
    history.replaceState(null, "", `/docs#${id}`);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
      <aside className="lg:sticky lg:top-24 lg:h-[calc(100vh-7rem)]">
        <div className="panel p-3">
          <div className="mb-2 flex items-center gap-1.5 label text-[13px] font-semibold text-emerald-300"><BookOpen className="size-3.5" /> Whitepaper</div>
          <nav className="space-y-0.5">
            {SECTIONS.map((s) => (
              <button key={s.id} type="button" onClick={() => jump(s.id)}
                className={cn("flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition-colors",
                  active === s.id ? "bg-emerald-500/15 text-emerald-200" : "text-slate-400 hover:bg-ink-800 hover:text-slate-200")}>
                <span className="mt-0.5">{s.icon}</span>
                <span><span className="block label text-[12px] opacity-70">{s.kicker}</span>{s.title}</span>
              </button>
            ))}
          </nav>
          <a href={BACKEND_DOCS} target="_blank" rel="noreferrer" className="mt-3 flex items-center gap-1 border-t border-ink-700 pt-2 text-[11px] text-sky-300 hover:underline">
            FastAPI OpenAPI reference <ExternalLink className="size-3" />
          </a>
        </div>
      </aside>
      <div className="min-w-0 space-y-8 pb-16">
        <header>
          <h1 className="text-2xl font-bold text-slate-50">KrishiNexus OS technical whitepaper</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Every panel below talks to the running backend: call any MCP tool, test each AI layer, recompute the metrics and run the regression suite live.
          </p>
        </header>
        {SECTIONS.map((s) => (
          <section key={s.id} id={s.id} ref={(el) => { refs.current[s.id] = el; }} className="scroll-mt-20">
            <div className="mb-3 flex items-center gap-2">
              <span className="grid size-7 place-items-center rounded-lg bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/30">{s.icon}</span>
              <div>
                <div className="label text-[12px] text-slate-500">{s.kicker}</div>
                <h2 className="text-lg font-semibold text-slate-100">{s.title}</h2>
              </div>
            </div>
            {s.body}
          </section>
        ))}
      </div>
    </div>
  );
}
