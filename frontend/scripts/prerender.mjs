// Build-time static generation, run after `vite build`: writes /team/ and /guide/ (each also in Bangla, under bn/),
// /team/team.json (the mobile app reads it), sitemap.xml and robots.txt into dist/.
// Why this and not a framework: moving the SPA to Next.js or Astro the day before judging would put every working route
// at risk, while two content pages only need complete HTML at build time. They are rendered from the same JSON the SPA
// reads (src/data/*.json), need no JavaScript, and serve.py and nginx already serve dist/team/index.html at /team/.

import assert from "node:assert/strict";
import { copyFileSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { ArrowRight, BriefcaseBusiness, Download, GitBranch, Globe, Mail, MessageCircle } from "lucide-react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const read = (path) => JSON.parse(readFileSync(join(root, path), "utf8"));
const team = read("src/data/team.json");
const guide = read("src/data/guide.json");
const site = read("src/data/site.json");
const ORIGIN = site.origin;
const today = new Date().toISOString().slice(0, 10);

const esc = (text) => String(text).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
// The same lucide icons the SPA uses, as inline SVG.
const icon = (Icon, size = 16) => renderToStaticMarkup(createElement(Icon, { size, "aria-hidden": true }));
const bnDigits = (value) => String(value).replace(/[0-9]/g, (d) => "০১২৩৪৫৬৭৮৯"[Number(d)]);

// The SPA's self-hosted Anek Bangla faces (hashed /assets/ files), so these pages use the same type at no extra cost.
const builtCss = readdirSync(join(dist, "assets")).filter((f) => f.endsWith(".css")).map((f) => readFileSync(join(dist, "assets", f), "utf8")).join("");
const fontFaces = (builtCss.match(/@font-face\{[^}]*\}/g) ?? []).filter((rule) => rule.includes("Anek Bangla")).join("");

const WORDMARK = `<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="5" fill="#047857"/><rect x="6" y="6" width="5" height="12" rx="1.2" fill="#ecfdf5"/><rect x="13" y="6" width="5" height="5" rx="1.2" fill="#fbbf24"/><rect x="13" y="13" width="5" height="5" rx="1.2" fill="#7dd3fc"/></svg>`;
const FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect x='2' y='2' width='20' height='20' rx='5' fill='%23047857'/%3E%3Crect x='6' y='6' width='5' height='12' rx='1.2' fill='%23ecfdf5'/%3E%3Crect x='13' y='6' width='5' height='5' rx='1.2' fill='%23fbbf24'/%3E%3Crect x='13' y='13' width='5' height='5' rx='1.2' fill='%237dd3fc'/%3E%3C/svg%3E";

// Design tokens from src/index.css: canvas, white surfaces, emerald brand, slate text.
const CSS = `
:root{--canvas:#f6f8f5;--em7:#047857;--em8:#065f46;--em50:#ecfdf5;--s9:#0f172a;--s7:#334155;--s6:#475569;--s5:#64748b;--s3:#cbd5e1;--s2:#e2e8f0;--s1:#f1f5f9;--card:0 1px 3px rgba(15,23,42,.04),0 8px 24px -4px rgba(15,23,42,.06)}
*{box-sizing:border-box}
html{background:var(--canvas);scrollbar-color:var(--s3) transparent}
body{margin:0;background:var(--canvas);color:var(--s9);font:15px/1.55 "Anek Bangla Variable","Anek Bangla",system-ui,sans-serif;font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}
[lang=bn]{line-height:1.7}
a{color:var(--em7);text-underline-offset:3px}
a:hover{color:var(--em8)}
:focus-visible{outline:2px solid var(--em7);outline-offset:2px}
::selection{background:#d1fae5;color:#064e3b}
svg{flex-shrink:0}
.wrap{max-width:1280px;margin:0 auto;padding:0 16px}
@media (min-width:640px){.wrap{padding:0 24px}}
.skip{position:absolute;left:-9999px;top:8px;z-index:20;background:#fff;padding:10px 14px;border-radius:8px}
.skip:focus{left:16px}
.top{position:sticky;top:0;z-index:10;background:rgba(255,255,255,.88);backdrop-filter:blur(12px);border-bottom:1px solid rgba(226,232,240,.8)}
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:0 12px;padding-top:6px;padding-bottom:6px}
.brand{display:inline-flex;align-items:center;gap:8px;min-height:44px;color:var(--s9);text-decoration:none;font-size:16px;font-weight:600;letter-spacing:-.01em}
.brand b{color:var(--em7);font-weight:600}
.bar nav{order:3;display:flex;flex-wrap:wrap;gap:2px;width:100%;margin:0 -10px}
.bar nav a,.lang{display:inline-flex;align-items:center;min-height:44px;padding:0 10px;border-radius:8px;color:var(--s6);text-decoration:none;font-size:14px;font-weight:500;white-space:nowrap}
.bar nav a:hover,.lang:hover{color:var(--s9);background:var(--s1)}
.bar nav a[aria-current=page]{color:var(--s9);background:#fff;box-shadow:inset 0 0 0 1px var(--s2)}
.lang{margin-left:auto;box-shadow:inset 0 0 0 1px var(--s3);background:#fff;color:var(--s7)}
@media (min-width:860px){.bar nav{order:0;width:auto;margin:0 auto}.lang{margin-left:0}}
main{padding-bottom:64px}
h1{margin:40px 0 0;font-size:clamp(30px,4.2vw,46px);line-height:1.1;letter-spacing:-.025em;font-weight:600}
[lang=bn] h1,[lang=bn] h2{letter-spacing:0;line-height:1.32}
h2{margin:0;font-size:24px;line-height:1.25;letter-spacing:-.02em;font-weight:600}
.lede{margin:12px 0 0;max-width:46rem;color:var(--s6);font-size:17px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:32px 0 0;padding:0}
@media (min-width:768px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (min-width:1280px){.grid{grid-template-columns:repeat(6,minmax(0,1fr))}}
.card{display:flex;flex-direction:column;min-width:0;overflow:hidden;background:#fff;border:1px solid var(--s2);border-radius:12px;box-shadow:var(--card)}
.card img{display:block;width:100%;height:auto;aspect-ratio:4/5;object-fit:cover;background:var(--s1)}
.card .body{display:flex;flex:1;flex-direction:column;padding:14px}
.card h3{margin:0;font-size:16px;line-height:1.35;font-weight:600}
.card .role{margin:2px 0 0;font-size:13px;font-weight:500;color:var(--em8)}
.card .bio{margin:8px 0 0;font-size:13px;line-height:1.6;color:var(--s6)}
.links{display:flex;flex-wrap:wrap;gap:4px;list-style:none;margin:auto 0 0 -8px;padding:8px 0 0}
.links a{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 8px;border-radius:8px;color:var(--s7);text-decoration:none;font-size:13px;font-weight:500}
.links a:hover{background:var(--s1);color:var(--s9)}
.panel{margin-top:48px;padding:20px;background:#fff;border:1px solid var(--s2);border-radius:12px;box-shadow:var(--card)}
.panel p{margin:8px 0 0;max-width:48rem;color:var(--s6)}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:4px 16px;margin-top:16px}
.btn{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;border-radius:8px;background:var(--em7);color:#fff;text-decoration:none;font-size:15px;font-weight:600;box-shadow:0 1px 2px rgba(15,23,42,.08)}
.btn:hover{background:var(--em8);color:#fff}
.btn.quiet{background:#fff;color:var(--s9);box-shadow:inset 0 0 0 1px var(--s3)}
.btn.quiet:hover{background:var(--s1)}
.meta{color:var(--s6);font-size:13px}
.inline{display:inline-flex;align-items:center;gap:6px;min-height:44px;font-weight:600;text-decoration:none}
footer{border-top:1px solid var(--s2);background:#fff}
footer .wrap{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 24px;padding-top:20px;padding-bottom:20px;font-size:13px;color:var(--s5)}
footer p{margin:0;max-width:60rem}
footer nav{display:flex;flex-wrap:wrap;gap:0 20px}
footer nav a{display:inline-flex;align-items:center;gap:4px;min-height:44px;color:var(--s7);font-weight:500;text-decoration:none}
footer nav a:hover{color:var(--s9)}
`;

const GUIDE_CSS = `
.guide{display:grid;gap:0 48px;align-items:start}
@media (min-width:1024px){.guide{grid-template-columns:240px minmax(0,1fr)}.toc{position:sticky;top:80px;grid-row:1/span 2}}
.guide header{grid-column:-2/-1;border-bottom:1px solid var(--s2);padding-bottom:24px}
.toc h2{margin:24px 0 8px;font-size:13px;letter-spacing:0;color:var(--s9)}
.toc ol{list-style:none;margin:0;padding:0;border-left:1px solid var(--s2)}
.toc a{display:flex;align-items:center;min-height:40px;padding:4px 16px;margin-left:-1px;border-left:2px solid transparent;color:var(--s6);text-decoration:none;font-size:14px;font-weight:500}
.toc a:hover{color:var(--s9);border-left-color:var(--s3)}
.content{grid-column:-2/-1;max-width:760px}
.content section{padding-top:40px;scroll-margin-top:72px}
.content p,.content li,.content dd{color:var(--s7);font-size:16px}
.content p{margin:12px 0 0}
.content ol,.content ul{margin:12px 0 0;padding-left:24px}
.content li{margin:8px 0 0;padding-left:4px}
.content li::marker{color:var(--em7);font-weight:600}
.faq{margin:4px 0 0}
.faq dt{margin:20px 0 0;font-weight:600;font-size:16px}
.faq dd{margin:4px 0 0}
@media print{
  .top,.toc,footer,.skip,.actions,.no-print{display:none!important}
  html,body{background:#fff}
  body{color:#000;font-size:11pt}
  .guide{display:block}
  .content{max-width:none}
  .content section{padding-top:16px;break-inside:avoid-page}
  .content p,.content li,.content dd{color:#000;font-size:11pt}
  a{color:#000}
  .content a[href^="http"]::after,.content a[href^="/"]::after{content:" (" attr(href) ")";font-size:9pt;color:#444}
  h1{margin-top:0;font-size:22pt}
}
`;

const COPY = {
  en: {
    skip: "Skip to content", other: "বাংলা", otherLang: "bn",
    nav: { home: "Overview", docs: "Whitepaper", guide: "User guide", team: "Team" },
    app: "Get the Android app", appMeta: `About ${site.apk_size_mb} MB · Android ${site.android_min} or newer`, older: "For older phones (32-bit)",
    congress: "International AI Builders Congress 2026 · AgriSphere AI → FarmMarket · Showcase on 26 December 2026 at Daffodil International University.",
    open: "Open KrishiNexus OS",
    teamTitle: "Team Heat Wave · the people behind KrishiNexus OS",
    teamLede: "The people building KrishiNexus OS: five builders in Bangladesh and an advisor who joins online.",
    teamDescription: "Team Heat Wave builds KrishiNexus OS, an AI system that helps Bangladeshi farmers sell at a fair price, find cold storage and harvest before floods.",
    aboutTitle: "What we are building",
    about: "KrishiNexus OS listens to a farmer's question in their own dialect and answers with a decision: grade the crop, sell on a shared truck past the middlemen, keep it in cold storage with credit, or harvest before a flood. Buyers bid in the open, drivers deliver, and the bank holds the payment until delivery.",
    portrait: (name) => `Portrait of ${name}`, on: (name, network) => `${name} on ${network}`,
    guideDescription: "How to use KrishiNexus, step by step, for farmers, buyers, truck drivers, co-ops, cold stores and banks: accounts and data, live tracking, and the Android app.",
  },
  bn: {
    skip: "মূল অংশে যান", other: "English", otherLang: "en",
    nav: { home: "সারসংক্ষেপ", docs: "শ্বেতপত্র", guide: "ব্যবহার নির্দেশিকা", team: "দল" },
    app: "অ্যান্ড্রয়েড অ্যাপ নিন", appMeta: `প্রায় ${bnDigits(site.apk_size_mb)} এমবি · অ্যান্ড্রয়েড ${bnDigits(site.android_min)} বা নতুন`, older: "পুরোনো ফোনের জন্য (৩২-বিট)",
    congress: "ইন্টারন্যাশনাল এআই বিল্ডার্স কংগ্রেস ২০২৬ · এগ্রিস্ফিয়ার এআই → ফার্মমার্কেট · প্রদর্শনী ২৬ ডিসেম্বর ২০২৬, ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি।",
    open: "কৃষিনেক্সাস ওএস খুলুন",
    teamTitle: "টিম হিট ওয়েভ · কৃষিনেক্সাস ওএসের পেছনের মানুষেরা",
    teamLede: "কৃষিনেক্সাস ওএস যাঁরা তৈরি করছেন: বাংলাদেশে পাঁচজন নির্মাতা, আর অনলাইনে যুক্ত একজন উপদেষ্টা।",
    teamDescription: "টিম হিট ওয়েভ কৃষিনেক্সাস ওএস তৈরি করছে: একটি এআই ব্যবস্থা, যা বাংলাদেশের কৃষককে ন্যায্য দামে বেচতে, হিমাগারে জায়গা পেতে আর বন্যার আগে ফসল তুলতে সাহায্য করে।",
    aboutTitle: "আমরা যা তৈরি করছি",
    about: "কৃষিনেক্সাস ওএস কৃষকের নিজের ভাষায় প্রশ্ন শোনে আর সিদ্ধান্ত দেয়: ফসল গ্রেড, মধ্যস্বত্বভোগী এড়িয়ে যৌথ ট্রাকে বিক্রি, ঋণসহ হিমাগারে রাখা, বা বন্যার আগে ধান কাটা। ক্রেতারা খোলাখুলি দর দেন, চালক পৌঁছে দেন, আর ডেলিভারি পর্যন্ত ব্যাংক টাকা আটকে রাখে।",
    portrait: (name) => `${name}-এর প্রতিকৃতি`, on: (name, network) => `${network}-এ ${name}`,
    guideDescription: "কৃষিনেক্সাস ধাপে ধাপে ব্যবহারের নিয়ম: কৃষক, ক্রেতা, ট্রাকচালক, সমবায়, হিমাগার ও ব্যাংকের জন্য; অ্যাকাউন্ট ও তথ্য, লাইভ ট্র্যাকিং আর অ্যান্ড্রয়েড অ্যাপ।",
  },
};

const LINKS = {
  github: { icon: GitBranch, label: "GitHub" },
  linkedin: { icon: BriefcaseBusiness, label: "LinkedIn" },
  facebook: { icon: MessageCircle, label: "Facebook" },
  website: { icon: Globe, label: "Website" },
  email: { icon: Mail, label: "Email" },
};

/** /team/ and /team/bn/ (or the guide's pair): English at the base path, Bangla under bn/. */
const pathFor = (base, lang) => (lang === "bn" ? `${base}bn/` : base);

function page({ lang, base, current, title, description, jsonLd = "", css = "", main }) {
  const c = COPY[lang];
  const url = `${ORIGIN}${pathFor(base, lang)}`;
  const image = `${ORIGIN}/icons/Icon-512.png`;
  const nav = [["/", c.nav.home], ["/docs", c.nav.docs], [pathFor("/guide/", lang), c.nav.guide], [pathFor("/team/", lang), c.nav.team]];
  return `<!doctype html>
<html lang="${lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
<link rel="canonical" href="${url}">
<link rel="alternate" hreflang="en" href="${ORIGIN}${base}">
<link rel="alternate" hreflang="bn" href="${ORIGIN}${base}bn/">
<link rel="alternate" hreflang="x-default" href="${ORIGIN}${base}">
<meta name="theme-color" content="#047857">
<link rel="icon" type="image/svg+xml" href="${FAVICON}">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icons/Icon-192.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="KrishiNexus OS">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${image}">
<meta property="og:locale" content="${lang === "bn" ? "bn_BD" : "en_US"}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="${esc(title)}">
<meta name="twitter:description" content="${esc(description)}">
<meta name="twitter:image" content="${image}">
${jsonLd ? `<script type="application/ld+json">${jsonLd}</script>\n` : ""}<style>${fontFaces}${CSS}${css}</style>
</head>
<body>
<a class="skip" href="#main">${esc(c.skip)}</a>
<header class="top"><div class="wrap bar">
<a class="brand" href="/" aria-label="KrishiNexus OS, overview">${WORDMARK}<span>KrishiNexus <b>OS</b></span></a>
<nav aria-label="Main">${nav.map(([href, label]) => `<a href="${href}"${href === pathFor(current, lang) ? ' aria-current="page"' : ""}>${esc(label)}</a>`).join("")}</nav>
<a class="lang" href="${pathFor(base, c.otherLang)}" hreflang="${c.otherLang}" lang="${c.otherLang}">${c.other}</a>
</div></header>
<main id="main" class="wrap">
${main}
</main>
<footer><div class="wrap">
<p>${esc(c.congress)}</p>
<nav aria-label="Footer"><a href="/">${esc(c.nav.home)}</a><a href="/docs">${esc(c.nav.docs)}</a><a href="${pathFor("/guide/", lang)}">${esc(c.nav.guide)}</a><a href="${site.apk}">${esc(c.app)}</a></nav>
</div></footer>
</body>
</html>
`;
}

const appButtons = (lang) => {
  const c = COPY[lang];
  return `<div class="actions"><a class="btn" href="${site.apk}">${icon(Download)} ${esc(c.app)}</a><span class="meta">${esc(c.appMeta)} · <a class="inline" href="${site.apk_armv7}">${esc(c.older)}</a></span></div>`;
};

function teamPage(lang) {
  const c = COPY[lang];
  const other = lang === "bn" ? "en" : "bn";
  const cards = team.members.map((m) => {
    const name = m.name[lang];
    const links = m.links.map((link) => {
      const kind = LINKS[link.type] ?? LINKS.website;
      return `<li><a href="${esc(link.url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(c.on(name, kind.label))}">${icon(kind.icon)} ${kind.label}</a></li>`;
    }).join("");
    return `<article class="card">
<img src="${m.photo_small}" srcset="${m.photo_small} 320w, ${m.photo} 640w" sizes="(min-width: 1280px) 192px, (min-width: 768px) 30vw, 46vw" width="640" height="800" loading="lazy" decoding="async" alt="${esc(c.portrait(name))}">
<div class="body"><h3>${esc(name)}</h3><p class="role">${esc(m.role[lang])}</p><p class="bio">${esc(m.bio[lang])}</p>${links ? `<ul class="links">${links}</ul>` : ""}</div>
</article>`;
  }).join("\n");
  const jsonLd = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Organization",
    name: team.team,
    url: `${ORIGIN}/team/`,
    description: c.teamDescription,
    member: team.members.map((m) => ({
      "@type": "Person",
      name: m.name[lang],
      alternateName: m.name[other],
      jobTitle: m.role[lang],
      image: `${ORIGIN}${m.photo}`,
      sameAs: m.links.map((link) => link.url),
    })),
  }).replace(/</g, "\\u003c");
  const main = `<section aria-labelledby="team-heading">
<h1 id="team-heading">${esc(lang === "bn" ? "টিম হিট ওয়েভ" : team.team)}</h1>
<p class="lede">${esc(c.teamLede)}</p>
<div class="grid">
${cards}
</div>
</section>
<section class="panel" aria-labelledby="about-heading">
<h2 id="about-heading">${esc(c.aboutTitle)}</h2>
<p>${esc(c.about)}</p>
<div class="actions"><a class="btn quiet" href="/">${esc(c.open)} ${icon(ArrowRight)}</a></div>
${appButtons(lang)}
</section>`;
  return page({ lang, base: "/team/", current: "/team/", title: c.teamTitle, description: c.teamDescription, jsonLd, main });
}

function guidePage(lang) {
  const c = COPY[lang];
  const g = guide[lang];
  const block = (b) => {
    if (b.p) return `<p>${esc(b.p)}</p>`;
    if (b.ul) return `<ul>${b.ul.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`;
    if (b.ol) return `<ol>${b.ol.map((item) => `<li>${esc(item)}</li>`).join("")}</ol>`;
    if (b.faq) return `<dl class="faq">${b.faq.map((f) => `<dt>${esc(f.q)}</dt><dd>${esc(f.a)}</dd>`).join("")}</dl>`;
    if (b.link) return `<p><a class="inline" href="${esc(b.link.href)}">${esc(b.link.text)} ${icon(ArrowRight)}</a></p>`;
    if (b.app) return appButtons(lang);
    throw new Error(`Unknown guide block: ${JSON.stringify(b)}`);
  };
  const main = `<article class="guide">
<header><h1>${esc(g.title)}</h1><p class="lede">${esc(g.lede)}</p><p class="meta">${esc(g.updated)} ${guide.updated}</p></header>
<nav class="toc" aria-labelledby="toc-heading"><h2 id="toc-heading">${esc(g.contents)}</h2><ol>${g.sections.map((s) => `<li><a href="#${s.id}">${esc(s.title)}</a></li>`).join("")}</ol></nav>
<div class="content">
${g.sections.map((s) => `<section id="${s.id}" aria-labelledby="${s.id}-heading"><h2 id="${s.id}-heading">${esc(s.title)}</h2>${s.blocks.map(block).join("")}</section>`).join("\n")}
</div>
</article>`;
  return page({ lang, base: "/guide/", current: "/guide/", title: `${g.title} · KrishiNexus OS`, description: c.guideDescription, css: GUIDE_CSS, main });
}

const written = {};
function write(rel, text) {
  mkdirSync(dirname(join(dist, rel)), { recursive: true });
  writeFileSync(join(dist, rel), text);
  written[rel] = text;
}

for (const lang of ["en", "bn"]) {
  write(`${pathFor("team/", lang)}index.html`, teamPage(lang));
  write(`${pathFor("guide/", lang)}index.html`, guidePage(lang));
}
copyFileSync(join(root, "src/data/team.json"), join(dist, "team/team.json"));

const pages = [["/", null], ["/docs", null], ["/signup", null], ["/team/", "/team/bn/"], ["/guide/", "/guide/bn/"]];
const alternates = (en, bn) => (bn
  ? `<xhtml:link rel="alternate" hreflang="en" href="${ORIGIN}${en}"/><xhtml:link rel="alternate" hreflang="bn" href="${ORIGIN}${bn}"/>`
  : "");
write("sitemap.xml", `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${pages.flatMap(([en, bn]) => (bn ? [en, bn] : [en]).map((loc) => `<url><loc>${ORIGIN}${loc}</loc><lastmod>${today}</lastmod>${alternates(en, bn)}</url>`)).join("\n")}
</urlset>
`);
write("robots.txt", `User-agent: *
Allow: /
Disallow: /os
Disallow: /admin
Disallow: /api/

Sitemap: ${ORIGIN}/sitemap.xml
`);

// Self-check: every page is complete, the structured data parses, and nothing rendered "undefined".
for (const [rel, html] of Object.entries(written).filter(([rel]) => rel.endsWith(".html"))) {
  for (const needle of ["<h1", 'rel="canonical"', 'property="og:title"', 'href="/"', 'href="/docs"', site.apk]) assert.ok(html.includes(needle), `${rel} lacks ${needle}`);
  assert.ok(!/undefined|\[object Object\]/.test(html), `${rel} rendered a missing value`);
}
for (const lang of ["en", "bn"]) {
  const html = written[`${pathFor("team/", lang)}index.html`];
  const ld = JSON.parse(html.match(/<script type="application\/ld\+json">(.*?)<\/script>/s)[1]);
  assert.equal(ld["@type"], "Organization");
  assert.equal(ld.member.length, team.members.length);
  assert.equal((html.match(/<article class="card">/g) ?? []).length, team.members.length);
}
assert.ok(fontFaces.includes("Anek Bangla"), "no Anek Bangla @font-face found in dist/assets");
assert.deepEqual(JSON.parse(readFileSync(join(dist, "team/team.json"), "utf8")), team);
console.log(`prerender: ${Object.keys(written).length} files and team/team.json written to dist/`);
