/* StructlogSidebar + isMergeFlashEvent tests — S4 plan.

   6 tests replacing the prior 2 (event ordering + empty state). Covers:
   - isMergeFlashEvent predicate as a unit-testable pure function (Test 1)
   - Merge-flash class applied on matching rows (Test 2)
   - Non-merge-flash rows NOT highlighted (Test 3)
   - Class still applied under reduced-motion (Test 4; CSS static tint is
     manual-verification only)
   - Existing categorization regression: amber/red/started bands (Test 5)
   - Updated empty-state copy (Test 6) */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { StructlogSidebar } from './StructlogSidebar';
import { isMergeFlashEvent } from '../lib/mergeFlash';
import type { StructlogEnvelope } from '../lib/sseEnvelope';

function makeEnvelope(event: string, at = '2026-05-03T10:00:00.000Z'): StructlogEnvelope {
  return {
    type: 'structlog_event',
    at,
    source_device_id: 'tent_a',
    payload: { event, level: 'info', timestamp: at },
  };
}

describe('isMergeFlashEvent — pure predicate (Test 1)', () => {
  it('returns true for matching_trigger_fired', () => {
    expect(isMergeFlashEvent('matching_trigger_fired')).toBe(true);
  });
  it('returns true for matching_retrigger_fired', () => {
    expect(isMergeFlashEvent('matching_retrigger_fired')).toBe(true);
  });
  it('returns false for pipeline_start', () => {
    expect(isMergeFlashEvent('pipeline_start')).toBe(false);
  });
  it('returns false for crisis_detected', () => {
    expect(isMergeFlashEvent('crisis_detected')).toBe(false);
  });
  it('returns false for tool_call_invoked', () => {
    expect(isMergeFlashEvent('tool_call_invoked')).toBe(false);
  });
});

describe('StructlogSidebar', () => {
  it('Test 2 — merge-flash class applied to matching_trigger_fired row', () => {
    const { container } = render(
      <StructlogSidebar
        events={[makeEnvelope('matching_trigger_fired')]}
      />,
    );
    const flashRow = container.querySelector('.kin-flash-highlight');
    expect(flashRow).not.toBeNull();
    expect(flashRow!.textContent).toContain('matching_trigger_fired');
  });

  it('Test 2b — merge-flash class applied to matching_retrigger_fired row', () => {
    const { container } = render(
      <StructlogSidebar
        events={[makeEnvelope('matching_retrigger_fired')]}
      />,
    );
    expect(container.querySelector('.kin-flash-highlight')).not.toBeNull();
  });

  it('Test 3 — non-merge-flash row does NOT have kin-flash-highlight', () => {
    const { container } = render(
      <StructlogSidebar
        events={[
          makeEnvelope('pipeline_start'),
          makeEnvelope('ingest_audio_start', '2026-05-03T10:00:00.500Z'),
          makeEnvelope('tool_call_invoked', '2026-05-03T10:00:01.200Z'),
        ]}
      />,
    );
    expect(container.querySelector('.kin-flash-highlight')).toBeNull();
  });

  it('Test 4 — kin-flash-highlight class still applied under prefers-reduced-motion', () => {
    /* The CSS fallback (static tint, no animation) is manual-verification
       only; this test confirms the class itself is present regardless of
       motion preference — the component never reads matchMedia. */
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => true,
      }),
    });

    const { container } = render(
      <StructlogSidebar
        events={[makeEnvelope('matching_trigger_fired')]}
      />,
    );
    expect(container.querySelector('.kin-flash-highlight')).not.toBeNull();

    Object.defineProperty(window, 'matchMedia', { writable: true, value: originalMatchMedia });
  });

  it('Test 5 — categorization regression: amber / red / started bands', () => {
    const { container } = render(
      <StructlogSidebar
        events={[
          makeEnvelope('crisis_detected', '2026-05-03T10:00:00.000Z'),
          makeEnvelope('inference_timeout', '2026-05-03T10:00:00.100Z'),
          makeEnvelope('adapter_call_start', '2026-05-03T10:00:00.200Z'),
        ]}
      />,
    );
    // crisis_detected starts with 'crisis_' → amber
    const amberRows = container.querySelectorAll('.border-amber');
    expect(amberRows.length).toBeGreaterThan(0);
    // inference_timeout → red
    const redRows = container.querySelectorAll('.border-red');
    expect(redRows.length).toBeGreaterThan(0);
    // adapter_call_start → primary (started)
    const primaryRows = container.querySelectorAll('.border-primary');
    expect(primaryRows.length).toBeGreaterThan(0);
  });

  it('Test 6 — empty state renders updated copy', () => {
    const { container } = render(<StructlogSidebar events={[]} />);
    expect(container.textContent).toContain(
      'System ready. Pipeline events will appear as the intake runs.',
    );
  });
});
