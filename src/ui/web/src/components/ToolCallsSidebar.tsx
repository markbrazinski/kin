/* Tool-calls observability sidebar.

   Ported from design_reference/round-2/tool-calls.jsx.
   DO NOT CHANGE: tool-calls and structlog are SEPARATE sidebars.
   DO NOT CHANGE: two-state row pattern (started → resolved).
   DO NOT CHANGE: plain mono JSON — no syntax highlighting library. */
import React from 'react';
import type { ToolCall } from '../state/toolCalls';
import { isMergeFlashEvent } from '../lib/mergeFlash';

// ---- JSON renderers (plain mono, token-role color only) -----------------

function JsonValue({ value }: { value: unknown }): React.ReactElement {
  if (value === null) return <span className="text-muted">null</span>;
  if (typeof value === 'string') {
    return <span className="text-[oklch(0.42_0.1_155)]">"{value}"</span>;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return <span className="text-primary">{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <span>
        <span className="text-muted">[</span>
        {value.map((v, i) => (
          <span key={i}>
            <JsonValue value={v} />
            {i < value.length - 1 && <span className="text-muted">, </span>}
          </span>
        ))}
        <span className="text-muted">]</span>
      </span>
    );
  }
  if (typeof value === 'object') {
    return <JsonObject obj={value as Record<string, unknown>} />;
  }
  return <span className="text-ink">{JSON.stringify(value)}</span>;
}

function JsonObject({ obj }: { obj: Record<string, unknown> | null }): React.ReactElement {
  const entries = Object.entries(obj ?? {});
  if (!entries.length) return <span className="text-muted">{'{}'}</span>;
  return (
    <div className="font-mono text-[11.5px] leading-relaxed">
      <span className="text-muted">{'{'}</span>
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
      <span className="text-muted">{'}'}</span>
    </div>
  );
}

// ---- Per-row status left-rule -------------------------------------------

const LEFT_RULE: Record<ToolCall['status'], string> = {
  started: 'border-l-2 border-line',
  resolved: 'border-l-2 border-green',
  error: 'border-l-2 border-red',
};

// ---- ToolCallRow ---------------------------------------------------------

type ToolCallRowProps = {
  call: ToolCall;
  isLatest: boolean;
};

function ToolCallRow({ call, isLatest }: ToolCallRowProps) {
  const started = call.status === 'started';
  return (
    <div
      className={`px-4 py-3 border-b border-hair ${LEFT_RULE[call.status]} ${isLatest && !started ? 'kin-populate' : ''} ${isMergeFlashEvent(call.name) ? 'kin-flash-highlight' : ''}`}
    >
      <div className="flex items-baseline gap-2">
        <span
          className={`font-mono text-[12.5px] font-medium ${started ? 'text-muted' : 'text-primary'}`}
        >
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
          <div className="text-[10px] uppercase tracking-wider text-muted font-medium mb-0.5">
            args
          </div>
          <JsonObject obj={call.args} />
        </div>
      )}

      {!started && call.result !== undefined && (
        <div className="mt-2">
          <div className="text-[10px] uppercase tracking-wider text-muted font-medium mb-0.5">
            result
          </div>
          <div className="font-mono text-[11.5px] text-ink">
            {typeof call.result === 'object' && call.result !== null ? (
              <JsonObject obj={call.result as Record<string, unknown>} />
            ) : (
              <JsonValue value={call.result} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- ToolCallsSidebar ---------------------------------------------------

export type ToolCallsSidebarProps = {
  calls: ToolCall[];
  className?: string;
};

export function ToolCallsSidebar({ calls, className = '' }: ToolCallsSidebarProps) {
  const resolved = calls.filter((c) => c.status !== 'started').length;
  const inFlight = calls.filter((c) => c.status === 'started').length;
  const reversed = calls.slice().reverse();

  return (
    <div
      className={`bg-card border border-line rounded-kin ${className}`}
      aria-label="Tool calls"
    >
      {/* Header */}
      <div className="px-4 h-11 border-b border-hair flex flex-col justify-center gap-0.5">
        <div className="flex items-center justify-between">
          <div className="text-[13px] font-semibold text-ink">Tool calls</div>
          <span className="text-[11px] font-mono text-muted">gemma · e2b</span>
        </div>
        <div className="text-[11px] text-muted">function invocations · live</div>
      </div>

      {/* Newest-first — no auto-scroll needed; top of list is always current. */}
      <div className="overflow-y-auto max-h-[280px]">
        {reversed.length === 0 ? (
          <div className="px-4 py-5 text-[12px] text-muted leading-relaxed">
            No invocations yet. Tool calls land here as the model decides to use them.
          </div>
        ) : (
          reversed.map((c, i) => (
            <ToolCallRow key={c.id} call={c} isLatest={i === 0} />
          ))
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-hair px-4 py-2 text-[11px] text-muted font-mono flex items-center justify-between">
        <span>{resolved} resolved</span>
        <span>{inFlight} in flight</span>
      </div>
    </div>
  );
}
