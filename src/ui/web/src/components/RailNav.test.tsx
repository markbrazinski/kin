/* Bundle 1.5 S1 — RailNav tests.
   - 2 icons render with correct aria-labels (bimodal capture/review,
     per design ref nav-rail.jsx)
   - active state applies aria-current="page" to current route only
   - ArrowUp/ArrowDown cycle focus across rail buttons (with wrap)
   - click fires setRoute with the corresponding key
   Bundle 1.5 S5:
   - badge hidden when count=0
   - kin-badge-tick applied on count INCREASE; cleared after the
     150ms animation; NOT applied on decrease */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent, screen, act } from '@testing-library/react';
import { RailNav } from './RailNav';

describe('RailNav', () => {
  it('renders 2 buttons with Intake and Queue aria-labels', () => {
    render(<RailNav route="intake" setRoute={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(2);
    expect(screen.getByLabelText('Intake')).toBeTruthy();
    expect(screen.getByLabelText('Queue')).toBeTruthy();
  });

  it('applies aria-current="page" to the active route only', () => {
    render(<RailNav route="queue" setRoute={() => {}} />);
    const intake = screen.getByLabelText('Intake');
    const queue = screen.getByLabelText('Queue');
    expect(queue.getAttribute('aria-current')).toBe('page');
    expect(intake.getAttribute('aria-current')).toBeNull();
  });

  it('ArrowDown moves focus to next button, ArrowUp wraps from first to last', () => {
    render(<RailNav route="intake" setRoute={() => {}} />);
    const intake = screen.getByLabelText('Intake') as HTMLButtonElement;
    const queue = screen.getByLabelText('Queue') as HTMLButtonElement;

    intake.focus();
    expect(document.activeElement).toBe(intake);

    fireEvent.keyDown(intake, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(queue);

    fireEvent.keyDown(queue, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(intake); // wraps forward

    fireEvent.keyDown(intake, { key: 'ArrowUp' });
    expect(document.activeElement).toBe(queue); // wraps backward
  });

  it('click fires setRoute with the corresponding key', () => {
    const setRoute = vi.fn();
    render(<RailNav route="intake" setRoute={setRoute} />);
    fireEvent.click(screen.getByLabelText('Queue'));
    expect(setRoute).toHaveBeenCalledWith('queue');
    fireEvent.click(screen.getByLabelText('Intake'));
    expect(setRoute).toHaveBeenCalledWith('intake');
  });

  it('Bundle 1.5 S5: badge hidden when queuedCount=0 (regression check)', () => {
    /* Existing badge implementation from Bundle 1 S1: {it.badge ?
       <span/> : null} renders nothing when badge is 0/undefined.
       This guards the existing falsy-check behavior. */
    render(<RailNav route="intake" setRoute={() => {}} queuedCount={0} />);
    const queueBtn = screen.getByLabelText('Queue');
    expect(queueBtn.querySelector('span.bg-primary.text-white')).toBeNull();
  });

  it('Bundle 1.5 S5: kin-badge-tick applied on count INCREASE; NOT on decrease', () => {
    /* Initial render with queuedCount=0 → no badge, no animation
       class. Rerender with queuedCount=2 → badge present with
       kin-badge-tick class (count increased from 0 to 2). After
       the 150ms animation completes, the class clears. Rerender
       with queuedCount=1 → badge present WITHOUT kin-badge-tick
       (count decreased; decrement should not pull worker
       attention). */
    vi.useFakeTimers();
    try {
      const { rerender } = render(
        <RailNav route="intake" setRoute={() => {}} queuedCount={0} />,
      );

      // Increase: 0 → 2.
      rerender(<RailNav route="intake" setRoute={() => {}} queuedCount={2} />);
      let badge = screen.getByLabelText('Queue').querySelector('span.bg-primary.text-white');
      expect(badge).not.toBeNull();
      expect(badge?.className).toContain('kin-badge-tick');

      // Animation duration elapses; class clears.
      act(() => {
        vi.advanceTimersByTime(250);
      });
      badge = screen.getByLabelText('Queue').querySelector('span.bg-primary.text-white');
      expect(badge?.className).not.toContain('kin-badge-tick');

      // Decrease: 2 → 1. Badge present, animation class NOT applied.
      rerender(<RailNav route="intake" setRoute={() => {}} queuedCount={1} />);
      badge = screen.getByLabelText('Queue').querySelector('span.bg-primary.text-white');
      expect(badge).not.toBeNull();
      expect(badge?.className).not.toContain('kin-badge-tick');
    } finally {
      vi.useRealTimers();
    }
  });
});
