/* useVoicePhase — 6-phase voice panel state machine driven by SSE
   structlog/audit arrivals + local mic state + POST resolution.

   Per design ref nav-app.jsx:14-19, the six phases each map to a
   structlog signal and a Waveform visual state. Collapsing them was
   tried and rejected — judges want to see each phase as evidence the
   system is doing real work.

   Phase signals (recon-verified):
     ready       initial / explicit reset / done -> Begin
     awaiting    Begin clicked, mic permission flow in progress
     recording   useMicCapture state === 'recording'
     transcribing  Stop clicked (synchronous; useMicCapture flips
                   processing -> idle in the same tick, so we cannot
                   drive this phase off mic state)
     extracting  structlog tool_call_invoked arrives
     done        POST resolves with status completed

   Crisis branch walks through extracting (Gemma's escalate_crisis
   tool_call DOES fire — same event name, same phase advance), then
   to done. isCrisis flag is set independently when a structlog
   crisis_path_taken event arrives.

   High-water-marks (seenAuditCount, seenStructlogCount) prevent
   re-processing stale events when consuming components re-render.
   BEGIN does NOT reset the marks — turn 2 picks up where turn 1
   stopped. RESET does reset both.
*/
import { useCallback, useEffect, useReducer, useRef } from 'react';
import type { MicState } from './useMicCapture';
import type { AuditEnvelope, StructlogEnvelope } from '../lib/sseEnvelope';

export type VoicePhase =
  | 'ready'
  | 'awaiting'
  | 'recording'
  | 'transcribing'
  | 'extracting'
  | 'done'
  | 'saved';

export type PostStatus = 'completed';

export type VoicePhaseInputs = {
  micState: MicState;
  auditEvents: AuditEnvelope[];
  structlogEvents: StructlogEnvelope[];
  lastPostStatus: PostStatus | null;
};

export type VoicePhaseResult = {
  phase: VoicePhase;
  isCrisis: boolean;
  onBegin: () => void;
  onStop: () => void;
  onSaved: () => void;
  reset: () => void;
};

type State = {
  phase: VoicePhase;
  isCrisis: boolean;
  seenAuditCount: number;
  seenStructlogCount: number;
  lastConsumedPostStatus: PostStatus | null;
};

type Action =
  | { type: 'BEGIN' }
  | { type: 'STOP' }
  | { type: 'RESET' }
  | { type: 'SAVED' }
  | { type: 'MIC_RECORDING' }
  | { type: 'MIC_ERROR' }
  | { type: 'STRUCTLOG_BATCH'; sawToolCallInvoked: boolean; sawCrisisPathTaken: boolean; newCount: number }
  | { type: 'AUDIT_BATCH'; sawIntakeCreated: boolean; newCount: number }
  | { type: 'POST_RESOLVED'; status: PostStatus };

const INITIAL_STATE: State = {
  phase: 'ready',
  isCrisis: false,
  seenAuditCount: 0,
  seenStructlogCount: 0,
  lastConsumedPostStatus: null,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'BEGIN':
      if (state.phase === 'ready' || state.phase === 'done' || state.phase === 'saved') {
        // S5-fix: reset lastConsumedPostStatus to null on every new
        // turn. Combined with the watcher's phase-gate (only fires
        // POST_RESOLVED when phase is transcribing/extracting), this
        // correctly handles BOTH:
        //   (a) turn 1 completed → BEGIN turn 2 → setLastPostStatus
        //       (null) propagates → no spurious fire (the original
        //       turn1→turn2 bug guarded against)
        //   (b) turn 2 POST resolves to 'completed' → watcher fires
        //       because state.lastConsumedPostStatus is null and
        //       phase is extracting (the new bug surfaced in S5
        //       dry-run where multi-turn STUCK at extracting)
        return {
          ...state,
          phase: 'awaiting',
          isCrisis: false,
          lastConsumedPostStatus: null,
        };
      }
      return state;

    case 'STOP':
      if (state.phase === 'recording') {
        return { ...state, phase: 'transcribing' };
      }
      return state;

    case 'RESET':
      return { ...INITIAL_STATE };

    case 'MIC_RECORDING':
      if (state.phase === 'awaiting') {
        return { ...state, phase: 'recording' };
      }
      return state;

    case 'MIC_ERROR':
      // Permission denial mid-flow: drop back to ready so the user
      // can retry Begin. Don't clear isCrisis (the crisis surface,
      // if open, is independent of voice readiness).
      return { ...state, phase: 'ready' };

    case 'STRUCTLOG_BATCH': {
      let phase = state.phase;
      let isCrisis = state.isCrisis;
      if (action.sawCrisisPathTaken) {
        isCrisis = true;
      }
      if (action.sawToolCallInvoked && phase === 'transcribing') {
        phase = 'extracting';
      }
      return {
        ...state,
        phase,
        isCrisis,
        seenStructlogCount: action.newCount,
      };
    }

    case 'AUDIT_BATCH': {
      let phase = state.phase;
      if (
        action.sawIntakeCreated &&
        (phase === 'transcribing' || phase === 'extracting')
      ) {
        phase = 'extracting';
      }
      return { ...state, phase, seenAuditCount: action.newCount };
    }

    case 'POST_RESOLVED':
      return {
        ...state,
        phase: 'done',
        lastConsumedPostStatus: action.status,
      };

    case 'SAVED':
      if (state.phase === 'done') {
        return { ...state, phase: 'saved' };
      }
      return state;

    default:
      return state;
  }
}

export function useVoicePhase(inputs: VoicePhaseInputs): VoicePhaseResult {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const prevMicStateRef = useRef<MicState>('idle');

  /* Mic state edge detection: feed reducer only on transitions, not
     on every render. */
  useEffect(() => {
    const prev = prevMicStateRef.current;
    if (inputs.micState !== prev) {
      if (inputs.micState === 'recording') {
        dispatch({ type: 'MIC_RECORDING' });
      } else if (inputs.micState === 'error') {
        dispatch({ type: 'MIC_ERROR' });
      }
      prevMicStateRef.current = inputs.micState;
    }
  }, [inputs.micState]);

  /* Structlog tail: examine only events past the high-water-mark. */
  useEffect(() => {
    const total = inputs.structlogEvents.length;
    if (total <= state.seenStructlogCount) return;
    const fresh = inputs.structlogEvents.slice(state.seenStructlogCount);
    let sawToolCallInvoked = false;
    let sawCrisisPathTaken = false;
    for (const env of fresh) {
      const name = env.payload?.event;
      if (name === 'tool_call_invoked') sawToolCallInvoked = true;
      if (name === 'crisis_path_taken') sawCrisisPathTaken = true;
    }
    dispatch({
      type: 'STRUCTLOG_BATCH',
      sawToolCallInvoked,
      sawCrisisPathTaken,
      newCount: total,
    });
  }, [inputs.structlogEvents, state.seenStructlogCount]);

  /* Audit tail: same pattern. */
  useEffect(() => {
    const total = inputs.auditEvents.length;
    if (total <= state.seenAuditCount) return;
    const fresh = inputs.auditEvents.slice(state.seenAuditCount);
    let sawIntakeCreated = false;
    for (const env of fresh) {
      if (env.payload?.event_type === 'intake_created') sawIntakeCreated = true;
    }
    dispatch({
      type: 'AUDIT_BATCH',
      sawIntakeCreated,
      newCount: total,
    });
  }, [inputs.auditEvents, state.seenAuditCount]);

  /* POST status edge: advance to done exactly once per turn.
     Phase-gated to {transcribing, extracting} so a stale 'completed'
     value from the previous turn (left over briefly while
     setLastPostStatus(null) propagates after BEGIN) doesn't fire
     POST_RESOLVED while phase is ready/awaiting/recording/done. The
     POST is sent at Stop click (which transitions recording ->
     transcribing); it cannot resolve before that. So legitimate
     POST_RESOLVED only ever arrives in transcribing or extracting. */
  useEffect(() => {
    if (
      inputs.lastPostStatus !== null &&
      inputs.lastPostStatus !== state.lastConsumedPostStatus &&
      (state.phase === 'transcribing' || state.phase === 'extracting')
    ) {
      dispatch({ type: 'POST_RESOLVED', status: inputs.lastPostStatus });
    }
  }, [inputs.lastPostStatus, state.lastConsumedPostStatus, state.phase]);

  const onBegin = useCallback(() => dispatch({ type: 'BEGIN' }), []);
  const onStop = useCallback(() => dispatch({ type: 'STOP' }), []);
  const onSaved = useCallback(() => dispatch({ type: 'SAVED' }), []);
  const reset = useCallback(() => dispatch({ type: 'RESET' }), []);

  return {
    phase: state.phase,
    isCrisis: state.isCrisis,
    onBegin,
    onStop,
    onSaved,
    reset,
  };
}
