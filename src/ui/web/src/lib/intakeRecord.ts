/* Frontend mirror of the Python IntakeRecord Pydantic model.
   Field names and types match the JSON serialization from GET /intake/records.
   UUIDs are serialized as strings; datetimes as ISO 8601 strings. */

export type IntakeStatus = 'complete' | 'partial' | 'paused_for_crisis';

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
  last_seen_date: string | null;
  distinguishing_marks: string | null;
  is_minor: boolean;
  is_crisis: boolean;
  referral_issued: boolean;
  referral_organization: string | null;
};
