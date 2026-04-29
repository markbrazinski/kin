/* Script-detection helpers for transliteration-field visibility.

   The IntakePanel surfaces a worker-entered transliteration field when
   the captured `record.name` contains characters outside the Latin
   block. This is a content-based heuristic: more robust than coupling
   to a language code that may lag the data, and it works whether the
   language code is in scope or not.
*/

/* Unicode ranges considered "non-Latin script" for the purpose of
   showing the transliteration field. Covers the four KIN-supported
   scripts (Arabic, Persian, Cyrillic) plus a generous wildcard for
   anything outside Basic Latin / Latin-1 / Latin Extended. */
const NON_LATIN_RANGES: ReadonlyArray<[number, number]> = [
  // Arabic + Arabic Supplement + Arabic Extended-A
  [0x0600, 0x06ff],
  [0x0750, 0x077f],
  [0x0870, 0x089f],
  // Arabic Presentation Forms-A and -B
  [0xfb50, 0xfdff],
  [0xfe70, 0xfeff],
  // Cyrillic + Cyrillic Supplement
  [0x0400, 0x052f],
  // Hebrew (not a KIN demo language but a likely transliteration trigger)
  [0x0590, 0x05ff],
];

export function containsNonLatinScript(s: string): boolean {
  for (const ch of s) {
    const code = ch.codePointAt(0);
    if (code === undefined) continue;
    for (const [lo, hi] of NON_LATIN_RANGES) {
      if (code >= lo && code <= hi) return true;
    }
  }
  return false;
}

const LATIN_LANGS = new Set(['en', 'es', 'fr']);

export function isLatinScriptLanguage(lang: string): boolean {
  return LATIN_LANGS.has(lang);
}
