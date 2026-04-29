import { describe, it, expect } from 'vitest';
import { formatTimestamp } from './formatters';

describe('formatTimestamp', () => {
  /* Use a fixed Date constructed in the local timezone via individual
     args; numeric components avoid ambiguity that ISO-string parsing
     would introduce across CI environments. */
  const sample = new Date(2026, 3, 28, 14, 32, 0); // April 28 2026, 14:32 local

  it('tent A returns 24-hour format', () => {
    expect(formatTimestamp(sample, 'a')).toBe('14:32');
  });

  it('tent B returns 12-hour format with AM/PM', () => {
    expect(formatTimestamp(sample, 'b')).toBe('2:32 PM');
  });
});
