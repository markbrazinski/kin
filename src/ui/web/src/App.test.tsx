/* App-level Beat 6 tests — S2-fix1 toast-driven match navigation.

   Per S2-fix1, match_proposed events surface as a MatchToast (not
   auto-route). User clicks "Open match" to navigate. Idempotency
   preserved via matchToastFiredRef so a second match_proposed
   doesn't re-show the toast within a session.

   We mock useEventStream and useMicCapture so the App harness is
   testable without real EventSource or MediaRecorder. The reducer
   state we feed in is the contract the App-level useEffect reads
   from. */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act, fireEvent, screen } from '@testing-library/react';

// Mutable mock state — tests update this between renders to simulate
// incoming SSE events.
type MockAuditEvent = {
  type: 'audit_event';
  payload: {
    id: string;
    at: string;
    event_type: string;
    record_ids: string[];
    match_id: string | null;
    actor: string;
    details: Record<string, unknown>;
  };
};

let mockAuditEvents: MockAuditEvent[] = [];

vi.mock('./hooks/useEventStream', () => ({
  useEventStream: () => ({
    state: {
      record: {
        name: '', age: '', relationship: '',
        lastSeenLocation: '', lastSeenLocationSource: 'speaker' as const,
        lastSeenDate: '', physicalDesc: '',
        guardian: { name: '', relationship: '', contact: '' },
      },
      auditEvents: mockAuditEvents,
      structlogEvents: [],
      connection: 'open' as const,
      intakeId: null,
    },
    connection: 'open' as const,
    reset: vi.fn(),
    clearIntakeId: vi.fn(),
  }),
}));

vi.mock('./hooks/useMicCapture', () => ({
  useMicCapture: () => ({
    state: 'idle' as const,
    start: vi.fn(),
    stop: vi.fn(),
    error: null,
  }),
}));

vi.mock('./lib/api', () => ({
  uploadAudioBlob: vi.fn(),
  postTransliteration: vi.fn(),
}));

import App from './App';

function makeMatchProposedEvent(id: string): MockAuditEvent {
  return {
    type: 'audit_event',
    payload: {
      id,
      at: new Date().toISOString(),
      event_type: 'match_proposed',
      record_ids: ['rec-a', 'rec-b'],
      match_id: 'match-' + id,
      actor: 'kin_system',
      details: {},
    },
  };
}

beforeEach(() => {
  mockAuditEvents = [];
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('App — Beat 6 MatchToast (S2-fix1)', () => {
  it('match_proposed surfaces toast WITHOUT auto-navigating away from intake', () => {
    const { rerender, queryByText, queryByRole } = render(<App />);
    // No match yet → no toast, view stays in single mode.
    expect(queryByText('Match candidate found')).toBeNull();
    expect(queryByText('Reunification candidate')).toBeNull();

    // match_proposed arrives mid-intake.
    mockAuditEvents = [makeMatchProposedEvent('e-1')];
    rerender(<App />);

    // Toast renders.
    expect(queryByText('Match candidate found')).not.toBeNull();
    // BUT view stays in single mode — user can keep recording the
    // next utterance. This is the demo Beat 5 fix: multi-turn flows
    // don't get hijacked by an auto-navigation.
    expect(queryByText('Reunification candidate')).toBeNull();
    // "Open match" button is present and waiting for the click.
    expect(queryByRole('button', { name: 'Open match' })).not.toBeNull();
  });

  it('clicking "Open match" navigates to match view and steps phase machine', () => {
    const { rerender, queryByText } = render(<App />);
    mockAuditEvents = [makeMatchProposedEvent('e-1')];
    rerender(<App />);

    const openBtn = screen.getByRole('button', { name: 'Open match' });
    act(() => { fireEvent.click(openBtn); });

    // View now in match mode (the "Reunification candidate" header
    // is the unique anchor on the match view).
    expect(queryByText('Reunification candidate')).not.toBeNull();
    expect(queryByText('Match confirmed')).toBeNull();

    // Toast dismissed itself on click.
    expect(queryByText('Match candidate found')).toBeNull();

    // Phase machine steps: split → linking at 400ms, → merged at 1100ms.
    act(() => { vi.advanceTimersByTime(400); });
    expect(queryByText('Match confirmed')).toBeNull();

    act(() => { vi.advanceTimersByTime(700); });
    expect(queryByText('Match confirmed')).not.toBeNull();
  });

  it('idempotent: a second match_proposed does NOT re-show the toast', () => {
    const { rerender, queryByText } = render(<App />);

    // First match_proposed → toast renders.
    mockAuditEvents = [makeMatchProposedEvent('e-1')];
    rerender(<App />);
    expect(queryByText('Match candidate found')).not.toBeNull();

    // User dismisses the toast.
    const dismissBtn = screen.getByRole('button', { name: 'Dismiss' });
    act(() => { fireEvent.click(dismissBtn); });
    expect(queryByText('Match candidate found')).toBeNull();

    // A second match_proposed arrives. matchToastFiredRef
    // short-circuits the watcher; toast stays dismissed.
    mockAuditEvents = [
      makeMatchProposedEvent('e-1'),
      makeMatchProposedEvent('e-2'),
    ];
    rerender(<App />);
    expect(queryByText('Match candidate found')).toBeNull();
  });
});

describe('App — S6 worker/speaker language separation', () => {
  it('clicking the AR speaker selector flips speakerLanguage AND keeps chrome English (regression check)', () => {
    /* The bug this guards against: pre-S6, clicking AR flipped the
       entire UI (chrome + content) to Arabic RTL. Per S6, the
       selector must only affect speakerLanguage; chrome stays
       English (workerLanguage='en'). */
    render(<App />);

    // Pre-click: Begin button visible in English ("Comenzar" would
    // mean Spanish chrome leaked in; "Begin" is the workerLanguage='en'
    // expected). Other chrome anchor: aria-pressed="true" on EN.
    const beginBefore = screen.getByRole('button', { name: 'Begin' });
    expect(beginBefore).toBeTruthy();

    const arButton = screen.getByRole('button', { name: 'AR' });
    expect(arButton.getAttribute('aria-pressed')).toBe('false');

    act(() => { fireEvent.click(arButton); });

    // After click: AR is now active in the selector …
    expect(arButton.getAttribute('aria-pressed')).toBe('true');
    // … but the Begin button is STILL English (chrome unchanged).
    // If S6 regressed, we'd see "ابدأ" here instead.
    expect(screen.getByRole('button', { name: 'Begin' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'ابدأ' })).toBeNull();
  });

  it('all 5 speaker codes (ES/AR/FA/FR/UK) plus EN are clickable in the selector', () => {
    render(<App />);
    for (const code of ['EN', 'ES', 'AR', 'FA', 'FR', 'UK']) {
      const btn = screen.queryByRole('button', { name: code });
      expect(btn).not.toBeNull();
    }
  });
});
