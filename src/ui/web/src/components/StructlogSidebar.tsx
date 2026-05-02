/* Per-panel structlog event sidebar.

   Reads from the panel's useEventStream state.structlogEvents slice
   and renders each event as a row: event name, time delta from the
   prior event, key-value pairs from the payload extras. Color band
   on the left edge categorizes pipeline / classifier / error events.

   Auto-scroll: anchored to the bottom on each new event arrival via
   a sentinel ref + scrollIntoView. No pause-on-user-scroll affordance —
   kept simple at per-panel scale.

   S4: added started category (border-l-primary for in-progress events),
   merge-flash highlight (kin-flash-highlight on matching_trigger_fired /
   matching_retrigger_fired), typographic polish, updated empty-state copy,
   event-count footer. */
import { useEffect, useRef } from 'react';
import type { StructlogEnvelope } from '../lib/sseEnvelope';
import { isMergeFlashEvent } from '../lib/mergeFlash';

export type StructlogSidebarProps = {
  events: StructlogEnvelope[];
  className?: string;
};

type Category = 'neutral' | 'started' | 'amber' | 'red';

function categorize(eventName: string): Category {
  if (
    eventName === 'adapter_call_start' ||
    eventName === 'ingest_audio_start' ||
    eventName === 'tool_call_invoked'
  ) return 'started';
  if (
    eventName.startsWith('crisis_') ||
    eventName === 'minor_flagged'
  ) return 'amber';
  if (
    eventName === 'inference_timeout' ||
    eventName.startsWith('inference_failed') ||
    eventName === 'padding_failed' ||
    eventName === 'tool_call_no_tools_emitted'
  ) return 'red';
  return 'neutral';
}

const BAND_CLASS: Record<Category, string> = {
  neutral: 'border-l-2 border-line',
  started: 'border-l-2 border-primary',
  amber:   'border-l-2 border-amber',
  red:     'border-l-2 border-red',
};

const SKIP_PAYLOAD_KEYS = new Set(['event', 'level', 'timestamp']);

function payloadEntries(envelope: StructlogEnvelope): [string, unknown][] {
  return Object.entries(envelope.payload).filter(
    ([k]) => !SKIP_PAYLOAD_KEYS.has(k),
  );
}

function deltaSeconds(curr: string, prev: string | null): string {
  if (!prev) return '+0.00s';
  const dCurr = Date.parse(curr);
  const dPrev = Date.parse(prev);
  if (Number.isNaN(dCurr) || Number.isNaN(dPrev)) return '';
  const delta = (dCurr - dPrev) / 1000;
  return `+${delta.toFixed(2)}s`;
}

export function StructlogSidebar({
  events,
  className = '',
}: StructlogSidebarProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    /* scrollIntoView may be missing in jsdom-based test environments;
       optional-chain on the method itself keeps tests green and is a
       no-op cost in real browsers. */
    bottomRef.current?.scrollIntoView?.({ block: 'end' });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div
        className={`bg-card border border-line rounded-kin p-3 ${className}`}
      >
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted mb-2">
          Pipeline log
        </div>
        <div className="text-[12px] text-muted">
          System ready. Pipeline events will appear as the intake runs.
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-card border border-line rounded-kin p-3 ${className}`}
    >
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted mb-2">
        Pipeline log
      </div>
      <div className="overflow-y-auto max-h-44 space-y-1.5">
        {events.map((env, idx) => {
          const prev = idx > 0 ? events[idx - 1].at : null;
          const cat = categorize(env.payload.event);
          const flash = isMergeFlashEvent(env.payload.event);
          return (
            <div
              key={`${env.at}-${idx}`}
              className={`pl-2 py-1 ${BAND_CLASS[cat]} ${flash ? 'kin-flash-highlight' : ''} hover:bg-subtle/60 transition-colors`}
            >
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[12px] text-ink">
                  {env.payload.event}
                </span>
                <span className="font-mono text-[10.5px] text-muted tabular-nums">
                  {deltaSeconds(env.at, prev)}
                </span>
              </div>
              {payloadEntries(env).length > 0 && (
                <div className="mt-0.5 font-mono text-[11px] leading-snug">
                  {payloadEntries(env).map(([k, v]) => (
                    <span key={k} className="mr-2">
                      <span className="text-muted">{k}=</span>
                      <span className="text-ink">{String(v)}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
      <div className="mt-1 font-mono text-[10.5px] text-muted/70 text-right">
        {events.length} event{events.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
