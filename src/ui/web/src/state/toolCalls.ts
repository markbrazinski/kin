/* Pure derivation of ToolCall[] from the structlog event stream.

   Tool-call events arrive as StructlogEnvelope objects (not audit events):
     tool_call_invoked  — fired before Gemma inference; has no tool_name yet
     tool_call_returned — fired after Gemma returns; has tool_name + tool_args

   Pairing is FIFO by insertion order. ADR-004 single-shot constraint
   guarantees Gemma issues at most one tool call per turn, so FIFO is safe. */
import type { StructlogEnvelope } from '../lib/sseEnvelope';

export type ToolCall = {
  id: string;
  name: string;
  /* 'error' is reserved for future error-event integration; no current
     structlog event produces it — present in the type so the left-rule
     color map is complete and code paths are explicit. */
  status: 'started' | 'resolved' | 'error';
  args: Record<string, unknown> | null;
  result: unknown;
  tMs: number;
};

export function deriveToolCalls(events: StructlogEnvelope[]): ToolCall[] {
  if (events.length === 0) return [];
  const t0 = Date.parse(events[0].at);
  const calls: ToolCall[] = [];
  const pendingIndices: number[] = [];

  for (const env of events) {
    const evName = env.payload.event as string;
    const tMs = Date.parse(env.at) - t0;

    if (evName === 'tool_call_invoked') {
      const idx = calls.length;
      calls.push({
        id: `call-${idx}`,
        name: '…',
        status: 'started',
        args: null,
        result: undefined,
        tMs,
      });
      pendingIndices.push(idx);
    } else if (evName === 'tool_call_returned') {
      const name = (env.payload.tool_name as string | undefined) ?? 'unknown';
      const callIdx = pendingIndices.shift();
      if (callIdx !== undefined) {
        calls[callIdx] = {
          ...calls[callIdx],
          id: `${name}-${callIdx}`,
          name,
          status: 'resolved',
          args: (env.payload.tool_args as Record<string, unknown> | undefined) ?? null,
          result: { latency_s: env.payload.latency_s },
          tMs,
        };
      }
    }
  }
  return calls;
}
