/* Pure reducer tests — no React, no DOM. */
import { describe, it, expect } from 'vitest';
import {
  eventReducer,
  INITIAL_STATE,
  type EventStreamState,
} from './eventReducer';
import type {
  AuditEnvelope,
  StructlogEnvelope,
} from '../lib/sseEnvelope';

function makeAuditEnvelope(opts: {
  event_type: AuditEnvelope['payload']['event_type'];
  details?: Record<string, unknown>;
  record_ids?: string[];
  source_device_id?: string;
}): AuditEnvelope {
  return {
    type: 'audit_event',
    at: '2026-04-28T12:00:00Z',
    source_device_id: opts.source_device_id ?? 'tent_a',
    payload: {
      id: '00000000-0000-0000-0000-000000000001',
      at: '2026-04-28T12:00:00Z',
      event_type: opts.event_type,
      record_ids: opts.record_ids ?? [
        '00000000-0000-0000-0000-000000000099',
      ],
      match_id: null,
      actor: 'kin_system',
      details: opts.details ?? {},
    },
  };
}

function makeStructlogEnvelope(event: string, extras: Record<string, unknown> = {}): StructlogEnvelope {
  return {
    type: 'structlog_event',
    at: '2026-04-28T12:00:00Z',
    source_device_id: 'tent_a',
    payload: {
      event,
      level: 'info',
      timestamp: '2026-04-28T12:00:00Z',
      ...extras,
    },
  };
}

describe('eventReducer', () => {
  it('audit_event field_extracted updates RecordData via field map', () => {
    const env = makeAuditEnvelope({
      event_type: 'field_extracted',
      details: {
        field_name: 'full_name_source_script',
        value: 'Carlos Alberto',
      },
    });
    const next = eventReducer(INITIAL_STATE, {
      type: 'envelope',
      envelope: env,
    });
    expect(next.record.name).toBe('Carlos Alberto');
    expect(next.auditEvents).toHaveLength(1);
  });

  it('structlog_event appends to structlogEvents slice in arrival order', () => {
    const a = makeStructlogEnvelope('first_event', { n: 1 });
    const b = makeStructlogEnvelope('second_event', { n: 2 });
    const s1 = eventReducer(INITIAL_STATE, { type: 'envelope', envelope: a });
    const s2 = eventReducer(s1, { type: 'envelope', envelope: b });
    expect(s2.structlogEvents.map((e) => e.payload.event)).toEqual([
      'first_event',
      'second_event',
    ]);
    /* Audit slice untouched. */
    expect(s2.auditEvents).toHaveLength(0);
  });

  it('last_seen_location maps to lastSeenLocationSource, not lastSeenLocation (Gap 2)', () => {
    /* Regression guard: the old FIELD_MAP entry mapped last_seen_location →
       'lastSeenLocation'. After the Gap 2 fix it maps to
       'lastSeenLocationSource' so the bilingual location display activates
       when Gemma preserves Arabic/Farsi/Spanish text in that field. */
    const env = makeAuditEnvelope({
      event_type: 'field_extracted',
      details: { field_name: 'last_seen_location', value: 'البوابة الجنوبية' },
    });
    const next = eventReducer(INITIAL_STATE, { type: 'envelope', envelope: env });
    expect(next.record.lastSeenLocationSource).toBe('البوابة الجنوبية');
    // lastSeenLocation must stay empty — the bilingual component renders
    // lastSeenLocationSource as primary text and lastSeenLocation as the
    // Latin transliteration. Setting both to the same Arabic string would
    // render the Arabic twice.
    expect(next.record.lastSeenLocation).toBe('');
  });

  it('separation_circumstance maps to circumstance (Gap 1)', () => {
    const env = makeAuditEnvelope({
      event_type: 'field_extracted',
      details: {
        field_name: 'separation_circumstance',
        value: 'Separated during crowd surge at the southern gate checkpoint',
      },
    });
    const next = eventReducer(INITIAL_STATE, { type: 'envelope', envelope: env });
    expect(next.record.circumstance).toBe(
      'Separated during crowd surge at the southern gate checkpoint',
    );
    // Unrelated location fields must be unaffected.
    expect(next.record.lastSeenLocation).toBe('');
    expect(next.record.lastSeenLocationSource).toBe('');
  });

  it('crisis-reorder: field_extracted events populate record before crisis audit events', () => {
    /* Regression guard for the crisis-reorder fix: the SSE event order
       after the fix is field_extracted* → crisis_detected → referral_issued.
       Crisis events must NOT clear the record fields set by extraction. */
    const familyRosterValue = [
      { name: 'مريم', name_transliteration: 'Mariam', relationship_to_searcher: 'أخت',
        status: 'missing', age: 32, last_seen_location: 'البوابة الجنوبية' },
    ];
    const events = [
      makeAuditEnvelope({ event_type: 'field_extracted',
        details: { field_name: 'searcher_name', value: 'يوسف العمر' } }),
      makeAuditEnvelope({ event_type: 'field_extracted',
        details: { field_name: 'family_roster', value: familyRosterValue } }),
      makeAuditEnvelope({ event_type: 'field_extracted',
        details: { field_name: 'last_seen_location', value: 'البوابة الجنوبية' } }),
      makeAuditEnvelope({ event_type: 'crisis_detected', details: {} }),
      makeAuditEnvelope({ event_type: 'referral_issued', details: {} }),
    ];

    let state: EventStreamState = INITIAL_STATE;
    for (const env of events) {
      state = eventReducer(state, { type: 'envelope', envelope: env });
    }

    // All extraction fields populated.
    expect(state.record.searcherName).toBe('يوسف العمر');
    expect(state.record.familyRoster).toHaveLength(1);
    expect(state.record.familyRoster[0].name).toBe('مريم');
    expect(state.record.lastSeenLocationSource).toBe('البوابة الجنوبية');
    // All 5 events in auditEvents (crisis events don't drop or reset record).
    expect(state.auditEvents).toHaveLength(5);
    expect(state.auditEvents[3].payload.event_type).toBe('crisis_detected');
    expect(state.auditEvents[4].payload.event_type).toBe('referral_issued');
  });

  it('progressive field_extracted events on the same record accumulate without resetting', () => {
    /* Forward constraint from S5: extend path must not drop earlier
       fields when later turns add new ones. */
    const turn1 = makeAuditEnvelope({
      event_type: 'field_extracted',
      details: { field_name: 'full_name_source_script', value: 'Carlos' },
    });
    const turn2 = makeAuditEnvelope({
      event_type: 'field_extracted',
      details: { field_name: 'relationship_to_seeker', value: 'son' },
    });
    const turn3 = makeAuditEnvelope({
      event_type: 'field_extracted',
      details: { field_name: 'age', value: 8 },
    });

    let state: EventStreamState = INITIAL_STATE;
    for (const env of [turn1, turn2, turn3]) {
      state = eventReducer(state, { type: 'envelope', envelope: env });
    }

    expect(state.record.name).toBe('Carlos');
    expect(state.record.relationship).toBe('son');
    expect(state.record.age).toBe('8');
    expect(state.auditEvents).toHaveLength(3);

    /* S4-fix regression: a later field_extracted re-write of the
       same field must replace the earlier value (last-writer-wins).
       The pre-S4-fix guard returned the same record reference and
       silently dropped the new value. */
    const refine = makeAuditEnvelope({
      event_type: 'field_extracted',
      details: { field_name: 'full_name_source_script', value: 'Carlos Alberto' },
    });
    state = eventReducer(state, { type: 'envelope', envelope: refine });
    expect(state.record.name).toBe('Carlos Alberto');
  });

});
