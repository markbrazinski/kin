/* NetworkMatch component tests — B2-S25 (V3 inline SVG graph).

   Tests cover: null guards, phase-gated edge rendering, source-script
   preservation, staggered animation delays on paths, reduced-motion
   fallback, score pill presence, roster sub-divider, and primary node
   fill on merged phase.
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

// ─── Null guards ──────────────────────────────────────────────────────

describe('NetworkMatch', () => {
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

  it('renders header when matched=true with empty node_matches', () => {
    const result: NetworkMatchResult = {
      matched: true,
      node_matches: [],
      primary_match: null,
    };
    const { container } = render(
      <NetworkMatch phase="split" onBack={() => {}} networkResult={result} />,
    );
    expect(container.firstChild).not.toBeNull();
  });

  // ─── Phase-gated edge rendering ────────────────────────────────────

  it('phase=split renders no edge paths', () => {
    const { container } = render(
      <NetworkMatch
        phase="split"
        onBack={() => {}}
        networkResult={DEFAULT_NETWORK_RESULT}
      />,
    );
    const paths = container.querySelectorAll('[data-testid^="edge-path-"]');
    expect(paths.length).toBe(0);
  });

  it('phase=linking renders one path per node_match', async () => {
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
    const paths = container.querySelectorAll('[data-testid^="edge-path-"]');
    expect(paths.length).toBe(3);
  });

  it('phase=linking: primary path has strokeWidth 3, supporting paths have strokeWidth 1', async () => {
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
    const paths = Array.from(
      container.querySelectorAll('[data-testid^="edge-path-"]'),
    ) as SVGPathElement[];
    expect(paths.length).toBeGreaterThanOrEqual(1);
    // Primary edge (edge_0) is the first match which matches primary_match.
    const primaryPath = container.querySelector('[data-testid="edge-path-edge_0"]');
    expect(primaryPath?.getAttribute('stroke-width')).toBe('3');
    // Any supporting edge should have strokeWidth 1.
    const supportingPath = container.querySelector('[data-testid="edge-path-edge_1"]');
    if (supportingPath) {
      expect(supportingPath.getAttribute('stroke-width')).toBe('1');
    }
  });

  // ─── Staggered animation delays ─────────────────────────────────────

  it('linking: primary path has animationDelay 0ms, supporting paths staggered', async () => {
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
    const primary = container.querySelector('[data-testid="edge-path-edge_0"]') as HTMLElement | null;
    const supporting = container.querySelector('[data-testid="edge-path-edge_1"]') as HTMLElement | null;

    const primaryDelay = primary?.style.animationDelay ?? '';
    expect(primaryDelay === '' || primaryDelay === '0ms').toBe(true);

    if (supporting) {
      const delay = parseInt(supporting.style.animationDelay ?? '0');
      expect(delay).toBeGreaterThan(0);
    }
  });

  // ─── Source-script preservation ──────────────────────────────────────

  it('Arabic nodes include direction=rtl on name text elements', () => {
    const { container } = render(
      <NetworkMatch
        phase="split"
        onBack={() => {}}
        networkResult={DEFAULT_NETWORK_RESULT}
      />,
    );
    // SVG text elements with direction="rtl" for Arabic names.
    const rtlTexts = container.querySelectorAll('text[direction="rtl"]');
    expect(rtlTexts.length).toBeGreaterThan(0);
  });

  // ─── Score pill ───────────────────────────────────────────────────────

  it('score pill renders on primary edge during linking phase', async () => {
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
    const pills = container.querySelectorAll('[data-testid="score-pill"]');
    // Exactly one pill — on the primary edge only.
    expect(pills.length).toBe(1);
  });

  it('score pill does not render in split phase', () => {
    const { container } = render(
      <NetworkMatch
        phase="split"
        onBack={() => {}}
        networkResult={DEFAULT_NETWORK_RESULT}
      />,
    );
    const pills = container.querySelectorAll('[data-testid="score-pill"]');
    expect(pills.length).toBe(0);
  });

  // ─── Roster sub-divider ───────────────────────────────────────────────

  it('roster members render as flat nodes without a section separator', () => {
    const { container } = render(
      <NetworkMatch
        phase="split"
        onBack={() => {}}
        networkResult={DEFAULT_NETWORK_RESULT}
      />,
    );
    // No "ALSO IN ROSTER" divider — flat list.
    const svgTexts = Array.from(container.querySelectorAll('text'));
    const rosterLabel = svgTexts.find(t => t.textContent?.includes('ALSO IN ROSTER'));
    expect(rosterLabel).toBeUndefined();
    // Roster nodes still render (Aisha on side A).
    expect(container.querySelector('[data-testid="node-a:roster_1"]')).toBeTruthy();
  });

  // ─── Merged phase — primary node fill ────────────────────────────────

  it('missing_person nodes have green-soft fill regardless of phase', () => {
    const { container } = render(
      <NetworkMatch
        phase="split"
        onBack={() => {}}
        networkResult={DEFAULT_NETWORK_RESULT}
      />,
    );
    // person_type=missing_person nodes always get green-soft fill.
    const missingRects = container.querySelectorAll('[data-testid="missing-node-rect"]');
    expect(missingRects.length).toBeGreaterThan(0);
    for (const rect of missingRects) {
      expect(rect.getAttribute('fill')).toBe('oklch(0.96 0.03 155)');
    }
  });

  // ─── Reduced motion ───────────────────────────────────────────────────

  it('reduced-motion: edges render in split phase without kin-edge-draw class', async () => {
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
        <NetworkMatch
          phase="split"
          onBack={() => {}}
          networkResult={DEFAULT_NETWORK_RESULT}
        />,
      );
      container = result.container;
    });

    // reducedMotion=true → showEdges=true regardless of phase.
    const paths = container.querySelectorAll('[data-testid^="edge-path-"]');
    expect(paths.length).toBe(3);
    // No kin-edge-draw class when reduced motion.
    for (const path of paths) {
      expect(path.classList.contains('kin-edge-draw')).toBe(false);
    }
  });
});
