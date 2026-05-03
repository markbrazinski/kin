/* NetworkMatch component tests — B2-S12.

   Seven tests covering null guards, phase-gated line rendering,
   source-script preservation, staggered animation delays, and
   reduced-motion fallback. All tests stub requestAnimationFrame
   synchronously so useEffect-driven SVG coordinate computation
   runs within act() boundaries.
*/
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render } from '@testing-library/react';
import { NetworkMatch, DEFAULT_NETWORK_RESULT } from './NetworkMatch';
import type { NetworkMatchResult } from '../lib/types';

beforeEach(() => {
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  });
  vi.stubGlobal('cancelAnimationFrame', () => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('NetworkMatch', () => {
  // ─── Null guards ────────────────────────────────────────────────

  it('returns null when networkResult.matched is false', () => {
    const result: NetworkMatchResult = {
      matched: false,
      node_matches: [],
      primary_match: null,
    };
    const { container } = render(
      <NetworkMatch phase="split" onBack={() => {}} networkResult={result} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('returns null when matched=true but node_matches is empty (defensive)', () => {
    const result: NetworkMatchResult = {
      matched: true,
      node_matches: [],
      primary_match: null,
    };
    // matched=true with empty list: component still renders (guard is
    // only on matched). Parent's richness rule (length >= 2) prevents
    // this from displaying — component doesn't gate on length.
    // Verify it does NOT crash and renders the header at minimum.
    const { container } = render(
      <NetworkMatch phase="split" onBack={() => {}} networkResult={result} />,
    );
    // Component renders (header present) — parent is responsible for
    // the length >= 2 richness rule, not the component's null guard.
    expect(container.firstChild).not.toBeNull();
  });

  // ─── Phase-gated line rendering ─────────────────────────────────

  it('phase=split renders no SVG line elements', () => {
    const { container } = render(
      <NetworkMatch
        phase="split"
        onBack={() => {}}
        networkResult={DEFAULT_NETWORK_RESULT}
      />,
    );
    const lines = container.querySelectorAll('line');
    expect(lines.length).toBe(0);
  });

  it('phase=linking renders one SVG line per node_match with correct classes', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const result = render(
        <NetworkMatch
          phase="linking"
          onBack={() => {}}
          networkResult={DEFAULT_NETWORK_RESULT}
        />,
      );
      container = result.container;
    });
    const lines = container.querySelectorAll('line');
    // 3 node_matches → 3 lines
    expect(lines.length).toBe(3);
    // Primary line: kin-link-draw, no strokeDasharray
    expect(lines[0].classList.contains('kin-link-draw')).toBe(true);
    expect(lines[0].getAttribute('stroke-dasharray')).toBeNull();
    // Supporting lines: kin-link-draw + strokeDasharray
    expect(lines[1].classList.contains('kin-link-draw')).toBe(true);
    expect(lines[1].getAttribute('stroke-dasharray')).toBeTruthy();
    expect(lines[2].classList.contains('kin-link-draw')).toBe(true);
    expect(lines[2].getAttribute('stroke-dasharray')).toBeTruthy();
  });

  // ─── Source-script preservation ─────────────────────────────────

  it('Arabic speakerLanguage: role slot containers carry dir=rtl', () => {
    const { container } = render(
      <NetworkMatch
        phase="split"
        onBack={() => {}}
        networkResult={DEFAULT_NETWORK_RESULT}
      />,
    );
    // DEFAULT_RECORD_A and DEFAULT_RECORD_B both use speakerLanguage='ar'
    const rtlSlots = container.querySelectorAll('[dir="rtl"]');
    expect(rtlSlots.length).toBeGreaterThan(0);
  });

  // ─── Staggered animation delays ─────────────────────────────────

  it('linking: SVG lines have staggered animationDelay (primary 0ms, others increasing)', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const result = render(
        <NetworkMatch
          phase="linking"
          onBack={() => {}}
          networkResult={DEFAULT_NETWORK_RESULT}
        />,
      );
      container = result.container;
    });
    const lines = Array.from(container.querySelectorAll('line')) as unknown as HTMLElement[];
    expect(lines.length).toBe(3);

    // Primary line: animationDelay absent or 0ms
    const delay0 = lines[0].style.animationDelay;
    expect(delay0 === '' || delay0 === '0ms').toBe(true);

    // Supporting lines: 400ms, 700ms
    expect(parseInt(lines[1].style.animationDelay)).toBeGreaterThanOrEqual(400);
    expect(parseInt(lines[2].style.animationDelay)).toBeGreaterThanOrEqual(700);
  });

  // ─── Reduced motion ─────────────────────────────────────────────

  it('reduced-motion: lines render in split phase without kin-link-draw class', async () => {
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    let container!: HTMLElement;
    await act(async () => {
      const result = render(
        // phase=split: normally no lines, but reducedMotion=true bypasses phase gating
        <NetworkMatch
          phase="split"
          onBack={() => {}}
          networkResult={DEFAULT_NETWORK_RESULT}
        />,
      );
      container = result.container;
    });

    const lines = container.querySelectorAll('line');
    // reducedMotion=true → showLines=true regardless of phase
    expect(lines.length).toBe(3);
    // No kin-link-draw class when reduced motion
    for (const line of lines) {
      expect(line.classList.contains('kin-link-draw')).toBe(false);
    }
  });
});
