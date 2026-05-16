/* Reducer for the SSE event stream.

   Three slices behind one dispatch:
   - record:            RecordData      driven by field_extracted audit events
   - auditEvents:       AuditEnvelope[] full audit log (ordered)
   - structlogEvents:   StructlogEnvelope[] all structlog events (ordered)

   Plus connection-state machine for the UI status indicator.

   `mapAuditEventToRecord` covers the IntakeRecord → RecordData mapping;
   IntakeRecord field names that have no RecordData slot still flow into
   `auditEvents` for the structlog sidebar (S4) — never silently dropped.
*/
import type {
  AuditEnvelope,
  EventEnvelope,
  StructlogEnvelope,
} from '../lib/sseEnvelope';
import { isAuditEnvelope } from '../lib/sseEnvelope';
import type { FamilyMember, RecordData } from '../lib/types';
import { INITIAL_RECORD } from '../lib/initialState';

export type ConnectionState =
  | 'connecting'
  | 'open'
  | 'closed'
  | 'error';

export type EventStreamState = {
  record: RecordData;
  auditEvents: AuditEnvelope[];
  structlogEvents: StructlogEnvelope[];
  connection: ConnectionState;
  intakeId: string | null;
  capturedAt: string | null;
};

export type EventStreamAction =
  | { type: 'envelope'; envelope: EventEnvelope }
  | { type: 'connection'; value: ConnectionState }
  | { type: 'reset' }
  | { type: 'clear_intake_id' };

export const INITIAL_STATE: EventStreamState = {
  record: INITIAL_RECORD,
  auditEvents: [],
  structlogEvents: [],
  connection: 'connecting',
  intakeId: null,
  capturedAt: null,
};

/* IntakeRecord field name (Pydantic snake_case) → RecordData property
   name. Fields not in this table flow into auditEvents only. */
const FIELD_MAP: Partial<Record<string, keyof RecordData>> = {
  full_name_source_script: 'name',
  full_name_transliteration: 'name',
  relationship_to_seeker: 'relationship',
  age: 'age',
  last_seen_location: 'lastSeenLocationSource',
  last_seen_date: 'lastSeenDate',
  distinguishing_marks: 'physicalDesc',
  separation_circumstance: 'circumstance',
  searcher_name: 'searcherName',
  searcher_name_transliteration: 'searcherNameLatin',
};

/* Array fields: value arrives as a JSON array from the backend and is
   stored as-is (no string coercion). The mapper branch below handles
   these separately from the scalar FIELD_MAP path. */
const ARRAY_FIELD_MAP: Partial<Record<string, keyof RecordData>> = {
  family_roster: 'familyRoster',
  missing_persons: 'missingPersons',
};

/* Apply a single field_extracted audit event to a RecordData. Returns
   the same reference when the field doesn't map or the value is empty. */
export function mapAuditEventToRecord(
  record: RecordData,
  audit: AuditEnvelope,
): RecordData {
  if (audit.payload.event_type !== 'field_extracted') return record;
  const details = audit.payload.details as {
    field_name?: string;
    value?: unknown;
  };
  const fieldName = details.field_name;
  if (!fieldName) return record;

  const rawValue = details.value;
  if (rawValue === null || rawValue === undefined) return record;

  // Array fields: map backend shape → frontend FamilyMember shape.
  const arrayKey = ARRAY_FIELD_MAP[fieldName];
  if (arrayKey) {
    if (!Array.isArray(rawValue)) return record;
    const members: FamilyMember[] = rawValue.map((m: Record<string, unknown>) => {
      const marksRaw = m.distinguishing_marks as string | null | undefined;
      const marks = marksRaw ? [marksRaw] : undefined;
      return {
        name: (m.name as string) ?? '',
        nameLatin: (m.name_transliteration as string | null) ?? undefined,
        age: (m.age as number | null) ?? undefined,
        relationship: (m.relationship_to_searcher as string) ?? '',
        status: m.status === 'present' ? 'WITH_SEARCHER'
              : m.status === 'missing' ? 'MISSING'
              : 'UNKNOWN',
        lastSeen: (m.last_seen_location as string | null) ?? undefined,
        marks,
      };
    });
    return { ...record, [arrayKey]: members };
  }

  const targetKey = FIELD_MAP[fieldName];
  if (!targetKey) return record;

  if (rawValue === '') return record;

  // Scalar fields: coerce numbers to strings for form-layer compatibility.
  const stringValue =
    typeof rawValue === 'string' ? rawValue : String(rawValue);

  if (record[targetKey] === stringValue) return record;
  return { ...record, [targetKey]: stringValue };
}

function applyAuditEvent(
  state: EventStreamState,
  envelope: AuditEnvelope,
): EventStreamState {
  const next: EventStreamState = {
    ...state,
    auditEvents: [...state.auditEvents, envelope],
  };
  const evType = envelope.payload.event_type;
  if (evType === 'intake_created' && envelope.payload.record_ids[0]) {
    next.intakeId = envelope.payload.record_ids[0];
    next.capturedAt = envelope.at;
  }
  if (evType === 'field_extracted') {
    next.record = mapAuditEventToRecord(state.record, envelope);
  }
  return next;
}

export function eventReducer(
  state: EventStreamState,
  action: EventStreamAction,
): EventStreamState {
  switch (action.type) {
    case 'envelope': {
      if (isAuditEnvelope(action.envelope)) {
        return applyAuditEvent(state, action.envelope);
      }
      return {
        ...state,
        structlogEvents: [...state.structlogEvents, action.envelope],
      };
    }
    case 'connection':
      return { ...state, connection: action.value };
    case 'reset':
      return { ...INITIAL_STATE, connection: state.connection };
    case 'clear_intake_id':
      // Gap 3 (ADR-004 REV 3): after a crisis turn the next mic turn
      // must take the create-path (S5 lock #4: extend-into-crisis is
      // ValueError) so we drop the cached intakeId. Done at the
      // reducer because intakeId lives here, not in App state.
      return state.intakeId === null ? state : { ...state, intakeId: null };
  }
}
