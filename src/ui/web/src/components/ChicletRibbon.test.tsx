/* ChicletRibbon component tests — S19 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChicletRibbon } from './ChicletRibbon';

describe('ChicletRibbon', () => {
  it('renders two chiclet containers', () => {
    const { container } = render(
      <ChicletRibbon searcherName="" missingPersonsCount={0} />
    );
    // The grid has 2 direct children (one per chiclet)
    const grid = container.firstChild as HTMLElement;
    expect(grid.children).toHaveLength(2);
  });

  it('Searcher dot has bg-primary class when searcherName is non-empty', () => {
    const { container } = render(
      <ChicletRibbon searcherName="Yusuf" missingPersonsCount={0} />
    );
    // First chiclet contains the primary dot
    const primaryDot = container.querySelector('.bg-primary');
    expect(primaryDot).not.toBeNull();
  });

  it('Missing persons sub-count reflects the person count', () => {
    render(
      <ChicletRibbon searcherName="" missingPersonsCount={2} detailedCount={2} />
    );
    // Should show "2 of 2 detailed"
    expect(screen.getByText('2 of 2 detailed')).toBeTruthy();
  });
});
