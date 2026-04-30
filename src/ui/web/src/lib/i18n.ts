/* Bundle 1.5 S6 — minimal hand-rolled i18n surface.

   Two responsibilities:
     - dirFor(language) returns 'ltr' | 'rtl', single source of truth
       replacing inline `lang === 'ar' || lang === 'fa'` ternaries.
     - t(key, language) looks up a chrome string in CHROME_STRINGS
       with English fallback if the language entry is missing.

   v1 always passes workerLanguage='en' to t(); the abstraction is
   in place so v1.1 can wire a Settings selector without touching
   call sites. Speaker-language tables (voiceCopy, CRISIS_COPY) keep
   their per-language entries since they drive body-text rendering. */
import type { Language } from './types';

export function dirFor(language: Language): 'ltr' | 'rtl' {
  return language === 'ar' || language === 'fa' ? 'rtl' : 'ltr';
}

/* Chrome strings keyed by lookup key. Entries default to the same
   English string when a worker_language other than 'en' is used —
   v1 has no Settings UI, so non-en variants exist as a placeholder
   for v1.1 translation work. */
export const CHROME_STRINGS: Record<string, Record<Language, string>> = {
  'voice.begin': {
    en: 'Begin',
    es: 'Comenzar',
    ar: 'ابدأ',
    fa: 'شروع',
    fr: 'Commencer',
    uk: 'Почати',
  },
  'voice.stop': {
    en: 'Stop',
    es: 'Detener',
    ar: 'إيقاف',
    fa: 'توقف',
    fr: 'Arrêter',
    uk: 'Зупинити',
  },
  'crisis.dismiss': {
    en: 'Dismiss',
    es: 'Descartar',
    ar: 'إغلاق',
    fa: 'بستن',
    fr: 'Fermer',
    uk: 'Закрити',
  },
  /* Crisis card chrome — dismissal buttons. The strings are the
     "two explicit logged actions, no generic Close" pattern from
     QA-3 lock; routing through t() so v1.1 worker_language toggles
     can localize without code changes. */
  'crisis.title': {
    en: 'Crisis signal detected',
    es: 'Crisis signal detected',
    ar: 'Crisis signal detected',
    fa: 'Crisis signal detected',
    fr: 'Crisis signal detected',
    uk: 'Crisis signal detected',
  },
  'crisis.subtitle': {
    en: 'Primary record paused. Surface this card to the person in front of you.',
    es: 'Primary record paused. Surface this card to the person in front of you.',
    ar: 'Primary record paused. Surface this card to the person in front of you.',
    fa: 'Primary record paused. Surface this card to the person in front of you.',
    fr: 'Primary record paused. Surface this card to the person in front of you.',
    uk: 'Primary record paused. Surface this card to the person in front of you.',
  },
  'crisis.deescalated': {
    en: 'De-escalated — continue intake',
    es: 'De-escalated — continue intake',
    ar: 'De-escalated — continue intake',
    fa: 'De-escalated — continue intake',
    fr: 'De-escalated — continue intake',
    uk: 'De-escalated — continue intake',
  },
  'crisis.referralProvided': {
    en: 'Referral provided',
    es: 'Referral provided',
    ar: 'Referral provided',
    fa: 'Referral provided',
    fr: 'Referral provided',
    uk: 'Referral provided',
  },
};

export function t(key: string, language: Language): string {
  const entry = CHROME_STRINGS[key];
  if (!entry) return key;
  return entry[language] ?? entry.en;
}
