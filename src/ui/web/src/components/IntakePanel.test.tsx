/* IntakePanel split-view tests — verifies per-device subscription
   isolation, tent attribute rendering, and SimpleVoicePanel phase UI. */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MockEventSource } from '../test-utils/MockEventSource';
import type { EventSourceFactory } from '../hooks/useEventStream';
import type { AuditEnvelope } from '../lib/sseEnvelope';

/* Mockable voice phase for the SimpleVoicePanel parameterized
   render test below. The 5 existing tests don't assert phase strings,
   so they pass regardless of the mocked default ('ready'). */
const mockPhase = {
  current: 'ready' as 'ready' | 'awaiting' | 'recording' | 'transcribing' | 'extracting' | 'done',
};
vi.mock('../hooks/useVoicePhase', () => ({
  useVoicePhase: () => ({
    phase: mockPhase.current,
    isCrisis: false,
    onBegin: vi.fn(),
    onStop: vi.fn(),
    reset: vi.fn(),
  }),
}));

import { IntakePanel } from './IntakePanel';
import { voiceCopy } from '../lib/voiceCopy';

const factory: EventSourceFactory = (url) =>
  new MockEventSource(url) as unknown as ReturnType<EventSourceFactory>;

function makeFieldExtractedEnvelope(value: string): AuditEnvelope {
  return {
    type: 'audit_event',
    at: '2026-04-28T12:00:00Z',
    source_device_id: null,
    payload: {
      id: '00000000-0000-0000-0000-000000000001',
      at: '2026-04-28T12:00:00Z',
      event_type: 'field_extracted',
      record_ids: ['00000000-0000-0000-0000-000000000099'],
      match_id: null,
      actor: 'kin_system',
      details: {
        field_name: 'full_name_source_script',
        value,
      },
    },
  };
}

const baseProps = {
  workerLanguage: 'en' as const,
  speakerLanguage: 'en' as const,
  timerSec: 0,
  timerRunning: false,
  crisisOpen: false,
};

beforeEach(() => {
  MockEventSource.reset();
  mockPhase.current = 'ready';
});

describe('IntakePanel', () => {
  it('opens an EventSource at the source-device-filtered URL', () => {
    render(
      <IntakePanel
        sourceDeviceId="tent_a"
        tent="a"
        panelLabel="Tent A"
        eventSourceFactory={factory}
        {...baseProps}
      />,
    );
    const es = MockEventSource.last()!;
    expect(es.url).toBe('/intake/stream?source_device_id=tent_a');
  });

  it('isolates per-device state across two panels — tent_a event does not affect tent_b', () => {
    render(
      <div>
        <IntakePanel
          sourceDeviceId="tent_a"
          tent="a"
          panelLabel="Tent A"
          eventSourceFactory={factory}
          {...baseProps}
        />
        <IntakePanel
          sourceDeviceId="tent_b"
          tent="b"
          panelLabel="Tent B"
          eventSourceFactory={factory}
          {...baseProps}
        />
      </div>,
    );

    expect(MockEventSource.instances).toHaveLength(2);
    const [esA, esB] = MockEventSource.instances;
    expect(esA.url).toContain('tent_a');
    expect(esB.url).toContain('tent_b');

    /* Emit on the tent_a stream only. */
    act(() => {
      esA.emit('audit_event', JSON.stringify(makeFieldExtractedEnvelope('Carlos')));
    });

    /* Find each panel's RecordCard via the data-tent root. The name
       field renders the value verbatim somewhere in the tent_a tree
       and not in the tent_b tree. */
    const panelA = document.querySelector('[data-tent="a"]')!;
    const panelB = document.querySelector('[data-tent="b"]')!;
    expect(panelA.textContent).toContain('Carlos');
    expect(panelB.textContent).not.toContain('Carlos');
  });

  it('applies data-tent attribute matching the tent prop', () => {
    const { container } = render(
      <IntakePanel
        sourceDeviceId="tent_b"
        tent="b"
        panelLabel="Tent B"
        eventSourceFactory={factory}
        {...baseProps}
      />,
    );
    const root = container.querySelector('[data-tent]')!;
    expect(root.getAttribute('data-tent')).toBe('b');
    /* screen reference unused; suppress lint via void. */
    void screen;
  });

  it('renders the transliteration field when record.name is non-Latin', () => {
    const { container } = render(
      <IntakePanel
        sourceDeviceId="tent_b"
        tent="b"
        panelLabel="Tent B"
        eventSourceFactory={factory}
        {...baseProps}
      />,
    );
    const es = MockEventSource.last()!;
    act(() => {
      es.emit('audit_event', JSON.stringify(makeFieldExtractedEnvelope('محمد')));
    });
    const input = container.querySelector(
      'input[aria-label="Transliteration"]',
    );
    expect(input).not.toBeNull();
  });

  it('hides the transliteration field for a Latin-script name', () => {
    const { container } = render(
      <IntakePanel
        sourceDeviceId="tent_a"
        tent="a"
        panelLabel="Tent A"
        eventSourceFactory={factory}
        {...baseProps}
      />,
    );
    const es = MockEventSource.last()!;
    act(() => {
      es.emit('audit_event', JSON.stringify(makeFieldExtractedEnvelope('Carlos')));
    });
    const input = container.querySelector(
      'input[aria-label="Transliteration"]',
    );
    expect(input).toBeNull();
  });
});

describe('SimpleVoicePanel — parameterized phase render (compact UI)', () => {
  type Phase = 'ready' | 'awaiting' | 'recording' | 'transcribing' | 'extracting' | 'done';
  const ALL_PHASES: Phase[] = ['ready', 'awaiting', 'recording', 'transcribing', 'extracting', 'done'];
  const SHOW_BEGIN: Phase[] = ['ready', 'done'];
  const SHOW_STOP_COMPACT: Phase[] = ['recording'];

  for (const phase of ALL_PHASES) {
    it(`compact panel renders correctly for phase=${phase}`, () => {
      mockPhase.current = phase;
      const { unmount } = render(
        <IntakePanel
          sourceDeviceId="tent_a"
          tent="a"
          panelLabel="Tent A"
          eventSourceFactory={factory}
          {...baseProps}
        />,
      );

      // Caption matches voiceCopy[phase].en, with aria-live polite.
      const caption = screen.getByText(voiceCopy[phase].en);
      const liveRegion = caption.closest('[aria-live="polite"]');
      expect(liveRegion).not.toBeNull();

      // Begin in {ready, done} only.
      const beginBtn = screen.queryByRole('button', { name: 'Begin' });
      if (SHOW_BEGIN.includes(phase)) {
        expect(beginBtn).not.toBeNull();
      } else {
        expect(beginBtn).toBeNull();
      }

      // Stop in compact mode is recording only (compact UI doesn't
      // surface Stop during transcribing/extracting since useMicCapture
      // already returned to idle and the compact row stays terse).
      const stopBtn = screen.queryByRole('button', { name: 'Stop' });
      if (SHOW_STOP_COMPACT.includes(phase)) {
        expect(stopBtn).not.toBeNull();
        expect(stopBtn!.className).toMatch(/\btext-red\b/);
      } else {
        expect(stopBtn).toBeNull();
      }

      unmount();
    });
  }
});

describe('IntakePanel — S3 marks bubble fix regression', () => {
  it('Test 5 — Marks section shows as filled when distinguishing_marks is populated', () => {
    /* Regression guard for the bug where `filled: !!(record.physicalDesc
       && record.features)` never fired because record.features has no
       FIELD_MAP entry. Fixed to `filled: !!record.physicalDesc`. */
    const { container } = render(
      <IntakePanel
        sourceDeviceId="tent_a"
        tent="a"
        panelLabel="Tent A"
        eventSourceFactory={factory}
        {...baseProps}
      />,
    );
    const es = MockEventSource.last()!;

    // Emit distinguishing_marks field_extracted event
    act(() => {
      es.emit(
        'audit_event',
        JSON.stringify({
          type: 'audit_event',
          at: '2026-05-02T10:00:00Z',
          source_device_id: 'tent_a',
          payload: {
            id: '00000000-0000-0000-0000-000000000002',
            at: '2026-05-02T10:00:00Z',
            event_type: 'field_extracted',
            record_ids: ['00000000-0000-0000-0000-000000000099'],
            match_id: null,
            actor: 'kin_system',
            details: { field_name: 'distinguishing_marks', value: 'marca en la mejilla derecha' },
          },
        }),
      );
    });

    // The completeness meter "N of M sections" count increases when
    // Marks is filled. The segment bar for Marks gets bg-primary when filled.
    const filledBars = container.querySelectorAll('.bg-primary.border-primary');
    expect(filledBars.length).toBeGreaterThan(0);

    // The "Marks" label is visible in the meter
    expect(container.textContent).toContain('Marks');
  });
});
