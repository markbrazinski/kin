/* Wire types for the SSE stream from src/ui/server/sse.py.

   The Python EventEnvelope has shape:
     {type: "audit_event" | "structlog_event",
      at: ISO8601 string,
      source_device_id: string | null,
      payload: dict}

   For audit_event, payload mirrors the Python AuditEvent model:
     {id, at, event_type, record_ids, match_id, actor, details}

   For structlog_event, payload is the structlog event_dict:
     {event: string, level: string, timestamp: string, ...extras}.
*/

export type AuditEventType =
  | 'intake_created'
  | 'crisis_detected'
  | 'referral_issued'
  | 'crisis_resolved'
  | 'match_proposed'
  | 'match_confirmed'
  | 'match_rejected'
  | 'field_extracted';

export type AuditEventPayload = {
  id: string;
  at: string;
  event_type: AuditEventType;
  record_ids: string[];
  match_id: string | null;
  actor: string;
  details: Record<string, unknown>;
  /* Bundle 1.5 S5: total candidates from the matching trigger run.
     0 for empty-result match_proposed events (where record_ids has
     a single new-record id) and other event types; otherwise the
     count of matches created in the run. Optional in TS to stay
     backward-compatible with pre-S5 JSONL records (Python schema
     defaults to 0). */
  candidate_count?: number;
};

export type StructlogEventPayload = {
  event: string;
  level?: string;
  timestamp?: string;
  [key: string]: unknown;
};

export type AuditEnvelope = {
  type: 'audit_event';
  at: string;
  source_device_id: string | null;
  payload: AuditEventPayload;
};

export type StructlogEnvelope = {
  type: 'structlog_event';
  at: string;
  source_device_id: string | null;
  payload: StructlogEventPayload;
};

export type EventEnvelope = AuditEnvelope | StructlogEnvelope;

export function isAuditEnvelope(env: EventEnvelope): env is AuditEnvelope {
  return env.type === 'audit_event';
}

export function isStructlogEnvelope(
  env: EventEnvelope,
): env is StructlogEnvelope {
  return env.type === 'structlog_event';
}
