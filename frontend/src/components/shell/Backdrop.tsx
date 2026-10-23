import { MosaicSvg } from "../MosaicSvg";

/** The story's delta, frozen at dawn and frosted, behind the OS and whitepaper glass. */
export function Backdrop() {
  return (
    <div className="pointer-events-none fixed inset-0" aria-hidden>
      <MosaicSvg className="h-full w-full scale-110 blur-[14px] saturate-[0.9]" />
      <div className="absolute inset-0 bg-gradient-to-b from-ink-900/60 via-ink-900/70 to-ink-900/85" />
      <div className="absolute inset-x-0 bottom-0 h-2/3 bg-[radial-gradient(80%_60%_at_70%_100%,rgb(237_183_35/0.08),transparent_70%)]" />
    </div>
  );
}
