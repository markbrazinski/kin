/* MinorStrip component tests — S19 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MinorStrip } from './MinorStrip';

describe('MinorStrip', () => {
  it('renders null when visible=false', () => {
    const { container } = render(<MinorStrip visible={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders amber banner with protection text when visible=true', () => {
    render(<MinorStrip visible={true} />);
    expect(
      screen.getByText(/Child protection routing required/i)
    ).toBeTruthy();
  });

  it('shows minor name in sub-line when minorName is provided', () => {
    render(<MinorStrip visible={true} minorName="Mohamad" />);
    expect(screen.getByText('Mohamad')).toBeTruthy();
  });
});
