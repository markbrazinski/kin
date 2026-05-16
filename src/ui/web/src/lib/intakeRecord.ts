/* Frontend mirror of the Python IntakeRecord Pydantic model.
   Field names and types match the JSON serialization from GET /intake/records.
   UUIDs are serialized as strings; datetimes as ISO 8601 strings. */

import type { FamilyMember as UiFamilyMember, RecordData } from './types';
import { INITIAL_RECORD } from './initialState';

export type IntakeStatus = 'complete' | 'partial';

export type StoredFamilyMember = {
  name: string;
  name_transliteration: string | null;
  relationship_to_searcher: string;
  status: 'missing' | 'known' | 'present';
  age: number | null;
  last_seen_location: string | null;
  distinguishing_marks: string | null;
  distinguishing_marks_transliteration: string | null;
};

export type IntakeRecord = {
  id: string;
  created_at: string;
  updated_at: string;
  status: IntakeStatus;
  language: string;
  source_device_id: string;
  full_name_source_script: string;
  full_name_transliteration: string;
  relationship_to_seeker: string;
  age: number | null;
  last_seen_location: string | null;
  last_seen_location_transliteration: string | null;
  last_seen_date: string | null;
  distinguishing_marks: string | null;
  is_minor: boolean;
  is_crisis: boolean;
  referral_issued: boolean;
  referral_organization: string | null;
  family_roster: StoredFamilyMember[];
  searcher_name: string;
  searcher_name_transliteration: string;
  searcher_relationship_to_target: string;
  separation_circumstance: string | null;
};

/**
 * Map a stored IntakeRecord (the GET /intake/records shape) into the
 * RecordData shape the App's UI components expect. Used by App.tsx
 * to populate Side A of the NetworkMatch view from a counterparty
 * record fetched out of queueRecords, when the active intake's
 * `record` state is Side B.
 */
export function intakeRecordToRecordData(stored: IntakeRecord): RecordData {
  const familyRoster: UiFamilyMember[] = (stored.family_roster ?? []).map(m => {
    const marksRaw = m.distinguishing_marks;
    const marksTranslit = m.distinguishing_marks_transliteration;
    const marks = marksRaw
      ? (marksTranslit ? [marksRaw, marksTranslit] : [marksRaw])
      : undefined;
    const status: UiFamilyMember['status'] =
      m.status === 'present' ? 'WITH_SEARCHER'
      : m.status === 'missing' ? 'MISSING'
      : 'UNKNOWN';
    return {
      name: m.name,
      nameLatin: m.name_transliteration ?? undefined,
      age: m.age ?? undefined,
      relationship: m.relationship_to_searcher,
      status,
      lastSeen: m.last_seen_location ?? undefined,
      marks,
    };
  });
  return {
    ...INITIAL_RECORD,
    name: stored.full_name_source_script || stored.full_name_transliteration || '',
    relationship: stored.relationship_to_seeker,
    age: stored.age != null ? String(stored.age) : '',
    language: stored.language,
    lastSeenLocation: stored.last_seen_location_transliteration ?? '',
    lastSeenLocationSource: stored.last_seen_location ?? '',
    lastSeenDate: stored.last_seen_date ?? '',
    physicalDesc: stored.distinguishing_marks ?? '',
    circumstance: stored.separation_circumstance ?? '',
    searcherName: stored.searcher_name ?? '',
    searcherNameLatin: stored.searcher_name_transliteration ?? '',
    familyRoster,
    recordId: stored.id,
    capturedAt: stored.created_at,
    syncStatus: 'queued',
  };
}
