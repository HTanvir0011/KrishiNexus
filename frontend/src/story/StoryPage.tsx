import "./story.css";

import { MoveHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";

import { MosaicSvg } from "../components/MosaicSvg";
import { TopBar } from "../components/shell/TopBar";
import { bnDigits, cn, kg, tk } from "../lib/format";
import { AgentsChapter } from "./chapters/AgentsChapter";
import { AnswerChapter } from "./chapters/AnswerChapter";
import { ColdChapter } from "./chapters/ColdChapter";
import { DawnChapter } from "./chapters/DawnChapter";
import { HaorChapter } from "./chapters/HaorChapter";
import { RoadChapter } from "./chapters/RoadChapter";
import { useStoryFacts } from "./data";
import { DISTRICT_LABELS, FACILITIES, HAOR_BASINS, PLACES, TIER_STOPS, type FacilitySeed, type LatLon } from "./geo";
import { Hero } from "./Hero";
import { CHAPTER_COUNT, Landscape, type RouteMode } from "./landscape/Landscape";
import { Anchor } from "./parts";
import type { StoryPreset } from "./presets";

const CHAPTERS = [
  { id: "story-hero", title: "Rahim's question" },
  { id: "story-cold", title: "Who holds the cold" },
  { id: "story-road", title: "The road to Dhaka" },
  { id: "story-answer", title: "Rahim's answer" },
  { id: "story-haor", title: "Abdul's question" },
  { id: "story-agents", title: "Four agents, one answer" },
  { id: "story-dawn", title: "Open the OS" },
];

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function Chapter({ index, sectionRef, tall = true, children }: {
  index: number;
  sectionRef: (el: HTMLElement | null) => void;
  tall?: boolean;
  children: ReactNode;
}) {
  return (
    <section id={CHAPTERS[index].id} ref={sectionRef} aria-label={CHAPTERS[index].title}
      className={cn("relative px-4 sm:px-8 lg:px-12", tall ? "min-h-[155vh] py-24" : "min-h-[110vh] pt-24 pb-32")}>
      <div className="pointer-events-auto max-w-[34rem]">{children}</div>
    </section>
  );
}

export default function StoryPage() {
  const facts = useStoryFacts();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const coordsRef = useRef<HTMLSpanElement>(null);
  const sections = useRef<(HTMLElement | null)[]>([]);
  const dragging = useRef(false);
  const [engine, setEngine] = useState<Landscape | null>(null);
  const [webgl, setWebgl] = useState(true);
  const [active, setActive] = useState(0);
  const [district, setDistrict] = useState<FacilitySeed["district"]>("Rangpur");
  const [mode, setMode] = useState<RouteMode>("syndicate");
  const [focus, setFocus] = useState<number | null>(null);
  const [radar, setRadar] = useState(0.62);
  const [flood, setFlood] = useState(0);
  const [heroPreset, setHeroPreset] = useState<StoryPreset | null>(null);
  const ladder = facts.ladder.data;
  const rahim = facts.rahim.data;

  // One world for the whole page; a static mosaic when WebGL is missing.
  useEffect(() => {
    const canvas = canvasRef.current;
    const labels = labelsRef.current;
    if (!canvas || !labels) return;
    if (!Landscape.isSupported()) {
      setWebgl(false);
      return;
    }
    let instance: Landscape | null = null;
    try {
      instance = new Landscape({
        canvas,
        labelsRoot: labels,
        reducedMotion: reducedMotion(),
        onPlace: (text) => {
          if (coordsRef.current) coordsRef.current.textContent = text;
        },
      });
      setEngine(instance);
    } catch (error) {
      console.warn("WebGL landscape unavailable, showing the static mosaic", error);
      setWebgl(false);
    }
    return () => {
      instance?.dispose();
      setEngine(null);
    };
  }, []);

  // Scroll position in chapters: the section crossing the reading line, plus how far through it we are.
  useEffect(() => {
    let frame = 0;
    const measure = () => {
      frame = 0;
      const line = window.innerHeight * (window.innerWidth < 768 ? 0.7 : 0.5);
      let p = 0;
      sections.current.forEach((el, i) => {
        if (!el) return;
        const rect = el.getBoundingClientRect();
        if (rect.top <= line) p = i + Math.min(0.9999, Math.max(0, (line - rect.top) / rect.height));
      });
      engine?.setProgress(p);
      setActive(Math.min(CHAPTER_COUNT - 1, Math.floor(p + 0.2)));
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      cancelAnimationFrame(frame);
    };
  }, [engine]);

  useEffect(() => engine?.setColdDistrict(district), [engine, district]);
  useEffect(() => engine?.setRouteMode(mode), [engine, mode]);
  useEffect(() => engine?.setTierFocus(focus), [engine, focus]);
  useEffect(() => engine?.setRadar(radar, true), [engine, radar]);
  useEffect(() => engine?.setFlood(flood), [engine, flood]);
  useEffect(() => engine?.setHeroPlace(heroPreset?.at ?? null), [engine, heroPreset]);
  useEffect(() => engine?.setLadder(ladder.grower, ladder.tiers.map((t) => t.sell)), [engine, ladder]);

  const anchors = useMemo(() => {
    const plotAt: LatLon = heroPreset?.at ?? PLACES.rahimPlot;
    const town = (heroPreset?.place ?? "Mithapukur, Rangpur").split(",")[0];
    const who = !heroPreset || heroPreset.farmer === "Rahim Mia" ? "Rahim's plot" : heroPreset.farmer === "A farmer" ? "A farmer's field" : `${heroPreset.farmer}'s field`;
    const routeAt = (t: number): LatLon => engine?.routeLatLon(t) ?? PLACES.mithapukur;
    const stopAt = (at: number | LatLon): LatLon => (typeof at === "number" ? routeAt(at) : at);
    const list: { key: string; at: LatLon; alt?: number; ch: number[]; alert?: boolean; follow?: boolean; body: ReactNode }[] = [
      { key: "plot", at: plotAt, alt: 0.02, ch: [0, 3, 6], body: <>{who}, {town}</> },
      { key: "ring", at: { lat: plotAt.lat + 0.032, lon: plotAt.lon + 0.036 }, ch: [0], body: "5 km union ring" },
      ...FACILITIES.filter((f) => f.district === district).map((f) => ({
        key: f.id, at: f.at, alt: (f.capacityMt / 12000) * 0.42 + 0.04, ch: [1], body: f.name,
      })),
    ];
    if (mode === "syndicate") {
      list.push({ key: "gate", at: routeAt(0), alt: ladder.grower * 0.012 + 0.06, ch: [2], body: <>Farm gate <b>{tk(ladder.grower)}</b></> });
      TIER_STOPS.forEach((stop, i) => {
        const tier = ladder.tiers[i];
        if (tier) list.push({ key: stop.tier, at: stopAt(stop.at), alt: tier.sell * 0.012 + 0.06, ch: [2], alert: true, body: <>{tier.tier} <b>{tk(tier.sell)}</b></> });
      });
    } else {
      list.push({ key: "depot", at: PLACES.mirpur, ch: [2], body: <>Mirpur supermarket depot <b>{tk(rahim.b2bNet)} to Rahim</b></> });
      if (rahim.pool) list.push({ key: "pool", at: routeAt(0), follow: true, ch: [2], body: <>Union truck <b>{kg(rahim.pool.after)} of {kg(rahim.pool.capacity)}</b></> });
    }
    list.push(
      { key: "dhaka", at: PLACES.karwanBazar, ch: [3], body: "Karwan Bazar, Dhaka" },
      { key: "tanguar", at: HAOR_BASINS[0].at, ch: [4], body: "Tanguar haor" },
      { key: "abdul", at: PLACES.abdulFields, ch: [4], alert: flood > 0.5, body: <>Abdul's fields, Tahirpur{flood > 0.5 && <b> harvest now</b>}</> },
      { key: "sunamganj", at: PLACES.sunamganj, ch: [4], body: "Sunamganj" },
      ...DISTRICT_LABELS.map((d) => ({ key: `d-${d.name}`, at: d.at, ch: [5], body: d.name })),
    );
    return list;
  }, [engine, heroPreset, district, mode, ladder, rahim, flood]);

  useEffect(() => engine?.refreshLabels(), [engine, anchors]);

  // Deep links such as /#story-road open at that chapter.
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (CHAPTERS.some((c) => c.id === hash)) requestAnimationFrame(() => document.getElementById(hash)?.scrollIntoView());
  }, []);

  const dragRadar = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragging.current || !stageRef.current) return;
    const rect = stageRef.current.getBoundingClientRect();
    setRadar(Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)));
  };

  const jump = (index: number) => {
    sections.current[index]?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth" });
  };

  return (
    <div className="relative">
      <TopBar overlay coordsRef={coordsRef} />

      <div ref={stageRef} className="story-stage">
        {webgl ? <canvas ref={canvasRef} aria-hidden /> : <MosaicSvg highlight className="absolute inset-0 h-full w-full" />}
        <div className="story-scrim" aria-hidden />
        <div ref={labelsRef} className="pointer-events-none absolute inset-0" aria-hidden>
          {webgl && anchors.map((a) => (
            <Anchor key={a.key} lat={a.at.lat} lon={a.at.lon} alt={a.alt} chapters={a.ch} alert={a.alert} followTruck={a.follow}>{a.body}</Anchor>
          ))}
        </div>
        {webgl && active === 4 && (
          <div className="radar-handle" style={{ left: `${radar * 100}%` }} aria-hidden
            onPointerDown={(e) => {
              dragging.current = true;
              e.currentTarget.setPointerCapture(e.pointerId);
            }}
            onPointerMove={dragRadar}
            onPointerUp={() => {
              dragging.current = false;
            }}>
            <span><MoveHorizontal className="size-4" /></span>
          </div>
        )}
      </div>

      <main className="pointer-events-none relative z-10">
        <section id={CHAPTERS[0].id} ref={(el) => {
          sections.current[0] = el;
        }} aria-label="Rahim's question"
          className="flex min-h-[100svh] flex-col justify-center px-4 pt-[46svh] pb-16 sm:px-8 md:pt-28 lg:px-12">
          <div className="pointer-events-auto">
            <Hero rahim={facts.rahim} onPreset={setHeroPreset} />
          </div>
        </section>
        <Chapter index={1} sectionRef={(el) => { sections.current[1] = el; }}>
          <ColdChapter district={district} onDistrict={setDistrict} />
        </Chapter>
        <Chapter index={2} sectionRef={(el) => { sections.current[2] = el; }}>
          <RoadChapter ladder={facts.ladder} rahim={facts.rahim} mode={mode} onMode={setMode} focus={focus} onFocus={setFocus} />
        </Chapter>
        <Chapter index={3} sectionRef={(el) => { sections.current[3] = el; }}>
          <AnswerChapter rahim={facts.rahim} />
        </Chapter>
        <Chapter index={4} sectionRef={(el) => { sections.current[4] = el; }}>
          <HaorChapter abdul={facts.abdul} radar={radar} onRadar={setRadar} onFlood={setFlood} />
        </Chapter>
        <Chapter index={5} sectionRef={(el) => { sections.current[5] = el; }}>
          <AgentsChapter />
        </Chapter>
        <Chapter index={6} tall={false} sectionRef={(el) => { sections.current[6] = el; }}>
          <DawnChapter />
        </Chapter>
      </main>

      <nav aria-label="Chapters" className="fixed top-1/2 right-6 z-20 hidden -translate-y-1/2 lg:block">
        <ol className="m-0 grid list-none gap-3.5 p-0">
          {CHAPTERS.slice(1).map((chapter, i) => {
            const index = i + 1;
            const current = active === index;
            return (
              <li key={chapter.id}>
                <a href={`#${chapter.id}`} aria-current={current ? "step" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    jump(index);
                  }}
                  className="group flex items-center justify-end gap-3 text-[15px] text-slate-400 no-underline">
                  <span className={cn("label translate-x-1.5 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100",
                    current && "text-slate-200")}>{chapter.title}</span>
                  <b className={cn("grid size-[30px] place-items-center rounded-full border font-medium",
                    current ? "border-mustard-400 text-mustard-400" : "border-slate-400/35")}>{bnDigits(index)}</b>
                </a>
              </li>
            );
          })}
        </ol>
      </nav>
    </div>
  );
}
