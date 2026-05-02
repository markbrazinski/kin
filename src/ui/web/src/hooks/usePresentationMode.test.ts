/* usePresentationMode hook tests — B1.5-S7, Test 5. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePresentationMode } from './usePresentationMode';

beforeEach(() => {
  vi.stubGlobal('localStorage', {
    setItem: vi.fn(),
    getItem: vi.fn(),
    removeItem: vi.fn(),
  });
  // Default: no ?present param
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { search: '' },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function fireKey(key: string, extra: Partial<KeyboardEvent> = {}) {
  const isMac = /Mac/.test(navigator.platform);
  window.dispatchEvent(
    new KeyboardEvent('keydown', {
      key,
      metaKey: isMac ? true : false,
      ctrlKey: !isMac ? true : false,
      shiftKey: true,
      bubbles: true,
      ...extra,
    }),
  );
}

describe('usePresentationMode', () => {
  it('Test 5 — ⌘⇧P activates presentationActive; re-press deactivates', () => {
    const { result } = renderHook(() => usePresentationMode([]));

    expect(result.current.presentationActive).toBe(false);

    act(() => { fireKey('p'); });
    expect(result.current.presentationActive).toBe(true);

    act(() => { fireKey('p'); });
    expect(result.current.presentationActive).toBe(false);
  });

  it('?present=1 URL param initializes presentationActive=true', () => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { search: '?present=1' },
    });
    const { result } = renderHook(() => usePresentationMode([]));
    expect(result.current.presentationActive).toBe(true);
  });

  it('setPresentationActive(false) deactivates', () => {
    const { result } = renderHook(() => usePresentationMode([]));
    act(() => { result.current.setPresentationActive(true); });
    expect(result.current.presentationActive).toBe(true);
    act(() => { result.current.setPresentationActive(false); });
    expect(result.current.presentationActive).toBe(false);
  });

  it('console.warn fires when expected record id missing on activation', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { result } = renderHook(() => usePresentationMode([])); // empty queue
    act(() => { result.current.setPresentationActive(true); });
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('record id=89 not found'));
    warnSpy.mockRestore();
  });
});
