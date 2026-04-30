/* ============================================================================
 * KIN — tool-calls.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: tool-calls and structlog are SEPARATE sidebars. They
 *     show different things and resisted merge during Round 2 review:
 *       structlog = system events (sync, heartbeat, save, log lines)
 *       tool-calls = LLM function-call observability (name, args, result)
 *     Merging them flattens the credibility narrative — keep them split.
 *   • DO NOT CHANGE: the two-state row pattern. A call appears first as
 *     'started' (gray, name only, no args yet) and resolves to full
 *     args+result with a one-shot highlight pulse on landing. This
 *     animates the "function call ↔ response" rhythm — it's what makes
 *     the panel read as live observability instead of a static log.
 *   • JSON formatting: 2-space indent, mono, text-[11px]. The args/result
 *     blocks have a subtle bg (bg-paper) to separate from the row chrome.
 *     Don't add syntax highlighting — plain mono reads more "API debugger"
 *     than "fancy IDE."
 *   • Status colors on the left rule: gray (started), green (ok), red
 *     (error). Red errors should NEVER be silently dropped — they're
 *     part of the honesty story.
 * ============================================================================
 * Tool-calls sidebar — JSON function-call observability, separate from structlog.
 * Each call streams in as 'started', resolves to full args+result with pulse. */

function JsonValue({ value }) {
  if (value === null) return <span className="text-muted">null</span>;
  if (typeof value === "string") return <span className="text-[oklch(0.42_0.1_155)]">"{value}"</span>;
  if (typeof value === "number" || typeof value === "boolean") return <span className="text-primary">{String(value)}</span>;
  if (Array.isArray(value)) {
    return (
      <span>
        <span className="text-muted">[</span>
        {value.map((v, i) => (
          <React.Fragment key={i}>
            <JsonValue value={v} />
            {i < value.length - 1 && <span className="text-muted">, </span>}
          </React.Fragment>
        ))}
        <span className="text-muted">]</span>
      </span>
    );
  }
  return <span className="text-ink">{JSON.stringify(value)}</span>;
}

function JsonObject({ obj, indent = 0 }) {
  const entries = Object.entries(obj || {});
  if (!entries.length) return <span className="text-muted">{"{}"}</span>;
  return (
    <div className="font-mono text-[11.5px] leading-relaxed">
      <span className="text-muted">{"{"}</span>
      <div className="ml-3">
        {entries.map(([k, v], i) => (
          <div key={k}>
            <span className="text-[oklch(0.45_0.02_240)]">"{k}"</span>
            <span className="text-muted">: </span>
            <JsonValue value={v} />
            {i < entries.length - 1 && <span className="text-muted">,</span>}
          </div>
        ))}
      </div>
      <span className="text-muted">{"}"}</span>
    </div>
  );
}

function ToolCallRow({ call, isLatest }) {
  const started = call.status === "started";
  return (
    <div className={`px-4 py-3 border-b border-hair ${isLatest && !started ? "kin-populate" : ""}`}>
      <div className="flex items-baseline gap-2">
        <span className={`font-mono text-[12.5px] font-medium ${started ? "text-muted" : "text-primary"}`}>
          {call.name}
        </span>
        {started && (
          <span className="inline-flex items-center gap-1 text-[10.5px] font-mono text-muted ml-1">
            <span className="w-1 h-1 rounded-full bg-muted animate-pulse" />
            running
          </span>
        )}
        <span className="font-mono text-[10.5px] text-muted ml-auto tabular-nums">
          +{(call.tMs / 1000).toFixed(2)}s
        </span>
      </div>

      {!started && call.args && (
        <div className="mt-1.5">
          <div className="text-[10px] uppercase tracking-wider text-muted font-medium mb-0.5">args</div>
          <JsonObject obj={call.args} />
        </div>
      )}

      {!started && call.result !== undefined && (
        <div className="mt-2">
          <div className="text-[10px] uppercase tracking-wider text-muted font-medium mb-0.5">result</div>
          <div className="font-mono text-[11.5px] text-ink">
            {typeof call.result === "object"
              ? <JsonObject obj={call.result} />
              : <JsonValue value={call.result} />}
          </div>
        </div>
      )}
    </div>
  );
}

function ToolCallsSidebar({ calls }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [calls.length]);

  return (
    <aside className="border-l border-line bg-card flex flex-col h-full" style={{ width: 320 }} aria-label="Tool calls">
      <div className="px-4 h-14 border-b border-hair flex flex-col justify-center gap-0.5">
        <div className="flex items-center justify-between">
          <div className="text-[13px] font-semibold text-ink">Tool calls</div>
          <span className="text-[11px] font-mono text-muted">gemma · e2b</span>
        </div>
        <div className="text-[11px] text-muted">function invocations · live</div>
      </div>

      <div ref={ref} className="flex-1 overflow-y-auto">
        {calls.length === 0 ? (
          <div className="px-4 py-6 text-[12px] text-muted leading-relaxed">
            No invocations yet. Tool calls land here as the model decides to use them.
          </div>
        ) : (
          calls.map((c, i) => (
            <ToolCallRow key={c.id} call={c} isLatest={i === calls.length - 1} />
          ))
        )}
      </div>

      <div className="border-t border-hair px-4 py-2 text-[11px] text-muted font-mono flex items-center justify-between">
        <span>{calls.filter(c => c.status !== "started").length} resolved</span>
        <span>{calls.filter(c => c.status === "started").length} in flight</span>
      </div>
    </aside>
  );
}

Object.assign(window, { ToolCallsSidebar });
