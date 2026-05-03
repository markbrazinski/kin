/* UI-layer shared types. NOT a mirror of src/core/ Pydantic schemas
   — those live in Python and arrive over SSE. These are the React
   side's view of the same data. When Core lands, an adapter at the
   integration boundary maps Python → these types. */
import type { ReactNode } from 'react';

// ----- Locale + state unions -----

/* Aligned with Python core.language_matrix.SupportedLang.
   Bundle 1.5 S6 extended from 4-tuple (en/es/ar/fa) to 6-tuple to
   match the speaker_language selector and close polish item #18.
   Backend has FLEURS-validated coverage for fr/uk; demo continues
   featuring en/es/ar/fa (CLAUDE.md §"Confirmed demo languages"). */
export type Language = 'en' | 'es' | 'ar' | 'fa' | 'fr' | 'uk';

export type MatchPhase = 'split' | 'linking' | 'merged';

// ----- Trace shapes -----

export type TraceCall = {
  id: number;
  t: number;
  name: string;
  args?: Record<string, unknown>;
  result?: unknown;
  highlight?: boolean;
};

// ----- Record (RFL) shapes -----

export type NameVariant = {
  latin: string;
  script?: string;
  rtl?: boolean;
};

export type GuardianData = {
  guardianPresent?: string;
  cpConsent?: string;
  cmKnown?: string;
  referralStatus?: string;
};

export type RecordData = {
  name: string;
  nameVariants: NameVariant[] | null;
  nameNative: string | null;
  nameNativeRtl: boolean;
  age: string;
  relationship: string;
  language: string;
  lastSeenLocation: string;
  lastSeenLocationSource: string;
  lastSeenLocationRtl: boolean;
  lastSeenDate: string;
  circumstance: string;
  physicalDesc: string;
  features: string;
  guardian: GuardianData;
};

// ----- UI summary shapes -----

export type CompletenessSegment = {
  key: string;
  label: ReactNode;
  filled: boolean;
};

// ----- Network match shapes (S12, mirrors src/core/matching.py) -----

export type NodeMatch = {
  role_a: 'searcher' | 'missing_person' | 'roster_member';
  role_b: 'searcher' | 'missing_person' | 'roster_member';
  name_a: string;
  name_b: string;
  roster_index_a: number | null;
  roster_index_b: number | null;
  phonetic_score: number;
  composite_score: number;
};

export type NetworkMatchResult = {
  matched: boolean;
  node_matches: NodeMatch[];
  primary_match: NodeMatch | null;
};
