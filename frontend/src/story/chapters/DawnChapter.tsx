import { Link } from "../../lib/router";
import { ChapterHeading, storyButtonClass } from "../parts";
import { TEAM } from "../presets";

export function DawnChapter() {
  return (
    <>
      <ChapterHeading index={6}>Open the OS</ChapterHeading>
      <p className="text-[18px] leading-relaxed text-slate-200">
        Everything on this page came from the agents running right now. The same agents run the operating system that farmers, cooperatives,
        cold-store managers and lenders use: the farmer's phone, the co-op's command center and the bank's credit desk.
      </p>
      <div className="mt-7 flex flex-wrap gap-3">
        <Link to="/os" className={storyButtonClass("primary")}>Open the live OS</Link>
        <Link to="/docs" className={storyButtonClass("ghost")}>Read the whitepaper</Link>
      </div>

      <h3 className="wide mt-16 mb-5 text-[24px] text-slate-50">The team</h3>
      <ul className="m-0 grid list-none gap-x-8 gap-y-5 p-0 sm:grid-cols-2">
        {TEAM.map((member) => (
          <li key={member.name}>
            <span className="block text-[17px] font-semibold text-slate-50">{member.name}</span>
            <span className="block text-[15px] text-slate-400">{member.role}</span>
            <span className="label block text-[13px] text-slate-500">{member.country}</span>
          </li>
        ))}
      </ul>
      <p className="label mt-14 text-[13px] leading-relaxed text-slate-500">
        Built for the International AI Builders Congress 2026, AgriSphere AI track. Showcase on 26 December 2026 at Daffodil International
        University.
      </p>
    </>
  );
}
