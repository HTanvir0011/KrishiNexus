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
      {error && <div className="rounded-lg bg-red-500/10 p-2 text-xs text-red-300">Backend unreachable: {error}</div>}
      <div className="grid gap-2 md:grid-cols-3">
        {servers.map((s) => (
          <div key={s.name} className="panel p-3">
            <div className="flex items-center gap-1.5 font-mono text-xs font-semibold text-emerald-300"><Server className="size-3.5" />{s.name}</div>
            <div className="mt-1 text-[11px] text-slate-400">{s.title} · v{s.version} · MCP {s.protocol_version}</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {s.transports.map((t) => <Badge key={t} tone="sky">{t}</Badge>)}
              <Badge tone="slate">{s.tool_count} tools</Badge>
            </div>
            <div className="mt-2 truncate font-mono text-[10px] text-slate-500" title={s.stdio_command}>$ {s.stdio_command}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="panel flex flex-col gap-2 p-3">
          <label htmlFor="mcp-tool" className="text-[10px] uppercase tracking-wider text-slate-500">Tool</label>
          <select id="mcp-tool" value={tool} onChange={(e) => choose(e.target.value)}
            className="rounded-lg bg-ink-800 px-2 py-1.5 font-mono text-xs text-slate-100 ring-1 ring-ink-600">
            {servers.map((s) => (
              <optgroup key={s.name} label={s.name}>
                {s.tools.map((name) => <option key={name} value={name}>{name}</option>)}
              </optgroup>
            ))}
          </select>
          <p className="text-xs leading-relaxed text-slate-400">{selected?.description}</p>
          <label htmlFor="mcp-json" className="text-[10px] uppercase tracking-wider text-slate-500">params.arguments</label>
          <textarea id="mcp-json" value={args} onChange={(e) => setArgs(e.target.value)} spellCheck={false}
            className="min-h-[150px] rounded-lg bg-black/40 p-2 font-mono text-[11px] text-slate-200 ring-1 ring-ink-600" />
          <Button variant="primary" onClick={execute} disabled={running}>
            {running ? <Spinner /> : <Play className="size-3.5" />} Execute Live MCP Tool Call
          </Button>
          <div className="font-mono text-[10px] text-slate-500">POST /mcp/call · method tools/call · JSON-RPC 2.0</div>
        </div>
        <div className="panel flex min-h-[320px] flex-col gap-2 p-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-slate-500">Response</span>
            {result && <Badge tone={result.status === 200 ? "emerald" : "red"}>HTTP {result.status || "—"}</Badge>}
            {result && <Badge tone="sky"><Timer className="size-3" /> {result.latencyMs.toFixed(0)} ms round trip</Badge>}
            {outcome && <Badge tone={outcome === "success" ? "emerald" : "amber"}>{outcome}</Badge>}
          </div>
          <pre className={cn("scroll-thin max-h-[440px] flex-1 overflow-auto rounded-lg bg-black/40 p-2 font-mono text-[11px]",
            outcome === "success" ? "text-emerald-100" : "text-slate-300")}>
            {result ? JSON.stringify(result.body, null, 2) : "Execute a call to see the raw JSON-RPC 2.0 envelope."}
          </pre>
        </div>
      </div>
    </div>
  );
}
