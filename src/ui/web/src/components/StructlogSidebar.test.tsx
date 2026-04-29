import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StructlogSidebar } from './StructlogSidebar';
import type { StructlogEnvelope } from '../lib/sseEnvelope';

function makeEnvelope(event: string, at: string): StructlogEnvelope {
  return {
    type: 'structlog_event',
    at,
    source_device_id: 'tent_a',
    payload: {
      event,
      level: 'info',
      timestamp: at,
    },
  };
}

describe('StructlogSidebar', () => {
  it('renders events from the events prop in arrival order', () => {
    const events: StructlogEnvelope[] = [
      makeEnvelope('whisper_transcribe_start', '2026-04-28T12:00:00.000Z'),
      makeEnvelope('ollama_translate_invoked', '2026-04-28T12:00:00.450Z'),
      makeEnvelope('tool_call_invoked', '2026-04-28T12:00:01.200Z'),
    ];

    const { container } = render(<StructlogSidebar events={events} />);
    const text = container.textContent ?? '';

    /* Event names appear in DOM in order. indexOf on the rendered
       text confirms ordering without relying on a query selector
       that might miss font-mono spans. */
    const i1 = text.indexOf('whisper_transcribe_start');
    const i2 = text.indexOf('ollama_translate_invoked');
    const i3 = text.indexOf('tool_call_invoked');
    expect(i1).toBeGreaterThanOrEqual(0);
    expect(i2).toBeGreaterThan(i1);
    expect(i3).toBeGreaterThan(i2);
  });

  it('shows an empty-state placeholder when events is empty', () => {
    const { container } = render(<StructlogSidebar events={[]} />);
    expect(container.textContent).toContain('Waiting for events');
  });
});
