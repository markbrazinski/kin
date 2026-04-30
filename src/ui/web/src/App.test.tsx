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
    candidate_count?: number;
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

function makeMatchProposedEvent(
  id: string,
  opts: { candidateCount?: number; recordIds?: string[] } = {},
): MockAuditEvent {
  const recordIds = opts.recordIds ?? ['rec-a', 'rec-b'];
  return {
    type: 'audit_event',
    payload: {
      id,
      at: new Date().toISOString(),
      event_type: 'match_proposed',
      record_ids: recordIds,
      match_id: 'match-' + id,
      actor: 'kin_system',
      details: {},
      candidate_count: opts.candidateCount ?? 1,
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

describe('App — Beat 6 match candidate badge (S5)', () => {
  it('match_proposed arrival does NOT surface MatchToast (S2-fix2 closure regression)', () => {
    /* Pre-S5: match_proposed surfaced a bottom-right toast with
       "Match candidate found" + Open match / Dismiss buttons. S5
       deletes MatchToast in favor of the queue rail badge. This
       test guards against accidental re-introduction. */
    const { rerender, queryByText, queryByRole } = render(<App />);
    mockAuditEvents = [makeMatchProposedEvent('e-1', { candidateCount: 2 })];
    rerender(<App />);

    expect(queryByText('Match candidate found')).toBeNull();
    expect(queryByRole('button', { name: 'Open match' })).toBeNull();
    expect(queryByRole('button', { name: 'Dismiss' })).toBeNull();
    // View stays in single mode — multi-turn flow uninterrupted.
    expect(queryByText('Reunification candidate')).toBeNull();
  });

  it('match_proposed updates the queue rail badge via getActiveMatchCount', () => {
    /* Bundle 1.5 S5: the new candidate-count flow drives the queue
       rail badge. record_ids[0] is the new-record key per the
       ordering convention; candidate_count > 0 contributes to
       getActiveMatchCount. */
    const { rerender, container } = render(<App />);

    // Initial: badge is hidden (no active candidates).
    const queueBeforeBtn = screen.getByLabelText('Queue');
    expect(queueBeforeBtn.querySelector('span.bg-primary.text-white')).toBeNull();

    // match_proposed arrives with 1 candidate for intake "rec-a".
    mockAuditEvents = [
      makeMatchProposedEvent('e-1', {
        candidateCount: 1,
        recordIds: ['rec-a', 'rec-b'],
      }),
    ];
    rerender(<App />);

    // Badge now visible on the Queue button (RailNav renders a span
    // with bg-primary + text-white when queuedCount is truthy).
    const queueAfterBtn = screen.getByLabelText('Queue');
    const badge = queueAfterBtn.querySelector('span.bg-primary.text-white');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toBe('1');

    void container;
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
