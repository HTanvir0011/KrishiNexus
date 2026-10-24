import { Play, Server, Timer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, rawJsonRpc, type McpServerInfo, type McpTool } from "../../api/client";
import { cn } from "../../lib/format";
import { MCP_EXAMPLE_ARGS } from "../../lib/mcpExamples";
import { Badge, Button, Spinner } from "../ui";

interface CallResult {
  status: number;
  latencyMs: number;
  body: unknown;
}

export function McpInspectorSection() {
  const [servers, setServers] = useState<McpServerInfo[]>([]);
  const [tools, setTools] = useState<McpTool[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tool, setTool] = useState("detect_syndicate_markup_anomaly");
  const [args, setArgs] = useState(JSON.stringify(MCP_EXAMPLE_ARGS.detect_syndicate_markup_anomaly, null, 2));
  const [result, setResult] = useState<CallResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    Promise.all([api.mcpServers(), api.mcpTools()])
      .then(([s, t]) => {
        setServers(s);
        setTools(t.tools);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const selected = useMemo(() => tools.find((t) => t.name === tool), [tools, tool]);
  const choose = (name: string) => {
    setTool(name);
    setArgs(JSON.stringify(MCP_EXAMPLE_ARGS[name] ?? {}, null, 2));
    setResult(null);
  };

  const execute = async () => {
    setRunning(true);
    try {
      const parsed = JSON.parse(args) as Record<string, unknown>;
      setResult(await rawJsonRpc({ jsonrpc: "2.0", id: Date.now(), method: "tools/call", params: { name: tool, arguments: parsed } }));
    } catch (e) {
      setResult({ status: 0, latencyMs: 0, body: { client_error: e instanceof Error ? e.message : String(e) } });
    } finally {
      setRunning(false);
    }
  };

  const rpc = result?.body as { result?: { isError?: boolean }; error?: unknown } | undefined;
  const outcome = !result ? null : rpc?.error ? "JSON-RPC error" : rpc?.result?.isError ? "tool error (isError)" : result.status === 200 ? "success" : "HTTP error";

  return (
    <div className="space-y-3">
      {error && <div role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-[13px] text-rose-700 ring-1 ring-rose-600/20 ring-inset">Backend unreachable: {error}</div>}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="surface min-w-0 divide-y divide-slate-100 lg:self-start">
          {servers.length === 0 && !error && <div className="flex items-center gap-2 p-4 text-[13px] text-slate-500"><Spinner /> Loading servers…</div>}
          {servers.map((s) => (
            <div key={s.name} className="p-4">
              <div className="flex items-center gap-1.5 font-mono text-[13px] font-semibold text-slate-900"><Server className="size-3.5 text-emerald-700" />{s.name}</div>
              <div className="mt-0.5 text-[12px] text-slate-500">{s.title} · v{s.version} · MCP {s.protocol_version}</div>
              <div className="mt-2 flex flex-wrap gap-1">
                {s.transports.map((t) => <Badge key={t} tone="sky">{t}</Badge>)}
                <Badge tone="slate"><span className="tabular-nums">{s.tool_count}</span> tools</Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-1 lg:flex-col">
                {s.tools.map((name) => (
                  <button key={name} type="button" onClick={() => choose(name)} aria-pressed={tool === name}
                    className={cn("rounded-md px-2.5 py-1.5 text-left font-mono text-[12.5px] ring-1 ring-inset transition-colors max-lg:min-h-10",
                      tool === name
                        ? "bg-emerald-50 font-semibold text-emerald-800 ring-emerald-700/25"
                        : "text-slate-700 ring-slate-200 hover:bg-slate-50 hover:text-slate-900 lg:ring-transparent")}>
                    {name}
                  </button>
                ))}
              </div>
              <div className="mt-3 truncate font-mono text-[11px] text-slate-500" title={s.stdio_command}>$ {s.stdio_command}</div>
            </div>
          ))}
        </div>

        <div className="surface min-w-0">
          <div className="space-y-4 p-4 sm:p-5">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="min-w-0 font-mono text-[15px] font-semibold text-slate-900 wrap-anywhere">{tool}</h3>
                {selected && <Badge tone="violet">{selected.server}</Badge>}
              </div>
              {selected && <p className="mt-1.5 text-[14px] leading-relaxed text-slate-600">{selected.description}</p>}
            </div>
            <div>
              <label htmlFor="mcp-json" className="text-[12px] font-medium text-slate-500">params.arguments</label>
              <textarea id="mcp-json" value={args} onChange={(e) => setArgs(e.target.value)} spellCheck={false}
                className="scroll-thin mt-1.5 block min-h-[180px] w-full resize-y rounded-lg bg-slate-50 p-3 font-mono text-[12.5px] leading-relaxed text-slate-800 ring-1 ring-slate-200 ring-inset" />
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <Button variant="primary" onClick={execute} disabled={running}>
                {running ? <Spinner /> : <Play className="size-3.5" />} Execute tool
              </Button>
              <span className="font-mono text-[12px] text-slate-500">POST /mcp/call · method tools/call · JSON-RPC 2.0</span>
            </div>
          </div>

          <div className="border-t border-slate-200 p-4 sm:p-5">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-[13px] font-semibold text-slate-900">Response</span>
              {result && <Badge tone={result.status === 200 ? "emerald" : "red"}>HTTP <span className="tabular-nums">{result.status || "—"}</span></Badge>}
              {result && <Badge tone="sky"><Timer className="size-3" /> <span className="tabular-nums">{result.latencyMs.toFixed(0)} ms</span> round trip</Badge>}
              {outcome && <Badge tone={outcome === "success" ? "emerald" : "amber"}>{outcome}</Badge>}
            </div>
            {/* Wrapped: content[0].text is one JSON string tens of thousands of pixels long. */}
            <pre className={cn("scroll-thin mt-3 max-h-[440px] min-h-[140px] overflow-auto rounded-lg bg-slate-50 p-3 font-mono text-[12px] leading-relaxed whitespace-pre-wrap ring-1 ring-slate-200 ring-inset wrap-anywhere",
              result ? "text-slate-800" : "text-slate-500")}>
              {result ? JSON.stringify(result.body, null, 2) : "Execute a call to see the raw JSON-RPC 2.0 envelope."}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
