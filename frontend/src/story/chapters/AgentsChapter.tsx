import { useMemo, useState } from "react";

import { api, type TraceEvent } from "../../api/client";
import { cn } from "../../lib/format";
import { setState, useAppState } from "../../state/store";
import { ChapterHeading, StoryButton } from "../parts";

/** LangGraph node order (`agents/supervisor.py`), named by what each step does for the farmer. */
const STEPS: { agent: string; title: string }[] = [
  { agent: "pii_guardrail", title: "Hide personal details" },
  { agent: "token_compression", title: "Shrink the context" },
  { agent: "crag_retrieval", title: "Look up the guidance" },
  { agent: "vision_grading", title: "Grade the crop" },
  { agent: "syndicate_bypass", title: "Find a direct buyer" },
  { agent: "coldchain_arbitrage", title: "Price cold storage" },
  { agent: "climate_credit", title: "Check flood risk and credit" },
  { agent: "supervisor", title: "Review the plan" },
  { agent: "voice_synthesizer", title: "Answer in Bangla" },
];

const EMPTY: TraceEvent[] = [];

export function AgentsChapter() {
  const [session, setSession] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{ events: number; ms: number; live: boolean; trace: TraceEvent[] } | null>(null);
  const traces = useAppState((s) => s.traces);
  const streamed = useMemo(() => (session ? traces.filter((e) => e.session_id === session) : EMPTY), [traces, session]);
  const events = streamed.length ? streamed : result?.trace ?? EMPTY;

  const latest = useMemo(() => {
    const byAgent = new Map<string, TraceEvent>();
    for (const event of events) byAgent.set(event.agent_name, event);
    return byAgent;
  }, [events]);
  const current = running ? events[events.length - 1]?.agent_name : undefined;

  const run = async () => {
    const id = `KNX-STORY-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
    setSession(id);
    setRunning(true);
    setResult(null);
    setState({ activeSessionId: id });
    try {
      const response = await api.voiceInteract({ preset_id: "rangpur_potato_distress", session_id: id });
      const orchestration = response.data.orchestration;
      setResult({
        events: orchestration?.trace_event_count ?? 0,
        ms: orchestration?.latency_ms ?? 0,
        live: response.live,
        trace: orchestration?.state.trace_events ?? EMPTY,
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <ChapterHeading index={5}>Four agents, one answer</ChapterHeading>
      <p className="text-[18px] leading-relaxed text-slate-200">
        Every answer above came from one run of the system: four agents, guarded and reviewed by a supervisor. Run it again on Rahim's
        question and watch each step report in.
      </p>
      <StoryButton className="mt-5" onClick={() => void run()} disabled={running}>
        {running ? "The agents are working…" : "Run the agents again"}
      </StoryButton>

      <ol className="m-0 mt-7 list-none space-y-1 p-0">
        {STEPS.map((step, i) => {
          const event = latest.get(step.agent);
          const state = current === step.agent ? "active" : event ? "done" : "waiting";
          return (
            <li key={step.agent} className="grid grid-cols-[2rem_1fr] gap-x-3 py-1.5">
              <span className={cn("num grid size-7 place-items-center rounded-full text-[14px]",
                state === "done" && "bg-emerald-600 text-slate-50", state === "active" && "bg-mustard-400 text-ink-900",
                state === "waiting" && "border border-slate-50/20 text-slate-400")}>{i + 1}</span>
              <span className="min-w-0">
                <span className={cn("text-[16px]", state === "waiting" ? "text-slate-400" : "text-slate-50")}>{step.title}</span>
                {event && <span className="line-clamp-2 text-[14px] break-words text-slate-400" title={event.payload_summary}>{event.payload_summary}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {result && (
        <p className="label mt-5 text-[14px] text-slate-400" role="status">
          {result.live
            ? `${result.events} events in ${(result.ms / 1000).toFixed(1)} seconds, streamed live over the agent-trace WebSocket.`
            : "Backend offline: start it to watch the agents run."}
        </p>
      )}
    </>
  );
}
