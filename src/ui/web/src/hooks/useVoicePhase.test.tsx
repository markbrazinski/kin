/* Bundle 1.5 S2 — useVoicePhase hook tests.
   - Happy-path 6-phase walk
   - Crisis branch (walks through extracting, isCrisis flag set)
   - Mic-error doesn't crash machine (resets to ready)
   - Turn 1 -> turn 2: high-water-marks prevent stale-event re-trigger
*/
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useVoicePhase } from './useVoicePhase';
import type {
  AuditEnvelope,
  StructlogEnvelope,
} from '../lib/sseEnvelope';
import type { MicState } from './useMicCapture';
import type { PostStatus } from './useVoicePhase';

function structlog(event: string): StructlogEnvelope {
  return {
    type: 'structlog_event',
    at: new Date().toISOString(),
    source_device_id: null,
    payload: { event },
  };
}

function audit(event_type: AuditEnvelope['payload']['event_type']): AuditEnvelope {
  return {
    type: 'audit_event',
    at: new Date().toISOString(),
    source_device_id: null,
    payload: {
      id: `aud-${Math.random().toString(36).slice(2, 8)}`,
      at: new Date().toISOString(),
      event_type,
      record_ids: [],
      match_id: null,
      actor: 'kin_system',
      details: {},
    },
  };
}

type Inputs = {
  micState: MicState;
  auditEvents: AuditEnvelope[];
  structlogEvents: StructlogEnvelope[];
  lastPostStatus: PostStatus | null;
};

const initial: Inputs = {
  micState: 'idle',
  auditEvents: [],
  structlogEvents: [],
  lastPostStatus: null,
};

describe('useVoicePhase', () => {
  it('walks through 6 phases on a happy-path turn', () => {
    const { result, rerender } = renderHook(
      (props: Inputs) => useVoicePhase(props),
      { initialProps: initial },
    );

    expect(result.current.phase).toBe('ready');

    // Begin -> awaiting
    act(() => result.current.onBegin());
    expect(result.current.phase).toBe('awaiting');

    // Mic recording -> recording
    rerender({ ...initial, micState: 'recording' });
    expect(result.current.phase).toBe('recording');

    // Stop -> transcribing
    act(() => result.current.onStop());
    expect(result.current.phase).toBe('transcribing');

    // tool_call_invoked -> extracting
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [structlog('tool_call_invoked')],
    });
    expect(result.current.phase).toBe('extracting');

    // intake_created arriving while extracting is idempotent
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [structlog('tool_call_invoked')],
      auditEvents: [audit('intake_created')],
    });
    expect(result.current.phase).toBe('extracting');

    // POST resolves -> done
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [structlog('tool_call_invoked')],
      auditEvents: [audit('intake_created')],
      lastPostStatus: 'completed',
    });
    expect(result.current.phase).toBe('done');
    expect(result.current.isCrisis).toBe(false);
  });

  it('handles the crisis branch — walks through extracting, sets isCrisis', () => {
    const { result, rerender } = renderHook(
      (props: Inputs) => useVoicePhase(props),
      { initialProps: initial },
    );

    act(() => result.current.onBegin());
    rerender({ ...initial, micState: 'recording' });
    act(() => result.current.onStop());
    expect(result.current.phase).toBe('transcribing');

    // crisis_path_taken arrives on the structlog stream
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [structlog('crisis_path_taken')],
    });
    expect(result.current.isCrisis).toBe(true);
    // Crisis alone doesn't advance phase (Gemma's tool_call_invoked does)
    expect(result.current.phase).toBe('transcribing');

    // escalate_crisis tool_call fires -> extracting (same event name)
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [
        structlog('crisis_path_taken'),
        structlog('tool_call_invoked'),
      ],
    });
    expect(result.current.phase).toBe('extracting');

    // POST resolves paused_for_crisis -> done, isCrisis still true
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [
        structlog('crisis_path_taken'),
        structlog('tool_call_invoked'),
      ],
      lastPostStatus: 'paused_for_crisis',
    });
    expect(result.current.phase).toBe('done');
    expect(result.current.isCrisis).toBe(true);
  });

  it('mic-error mid-flow resets phase to ready (permission-denial recovery)', () => {
    const { result, rerender } = renderHook(
      (props: Inputs) => useVoicePhase(props),
      { initialProps: initial },
    );

    act(() => result.current.onBegin());
    expect(result.current.phase).toBe('awaiting');

    // Permission denied: useMicCapture flips state to 'error'
    rerender({ ...initial, micState: 'error' });
    expect(result.current.phase).toBe('ready');

    // User can retry Begin cleanly
    act(() => result.current.onBegin());
    expect(result.current.phase).toBe('awaiting');
  });

  it('turn 1 -> turn 2: stale events do not re-trigger transitions (high-water-marks)', () => {
    const { result, rerender } = renderHook(
      (props: Inputs) => useVoicePhase(props),
      { initialProps: initial },
    );

    // Complete turn 1 fully.
    act(() => result.current.onBegin());
    rerender({ ...initial, micState: 'recording' });
    act(() => result.current.onStop());
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [structlog('tool_call_invoked')],
    });
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [structlog('tool_call_invoked')],
      auditEvents: [audit('intake_created')],
      lastPostStatus: 'completed',
    });
    expect(result.current.phase).toBe('done');

    // Turn 2: Begin clicked. Stale events from turn 1 are still in
    // the arrays (the SSE reducer accumulates them) but must NOT
    // re-advance phase.
    act(() => result.current.onBegin());
    expect(result.current.phase).toBe('awaiting');

    // Re-render with the same stale arrays: phase must stay
    // 'awaiting', NOT jump to 'extracting' from the stale
    // tool_call_invoked.
    rerender({
      micState: 'idle',
      structlogEvents: [structlog('tool_call_invoked')],
      auditEvents: [audit('intake_created')],
      lastPostStatus: 'completed',
    });
    expect(result.current.phase).toBe('awaiting');

    // New mic-recording transition for turn 2 advances normally.
    rerender({
      micState: 'recording',
      structlogEvents: [structlog('tool_call_invoked')],
      auditEvents: [audit('intake_created')],
      lastPostStatus: 'completed',
    });
    expect(result.current.phase).toBe('recording');
  });
});
