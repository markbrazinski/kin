/* ============================================================================
 * KIN — structlog.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: the "Stripe API docs" typographic credibility aesthetic.
 *     Mono font for keys/values, no chrome (no card borders around rows),
 *     status communicated via 1px LEFT BORDER per row (not bg fill, not
 *     icon). This is the locked sidebar visual language.
 *   • DO NOT CHANGE: heartbeat states. 'idle' = 2s pulse, 'busy' = 0.5s
 *     pulse, 'down' = solid amber. The amber-on-disconnect is critical —
 *     it is how the operator knows the field tool is queueing locally vs
 *     synced. This is part of the trust story for offline-first.
 *   • Mono font: ui-monospace stack. If your repo has a custom mono
 *     (JetBrains Mono, Berkeley Mono, etc.), swap it in via Tailwind
 *     font-mono — but keep the size at text-[11px] for entries. The
 *     density is intentional.
 *   • Event row schema: { ts, level, msg, kv? }. `kv` is rendered as
 *     inline key=value pairs in muted color. When porting, keep the
 *     unstyled-key, styled-value pattern — flipping it makes scanning
 *     harder.
 *   • For SPLIT view (future Bundle 1.5+ work): rows will gain an
 *     `origin: 'A' | 'B'` field that prepends a mono [A]/[B] tag.
 *     Don't refactor the row component until split lands — leaving the
 *     hook obvious here.
 * ============================================================================
 * Structlog sidebar — credibility surface, "Stripe API docs" aesthetic.
 * Typographic hierarchy, status by 1px left border, no chrome.
 * Heartbeat in header: pulses 2s idle / 0.5s in-flight / amber on disconnect. */

function StructlogHeartbeat({ state /* 'idle' | 'busy' | 'down' */, since }) {
  const dotCls =
    state === "busy" ? "bg-primary" :
    state === "down" ? "bg-amber" :
    "bg-green";
  // Different pulse cadence per state via inline style
  const pulse =
    state === "busy" ? "kin-pulse-fast" :
    state === "down" ? "" :
    "kin-pulse-slow";
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-muted" aria-live="polite">
      <span className={`w-[6px] h-[6px] rounded-full ${dotCls} ${pulse}`} aria-hidden="true" />
      <span className="text-ink/70">
        {state === "down" ? "SSE down" : state === "busy" ? "SSE · in-flight" : "SSE live"}
      </span>
      {since && state !== "down" && <span>· connected {since}</span>}
    </span>
  );
}

function StructlogRow({ ev }) {
  // status: 'ok' (default) | 'started' | 'warn' | 'error'
  const borderCls =
    ev.status === "started" ? "border-l-primary" :
    ev.status === "warn"    ? "border-l-amber" :
    ev.status === "error"   ? "border-l-red" :
    "border-l-line";

  const tRel = `+${(ev.tMs / 1000).toFixed(2)}s`;
  return (
    <li className={`px-3 py-2 border-l-2 ${borderCls} hover:bg-subtle/60 transition-colors`}>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[12px] text-ink">{ev.name}</span>
        <span className="font-mono text-[10.5px] text-muted ml-auto tabular-nums">{tRel}</span>
      </div>
      {ev.subtitle && <div className="text-[12px] text-muted mt-0.5 leading-snug">{ev.subtitle}</div>}
      {ev.kvs && (
        <div className="mt-1 font-mono text-[11px] text-muted leading-relaxed">
          {Object.entries(ev.kvs).map(([k, v]) => (
            <div key={k}>
              <span className="text-[oklch(0.45_0.02_240)]">{k}</span>
              <span>=</span>
              <span className="text-ink">{typeof v === "string" ? `"${v}"` : String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </li>
  );
}

function StructlogSidebar({ events, heartbeat = "idle", since = "11:02" }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events.length]);

  return (
    <aside className="border-l border-line bg-card flex flex-col h-full" style={{ width: 320 }} aria-label="Pipeline structlog">
      <div className="px-4 h-14 border-b border-hair flex flex-col justify-center gap-0.5">
        <div className="flex items-center justify-between">
          <div className="text-[13px] font-semibold text-ink">Pipeline</div>
          <StructlogHeartbeat state={heartbeat} since={since} />
        </div>
        <div className="text-[11px] text-muted">structlog · session #147</div>
      </div>

      <div ref={ref} className="flex-1 overflow-y-auto py-1">
        {events.length === 0 ? (
          <div className="px-4 py-6 text-[12px] text-muted leading-relaxed">
            System ready. Pipeline events will appear as the intake runs.
          </div>
        ) : (
          <ol>{events.map((ev, i) => <StructlogRow key={ev.id ?? i} ev={ev} />)}</ol>
        )}
      </div>

      <div className="border-t border-hair px-4 py-2 text-[11px] text-muted font-mono flex items-center justify-between">
        <span>{events.length} events</span>
        <span>auto-scroll</span>
      </div>
    </aside>
  );
}

Object.assign(window, { StructlogSidebar, StructlogHeartbeat });
