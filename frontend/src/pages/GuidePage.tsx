import { ArrowRight, BookOpen, Printer } from "lucide-react";
import { useEffect } from "react";

import { AppDownload } from "../components/AppDownload";
import { Button } from "../components/ui";
import guide from "../data/guide.json";
import { Link } from "../lib/router";
import { useAppState } from "../state/store";

interface Block {
  p?: string;
  ul?: string[];
  ol?: string[];
  faq?: { q: string; a: string }[];
  link?: { href: string; text: string };
  app?: boolean;
}

function GuideBlock({ block }: { block: Block }) {
  if (block.p) return <p className="m-0 mt-3 text-[16px] leading-relaxed text-slate-700">{block.p}</p>;
  if (block.ul || block.ol) {
    const List = block.ol ? "ol" : "ul";
    return (
      <List className={`m-0 mt-3 grid gap-2 pl-6 text-[16px] leading-relaxed text-slate-700 marker:font-semibold marker:text-emerald-700 ${block.ol ? "list-decimal" : "list-disc"}`}>
        {(block.ol ?? block.ul)!.map((item) => <li key={item} className="pl-1">{item}</li>)}
      </List>
    );
  }
  if (block.faq) {
    return (
      <dl className="m-0 mt-2">
        {block.faq.map((f) => (
          <div key={f.q} className="mt-5">
            <dt className="text-[16px] font-semibold text-slate-900">{f.q}</dt>
            <dd className="m-0 mt-1 text-[16px] leading-relaxed text-slate-700">{f.a}</dd>
          </div>
        ))}
      </dl>
    );
  }
  if (block.link) {
    return (
      <p className="m-0 mt-2">
        <Link to={block.link.href} className="inline-flex min-h-11 items-center gap-1.5 text-[15px] font-semibold text-emerald-700 no-underline hover:text-emerald-800">
          {block.link.text} <ArrowRight className="size-4" aria-hidden />
        </Link>
      </p>
    );
  }
  return block.app ? <AppDownload className="mt-4 print:hidden" /> : null;
}

/**
 * The plain-language user guide, from src/data/guide.json in the navbar's language. scripts/prerender.mjs writes the
 * same guide to dist/guide/ (and /guide/bn/), so it also loads with no JavaScript and prints from either page.
 */
export function GuidePage() {
  const lang = useAppState((s) => s.lang);
  const g = guide[lang];

  // /guide#app from another page: the browser's own jump ran before this lazy page existed.
  useEffect(() => {
    const id = location.hash.slice(1);
    if (id) document.getElementById(id)?.scrollIntoView({ block: "start" });
  }, []);

  return (
    <main lang={lang} className="guide mx-auto grid max-w-[1180px] gap-x-12 px-4 pt-8 pb-20 sm:px-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <header className="min-w-0 border-b border-slate-200 pb-6 lg:col-start-2">
        <h1 className={`m-0 text-[clamp(28px,4vw,40px)] font-semibold text-slate-900 ${lang === "bn" ? "leading-[1.32]" : "leading-[1.1] tracking-[-0.025em]"}`}>{g.title}</h1>
        <p className="m-0 mt-3 max-w-[46rem] text-[17px] leading-relaxed text-slate-600">{g.lede}</p>
        <div className="mt-4 flex flex-wrap items-center gap-3 print:hidden">
          <Button variant="ghost" className="min-h-11" onClick={() => window.print()}><Printer className="size-4" aria-hidden /> {g.print}</Button>
          <span className="text-[13px] text-slate-500">{g.updated} {guide.updated}</span>
        </div>
      </header>

      <nav aria-labelledby="guide-toc" className="min-w-0 pt-6 print:hidden lg:sticky lg:top-[88px] lg:col-start-1 lg:row-[1/span_2] lg:self-start lg:pt-0">
        <h2 id="guide-toc" className="m-0 mb-2 flex items-center gap-2 text-[13px] font-semibold text-slate-900">
          <BookOpen className="size-4 text-emerald-700" aria-hidden /> {g.contents}
        </h2>
        <ol className="scroll-thin m-0 flex list-none gap-2 overflow-x-auto p-0 py-1 lg:flex-col lg:gap-0 lg:overflow-visible lg:border-l lg:border-slate-200 lg:py-0">
          {g.sections.map((s) => (
            <li key={s.id} className="shrink-0">
              <a href={`#${s.id}`} className="flex min-h-10 items-center rounded-full bg-white px-3.5 text-[13.5px] font-medium whitespace-nowrap text-slate-600 no-underline ring-1 ring-inset ring-slate-200 hover:text-slate-900 lg:-ml-px lg:rounded-none lg:border-l-2 lg:border-transparent lg:bg-transparent lg:px-4 lg:whitespace-normal lg:ring-0 lg:hover:border-slate-300">
                {s.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="min-w-0 max-w-[760px] lg:col-start-2">
        {g.sections.map((s) => (
          <section key={s.id} id={s.id} aria-labelledby={`${s.id}-heading`} className="scroll-mt-[88px] pt-10 print:break-inside-avoid-page print:pt-5">
            <h2 id={`${s.id}-heading`} className={`m-0 text-[22px] font-semibold text-slate-900 ${lang === "bn" ? "leading-[1.4]" : "tracking-[-0.015em]"}`}>{s.title}</h2>
            {(s.blocks as Block[]).map((block, i) => <GuideBlock key={i} block={block} />)}
          </section>
        ))}
      </div>
    </main>
  );
}

export default GuidePage;
