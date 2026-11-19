import { useEffect, useState, type ReactNode } from "react";

import { cn } from "../lib/format";

/**
 * A captioned video that loads nothing until played (poster, native controls, preload none, no autoplay). The files
 * arrive separately in public/video/, so the block stays hidden until a HEAD request finds a real video there: a
 * missing file comes back 404, or as the SPA's index.html, never as video/*.
 */
export function LandingVideo({ name, label, title, children, className }: {
  /** public/video/<name>.mp4, with <name>.jpg (poster) and <name>.en.vtt (English captions) beside it. */
  name: string;
  /** Accessible name of the player. */
  label: string;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const src = `/video/${name}.mp4`;
  const [present, setPresent] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(src, { method: "HEAD" })
      .then((r) => alive && setPresent(r.ok && (r.headers.get("content-type") ?? "").startsWith("video/")))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [src]);

  if (!present) return null;
  return (
    <figure className={cn("m-0 min-w-0", className)}>
      {title}
      <video controls preload="none" playsInline poster={`/video/${name}.jpg`} aria-label={label}
        className="aspect-video w-full rounded-xl bg-slate-900 shadow-card ring-1 ring-slate-200">
        <source src={src} type="video/mp4" />
        <track kind="captions" src={`/video/${name}.en.vtt`} srcLang="en" label="English" default />
      </video>
      {children && <figcaption className="mt-2 text-[13px] text-slate-600">{children}</figcaption>}
    </figure>
  );
}
