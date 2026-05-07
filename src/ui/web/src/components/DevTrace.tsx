/* Developer trace panel — right-side rail revealed in developer mode (⌘D).
   Chronological function-call log with brief highlight when an entry lands. */
import React from 'react';
import { IconTerminal, IconX } from './icons';
import type { TraceCall } from '../lib/types';

export type TracePanelProps = {
  calls: TraceCall[];
  highlightId: number | null;
  onClose: () => void;
};

function TracePanel({ calls, highlightId, onClose }: TracePanelProps) {
  const reversed = calls.slice().reverse();

  return (
    <aside
      className="kin-slide-in-right border-l border-line bg-card flex flex-col h-full"
      style={{ width: 340 }}
    >
      <div className="px-4 py-3 border-b border-hair flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-muted"><IconTerminal size={16} /></span>
          <div>
            <div className="text-[13px] font-semibold text-ink">Developer view</div>
            <div className="text-[11px] text-muted">Function-call trace · not field-facing</div>
          </div>
        </div>
        <button className="text-muted hover:text-ink p-1 rounded-kin" onClick={onClose} aria-label="Close developer view">
          <IconX size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 font-mono text-[12.5px]">
        {reversed.length === 0 && (
          <div className="text-muted text-[12px] font-sans leading-relaxed">
            No calls yet. Start the demo sequence or simulate a match to see the trace populate.
          </div>
        )}
        <ol className="space-y-3">
          {reversed.map((c, i) => {
            // In reversed order, prior call in time is the next element.
            const prev = reversed[i + 1];
            const relMs = prev ? c.t - prev.t : 0;
            const highlight = c.id === highlightId;
            return (
              <li
                key={c.id}
                className={`border rounded-kin px-2.5 py-2 transition-colors duration-300 ${
                  highlight ? "border-primary bg-primary-soft" : "border-hair bg-subtle/50"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-primary font-medium">{c.name}</span>
                  <span className="text-muted text-[11px]">
                    +{(c.t / 1000).toFixed(2)}s{prev && ` · Δ${(relMs / 1000).toFixed(2)}s`}
                  </span>
                </div>
                {c.args && (
                  <div className="mt-1 text-muted whitespace-pre-wrap break-words">
                    {Object.entries(c.args).map(([k, v]) => (
                      <div key={k}>
                        <span className="text-[oklch(0.45_0.02_240)]">{k}</span>
                        <span className="text-muted">: </span>
                        <span className="text-ink">{typeof v === "string" ? `"${v}"` : String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {c.result !== undefined && (
                  <div className="mt-1 text-ink">
                    <span className="text-muted">→ </span>
                    {typeof c.result === "string" && c.result.length > 40
                      ? <span>"{c.result.slice(0, 38)}…"</span>
                      : <span>{typeof c.result === "string" ? `"${c.result}"` : String(c.result)}</span>}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </div>
      <div className="border-t border-hair px-4 py-2.5 text-[11px] text-muted font-sans">
        {calls.length} calls · auto-scroll enabled
      </div>
    </aside>
  );
}

export { TracePanel };
