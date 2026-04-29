/* IntakePanel split-view tests — verifies per-device subscription
   isolation and tent attribute rendering. */
import { describe, it, expect, beforeEach } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MockEventSource } from '../test-utils/MockEventSource';
import { IntakePanel } from './IntakePanel';
import type { EventSourceFactory } from '../hooks/useEventStream';
import type { AuditEnvelope } from '../lib/sseEnvelope';

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
  lang: 'en' as const,
  phase: 'ready' as const,
  timerSec: 0,
  timerRunning: false,
  onBegin: () => {},
  crisisOpen: false,
};

beforeEach(() => {
  MockEventSource.reset();
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
