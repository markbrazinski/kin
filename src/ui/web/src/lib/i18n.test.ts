/* Bundle 1.5 S6 — i18n helper tests. */
import { describe, it, expect } from 'vitest';
import { dirFor, t } from './i18n';

describe('dirFor', () => {
  it('maps all 6 languages correctly', () => {
    expect(dirFor('en')).toBe('ltr');
    expect(dirFor('es')).toBe('ltr');
    expect(dirFor('fr')).toBe('ltr');
    expect(dirFor('uk')).toBe('ltr');
    expect(dirFor('ar')).toBe('rtl');
    expect(dirFor('fa')).toBe('rtl');
  });
});

describe('t', () => {
  it('returns English for en', () => {
    expect(t('voice.begin', 'en')).toBe('Begin');
  });

  it('returns Spanish for es', () => {
    expect(t('voice.begin', 'es')).toBe('Comenzar');
  });

  it('returns key when chrome string is unknown', () => {
    expect(t('nonexistent.key', 'en')).toBe('nonexistent.key');
  });
});
