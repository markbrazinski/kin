import { describe, it, expect } from 'vitest';
import { containsNonLatinScript } from './script';

describe('containsNonLatinScript', () => {
  it('returns true for Arabic / Persian / Cyrillic strings', () => {
    expect(containsNonLatinScript('محمد')).toBe(true); // Arabic
    expect(containsNonLatinScript('محمّد رضا')).toBe(true); // Persian-flavored Arabic
    expect(containsNonLatinScript('Москва')).toBe(true); // Cyrillic
  });

  it('returns false for Latin-only strings', () => {
    expect(containsNonLatinScript('Carlos')).toBe(false);
    expect(containsNonLatinScript('María Elena Torres')).toBe(false);
    expect(containsNonLatinScript('José François')).toBe(false);
  });
});
