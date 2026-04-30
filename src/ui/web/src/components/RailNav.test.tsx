/* Bundle 1.5 S1 — RailNav tests.
   - 2 icons render with correct aria-labels (bimodal capture/review,
     per design ref nav-rail.jsx)
   - active state applies aria-current="page" to current route only
   - ArrowUp/ArrowDown cycle focus across rail buttons (with wrap)
   - click fires setRoute with the corresponding key */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent, screen } from '@testing-library/react';
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
});
