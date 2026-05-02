/* deriveToolCalls — pure function over StructlogEnvelope[].

   Test 4 per S3 plan: verifies that a tool_call_invoked + tool_call_returned
   pair produces a single resolved ToolCall. No React, no rendering — pure
   function, testable in isolation from the UI. */
import { describe, it, expect } from 'vitest';
import { deriveToolCalls } from './toolCalls';
import type { StructlogEnvelope } from '../lib/sseEnvelope';

function makeEnvelope(event: string, extras: Record<string, unknown> = {}, atOffset = 0): StructlogEnvelope {
  return {
    type: 'structlog_event',
    at: new Date(1000 + atOffset).toISOString(),
    source_device_id: null,
    payload: { event, level: 'info', timestamp: new Date(1000 + atOffset).toISOString(), ...extras },
  };
}

describe('deriveToolCalls', () => {
  it('returns empty array for empty event stream', () => {
    expect(deriveToolCalls([])).toEqual([]);
  });

  it('returns empty array when no tool_call_* events present', () => {
    const events = [
      makeEnvelope('pipeline_start'),
      makeEnvelope('whisper_transcribe_start'),
    ];
    expect(deriveToolCalls(events)).toEqual([]);
  });

  it('Test 4 — pairs invoked + returned into a single resolved call', () => {
    // Pure-function derivation: two events → one resolved ToolCall.
    // This is the architectural property: deriveToolCalls(events) === expected_state.
    const events = [
      makeEnvelope('pipeline_start', {}, 0),
      makeEnvelope('tool_call_invoked', { model: 'gemma4:e2b', tool_count: '2' }, 500),
      makeEnvelope('tool_call_returned', {
        tool_name: 'fill_rfl_record',
        tool_args: { full_name: 'Carlos', age: 7 },
        latency_s: 1.4,
      }, 1900),
    ];

    const calls = deriveToolCalls(events);

    expect(calls).toHaveLength(1);
    const call = calls[0];
    expect(call.name).toBe('fill_rfl_record');
    expect(call.status).toBe('resolved');
    expect(call.args).toEqual({ full_name: 'Carlos', age: 7 });
    expect((call.result as Record<string, unknown>).latency_s).toBe(1.4);
    // tMs is relative to first event (pipeline_start at offset 0)
    expect(call.tMs).toBeGreaterThan(0);
  });

  it('started row has placeholder name before returned event arrives', () => {
    const events = [
      makeEnvelope('tool_call_invoked', { model: 'gemma4:e2b' }, 0),
    ];
    const calls = deriveToolCalls(events);
    expect(calls).toHaveLength(1);
    expect(calls[0].status).toBe('started');
    expect(calls[0].name).toBe('…');
    expect(calls[0].args).toBeNull();
  });

  it('unmatched returned event (no prior invoked) is silently ignored', () => {
    const events = [
      makeEnvelope('tool_call_returned', { tool_name: 'flag_minor', latency_s: 0.5 }, 0),
    ];
    expect(deriveToolCalls(events)).toEqual([]);
  });

  it('two sequential calls resolve independently (FIFO pairing)', () => {
    const events = [
      makeEnvelope('tool_call_invoked', {}, 100),
      makeEnvelope('tool_call_invoked', {}, 200),
      makeEnvelope('tool_call_returned', { tool_name: 'flag_minor', tool_args: { age: 8 }, latency_s: 0.9 }, 1100),
      makeEnvelope('tool_call_returned', { tool_name: 'fill_rfl_record', tool_args: { full_name: 'Ana' }, latency_s: 1.2 }, 1400),
    ];

    const calls = deriveToolCalls(events);
    expect(calls).toHaveLength(2);
    expect(calls[0].name).toBe('flag_minor');
    expect(calls[0].status).toBe('resolved');
    expect(calls[1].name).toBe('fill_rfl_record');
    expect(calls[1].status).toBe('resolved');
  });
});
