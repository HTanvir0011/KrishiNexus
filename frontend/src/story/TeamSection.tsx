import { ArrowRight, BriefcaseBusiness, GitBranch, Globe, Mail, MessageCircle, type LucideIcon } from "lucide-react";

import team from "../data/team.json";
import { useCopy } from "../lib/i18n";
import { useAppState } from "../state/store";

type LinkType = "github" | "linkedin" | "facebook" | "website" | "email";
// lucide has no brand marks, so each network gets a plain glyph plus its name in words.
const LINK: Record<LinkType, { icon: LucideIcon; label: string }> = {
  github: { icon: GitBranch, label: "GitHub" },
  linkedin: { icon: BriefcaseBusiness, label: "LinkedIn" },
  facebook: { icon: MessageCircle, label: "Facebook" },
  website: { icon: Globe, label: "Website" },
  email: { icon: Mail, label: "Email" },
};

const COPY = {
  en: {
    title: team.team,
    lede: "The people building KrishiNexus OS: five builders in Bangladesh and an advisor who joins online.",
    portrait: (name: string) => `Portrait of ${name}`,
    on: (name: string, network: string) => `${name} on ${network}`,
    page: "Open the team page",
  },
  bn: {
    title: "টিম হিট ওয়েভ",
    lede: "কৃষিনেক্সাস ওএস যাঁরা তৈরি করছেন: বাংলাদেশে পাঁচজন নির্মাতা, আর অনলাইনে যুক্ত একজন উপদেষ্টা।",
    portrait: (name: string) => `${name}-এর প্রতিকৃতি`,
    on: (name: string, network: string) => `${network}-এ ${name}`,
    page: "দলের পাতা খুলুন",
  },
};

/** The team from src/data/team.json (also the source of the pre-rendered /team/ page and the mobile app's team screen). */
export function TeamSection() {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  return (
    <section aria-labelledby="team-heading" className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-[1280px] px-4 py-16 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <h2 id="team-heading" lang={lang} className="m-0 text-[28px] font-semibold tracking-[-0.02em] text-slate-900">{c.title}</h2>
            <p className="m-0 mt-2 max-w-[44rem] text-[15px] text-slate-600">{c.lede}</p>
          </div>
          {/* A real page load: /team/ is a static page written at build time (scripts/prerender.mjs). */}
          <a href={lang === "bn" ? "/team/bn/" : "/team/"} className="inline-flex min-h-11 items-center gap-1.5 text-[14px] font-semibold text-emerald-700 no-underline hover:text-emerald-800">
            {c.page} <ArrowRight className="size-4" aria-hidden />
          </a>
        </div>
        <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          {team.members.map((member) => {
            const name = member.name[lang];
            return (
              <article key={member.slug} lang={lang} className="surface flex min-w-0 flex-col overflow-hidden">
                <img src={member.photo_small} srcSet={`${member.photo_small} 320w, ${member.photo} 640w`}
                  sizes="(min-width: 1280px) 192px, (min-width: 768px) 30vw, 46vw" width={640} height={800}
                  loading="lazy" decoding="async" alt={c.portrait(name)} className="aspect-[4/5] w-full bg-slate-100 object-cover" />
                <div className="flex flex-1 flex-col p-3.5">
                  <h3 className="m-0 text-[16px] leading-snug font-semibold text-slate-900">{name}</h3>
                  <p className="m-0 mt-0.5 text-[13px] font-medium text-emerald-800">{member.role[lang]}</p>
                  <p className="m-0 mt-2 text-[13px] leading-relaxed text-slate-600">{member.bio[lang]}</p>
                  {member.links.length > 0 && (
                    <ul className="m-0 mt-auto -ml-2 flex list-none flex-wrap gap-1 p-0 pt-2">
                      {member.links.map((link) => {
                        const kind = LINK[link.type as LinkType] ?? LINK.website;
                        return (
                          <li key={link.url}>
                            <a href={link.url} target="_blank" rel="noopener noreferrer" aria-label={c.on(name, kind.label)}
                              className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-[13px] font-medium text-slate-700 no-underline hover:bg-slate-100 hover:text-slate-900">
                              <kind.icon className="size-4" aria-hidden /> {kind.label}
                            </a>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
