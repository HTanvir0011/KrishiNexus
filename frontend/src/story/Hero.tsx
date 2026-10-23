import { ChevronDown, Keyboard, Languages, Volume2, X } from "lucide-react";
import { Fragment, useMemo, useState, type CSSProperties, type FormEvent } from "react";

import { api, ApiError, type VoiceInteractResponse } from "../api/client";
import { kg, tk } from "../lib/format";
import { Link } from "../lib/router";
import { speak } from "../lib/speech";
import { englishSummary } from "../lib/summary";
import { setState } from "../state/store";
import type { RahimFacts, Sourced } from "./data";
import { StoryButton, Waveform } from "./parts";
import { RAHIM, STORY_PRESETS, type StoryPreset } from "./presets";

interface Asked {
  preset: StoryPreset | null;
  question: string;
  result: VoiceInteractResponse | null;
  live: boolean;
  error?: string;
}

export function hasBanglaVoice(): boolean {
  return "speechSynthesis" in window && window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith("bn"));
}

export function Hero({ rahim, onPreset }: { rahim: Sourced<RahimFacts>; onPreset: (preset: StoryPreset | null) => void }) {
  const [take, setTake] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [panel, setPanel] = useState<"dialects" | "type" | null>(null);
  const [text, setText] = useState("");
  const [asked, setAsked] = useState<Asked | null>(null);
  const [busy, setBusy] = useState(false);

  const words = RAHIM.question.split(" ");
  const facts = rahim.data;
  const tags = useMemo(() => {
    const list: { text: string; dot: string }[] = [
      { text: facts.quantityExpression ? `${facts.quantityExpression} = ${kg(facts.quantityKg)}` : kg(facts.quantityKg), dot: "bg-slate-400" },
      { text: `Faria offers ${tk(facts.offer, 0)} a kilo`, dot: "bg-mustard-400" },
    ];
    if (facts.worriedAboutRot) list.push({ text: "Worried they will rot", dot: "bg-slate-400" });
    if (facts.piiHidden > 0) list.push({ text: "Phone number hidden", dot: "bg-sky-400" });
    return list;
  }, [facts]);

  const playQuestion = () => {
    setTake((t) => t + 1);
    if (hasBanglaVoice()) {
      speak(RAHIM.question, "bn-BD");
      setNotice(null);
    } else {
      setNotice("This device has no Bangla voice installed, so the question is shown but not spoken.");
    }
  };

  const ask = async (preset: StoryPreset | null, question: string) => {
    setPanel(null);
    setBusy(true);
    onPreset(preset);
    setAsked({ preset, question, result: null, live: false });
    try {
      const response = await api.voiceInteract(preset ? { preset_id: preset.id } : { text: question, district: "Rangpur", upazila: "Mithapukur" });
      setState({ lastVoice: response.data });
      setAsked({ preset, question, result: response.data, live: response.live });
    } catch (error) {
      setAsked({ preset, question, result: null, live: false, error: error instanceof ApiError ? error.message : String(error) });
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (text.trim().length >= 2) void ask(null, text.trim());
  };

  const close = () => {
    setAsked(null);
    onPreset(null);
  };

  return (
    <div className="max-w-[44rem]">
      <p className="mb-4 text-[17px] text-slate-400">{RAHIM.farmer} farms in {RAHIM.place}.</p>
      <h1 key={`q${take}`} lang="bn" className="voice m-0 text-[clamp(46px,7.2vw,112px)] leading-[1.22] text-slate-50" style={{ textWrap: "balance" }}>
        {words.map((word, i) => (
          <Fragment key={i}>
            <span className="story-word" style={{ "--i": i } as CSSProperties}>{word}</span>{i < words.length - 1 ? " " : ""}
          </Fragment>
        ))}
      </h1>
      <Waveform key={`w${take}`} words={words.length} className="mt-1 mb-5 block h-[46px] w-full max-w-[640px]" />

      <ul aria-label="What the system understood" className="m-0 mb-6 flex min-h-9 list-none flex-wrap gap-2 p-0" aria-busy={rahim.status === "loading"}>
        {rahim.status !== "loading" && tags.map((tag, i) => (
          <li key={`${take}-${tag.text}`} className="story-tag label flex items-center gap-2 rounded-full border border-slate-400/30 py-1 pr-3 pl-2.5 text-[14px] text-slate-50"
            style={{ "--i": i + 1 } as CSSProperties}>
            <span className={`size-1.5 rounded-full ${tag.dot}`} />{tag.text}
          </li>
        ))}
      </ul>

      <p className="m-0 mb-8 max-w-[34rem] text-[21px] leading-[1.45] text-slate-50">
        “{RAHIM.english}”
        <span className="mt-1 block text-[14px] text-slate-400">{RAHIM.dialect} dialect, recorded for this demo.</span>
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <StoryButton onClick={playQuestion}><Volume2 className="size-[18px]" aria-hidden /> Play his question</StoryButton>
        <StoryButton variant="ghost" aria-expanded={panel === "dialects"} onClick={() => setPanel(panel === "dialects" ? null : "dialects")}>
          <Languages className="size-[18px]" aria-hidden /> Ask in another dialect
        </StoryButton>
        <StoryButton variant="link" aria-expanded={panel === "type"} onClick={() => setPanel(panel === "type" ? null : "type")}>
          <Keyboard className="size-4" aria-hidden /> Type a question
        </StoryButton>
      </div>
      {notice && <p className="mt-3 text-[14px] text-slate-400" role="status">{notice}</p>}

      {panel === "dialects" && (
        <div className="mt-5 grid gap-2 sm:grid-cols-2" role="group" aria-label="Other farmers' recorded questions">
          {STORY_PRESETS.slice(1).map((preset) => (
            <button key={preset.id} type="button" onClick={() => void ask(preset, preset.question)}
              className="card px-4 py-3 text-left transition-colors hover:border-mustard-400/50">
              <span className="label block text-[13px] text-slate-400">{preset.farmer} in {preset.place}, {preset.dialect}</span>
              <span lang="bn" className="voice mt-1 block text-[21px] leading-[1.45] text-slate-50">{preset.question}</span>
              <span className="mt-1 block text-[14px] text-slate-300">{preset.english}</span>
            </button>
          ))}
        </div>
      )}

      {panel === "type" && (
        <form onSubmit={submit} className="mt-5 flex max-w-[34rem] flex-wrap gap-2">
          <label htmlFor="story-question" className="sr-only">Your question, in Bangla or English</label>
          <input id="story-question" value={text} onChange={(e) => setText(e.target.value)} autoComplete="off"
            placeholder="আমার ৫ মণ আলু আছে, কোথায় বেচব?"
            className="min-h-12 min-w-0 flex-1 rounded-full border border-slate-50/25 bg-ink-900/80 px-5 text-[16px] text-slate-50 placeholder:text-slate-500" />
          <StoryButton type="submit" disabled={text.trim().length < 2}>Ask the agents</StoryButton>
          <span className="w-full px-1 text-[13px] text-slate-500">Answered for a farmer in Mithapukur, Rangpur.</span>
        </form>
      )}

      {asked && (
        <div className="card mt-6 p-5" aria-live="polite">
          <div className="flex items-start justify-between gap-3">
            <p className="label m-0 text-[13px] text-slate-400">{asked.preset ? `${asked.preset.farmer} in ${asked.preset.place}` : "Your question"}</p>
            <button type="button" aria-label="Close the answer" onClick={close} className="rounded-full p-1 text-slate-400 hover:text-slate-100"><X className="size-4" /></button>
          </div>
          <p lang="bn" className="voice m-0 mt-1 text-[24px] leading-[1.45] text-slate-50">{asked.question}</p>
          {busy && <p className="mt-3 text-[15px] text-slate-400">Asking the agents…</p>}
          {asked.error && <p className="mt-3 text-[15px] text-red-300">The agents could not answer: {asked.error}</p>}
          {asked.result && (
            <>
              <p className="mt-3 mb-0 text-[16px] leading-relaxed text-slate-200">
                {asked.result.status === "NEEDS_CLARIFICATION" ? "The agents need one more detail before they can answer." : englishSummary(asked.result)}
              </p>
              <p lang="bn" className="voice mt-3 mb-0 text-[18px] leading-[1.75] text-slate-300">
                {asked.result.follow_up_question_bn && asked.result.status === "NEEDS_CLARIFICATION" ? asked.result.follow_up_question_bn : asked.result.spoken_response_bn}
              </p>
              <p className="label mt-4 mb-0 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-slate-500">
                <span>{asked.live ? "Live answer from the agents" : "Backend offline: showing the cached demo answer"}</span>
                <Link to="/os/field" className="text-mustard-300 underline underline-offset-4">Open it in the live OS</Link>
              </p>
            </>
          )}
        </div>
      )}

      <p className="label mt-14 flex items-center gap-2 text-[14px] text-slate-500">
        <ChevronDown className="size-4" aria-hidden /> Scroll to follow his potatoes
      </p>
    </div>
  );
}
