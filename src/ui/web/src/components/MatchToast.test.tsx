/* Bundle 1.5 S2-fix1 — MatchToast tests.
   - Renders open + fires onOpen on "Open match" click; aria-live present
   - 30s silent auto-dismiss timer fires onDismiss (NOT onOpen)
*/
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MatchToast } from './MatchToast';

describe('MatchToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders when open and fires onOpen on Open match click', () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    render(<MatchToast open={true} onOpen={onOpen} onDismiss={onDismiss} />);

    // Live region present (a11y)
    const live = screen.getByRole('status');
    expect(live.getAttribute('aria-live')).toBe('polite');

    // Both buttons present
    expect(screen.getByRole('button', { name: 'Open match' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Dismiss' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Open match' }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it('30s silent auto-dismiss fires onDismiss (not onOpen)', () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    render(<MatchToast open={true} onOpen={onOpen} onDismiss={onDismiss} />);

    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(29_999);
    });
    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(2);
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onOpen).not.toHaveBeenCalled();
  });
});
