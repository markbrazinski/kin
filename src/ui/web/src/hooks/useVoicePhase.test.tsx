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

    // POST resolves completed -> done, isCrisis still true (set by structlog event)
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [
        structlog('crisis_path_taken'),
        structlog('tool_call_invoked'),
      ],
      lastPostStatus: 'completed',
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

  it('S5 dry-run regression: turn 2 POST=completed advances to done even when turn 1 also ended completed', () => {
    /* Production scenario surfaced in S5 manual dry-run: phase
       stuck on Stop because turn 2's setLastPostStatus('completed')
       didn't fire POST_RESOLVED. Root cause: pre-fix BEGIN action
       set lastConsumedPostStatus = currentPostStatus
       (= 'completed' from turn 1), so when turn 2 settled on
       'completed' the watcher saw equal values and short-circuited.
       Fix: BEGIN resets lastConsumedPostStatus to null, with the
       watcher phase-gated to {transcribing, extracting} so a stale
       'completed' lingering during awaiting can't fire spuriously. */

    // Turn 1 happy-path through to done.
    const { result, rerender } = renderHook(
      (props: Inputs) => useVoicePhase(props),
      { initialProps: initial },
    );
    act(() => result.current.onBegin());
    rerender({ ...initial, micState: 'recording' });
    act(() => result.current.onStop());
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [structlog('tool_call_invoked')],
      lastPostStatus: 'completed',
    });
    expect(result.current.phase).toBe('done');

    // Turn 2: BEGIN. In production, VoicePanel calls
    // setLastPostStatus(null) synchronously after phaseBegin(), but
    // React state updates batch — the next render still has
    // lastPostStatus='completed' for one tick.
    act(() => result.current.onBegin());
    expect(result.current.phase).toBe('awaiting');

    // Stale 'completed' lingering during awaiting must NOT fire
    // POST_RESOLVED (phase gate keeps awaiting safe).
    rerender({
      ...initial,
      micState: 'idle',
      lastPostStatus: 'completed',
    });
    expect(result.current.phase).toBe('awaiting');

    // setLastPostStatus(null) lands.
    rerender({ ...initial, micState: 'idle', lastPostStatus: null });
    expect(result.current.phase).toBe('awaiting');

    // Mic recording → recording. POST sent at Stop. POST resolves
    // back to 'completed' during extracting. Phase MUST advance to
    // done (the bug surfaced when this stuck on extracting). The
    // structlog array carries turn 1's tool_call_invoked plus a
    // fresh turn 2 one (real SSE accumulates events; the high-
    // water-mark in the hook only fires on NEW past-mark events).
    rerender({ ...initial, micState: 'recording', lastPostStatus: null });
    expect(result.current.phase).toBe('recording');
    act(() => result.current.onStop());
    expect(result.current.phase).toBe('transcribing');
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [
        structlog('tool_call_invoked'),  // turn 1 carry-over
        structlog('tool_call_invoked'),  // turn 2 fresh
      ],
      lastPostStatus: null,
    });
    expect(result.current.phase).toBe('extracting');
    // POST resolves: the dry-run STUCK happened here pre-fix because
    // lastConsumedPostStatus was still 'completed' from turn 1's
    // BEGIN action. With the fix (BEGIN resets to null), this fires.
    rerender({
      ...initial,
      micState: 'idle',
      structlogEvents: [
        structlog('tool_call_invoked'),
        structlog('tool_call_invoked'),
      ],
      lastPostStatus: 'completed',
    });
    expect(result.current.phase).toBe('done');
  });
});
