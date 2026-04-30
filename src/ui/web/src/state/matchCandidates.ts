/* Bundle 1.5 S5 — frontend match-candidates session state.

   The queue rail badge derives its value from getActiveMatchCount.
   This module owns the pure-function helpers; App.tsx wires them
   to a useState slot and dispatches on SSE arrival. No useReducer
   per Mark's locked answer (App.tsx is uniformly useState).

   ORDERING CONVENTION (mirror of transcription_pipeline.py:710-715):
   match_proposed audit events have record_ids[0] = the new record
   being matched, record_ids[1:] = matched counterparties. For
   empty-result runs (Bundle 1.5 S5 always-emit), record_ids has a
   single id (the new record) and candidate_count is 0.

   Latest-wins per intake_id: a 3-turn intake produces multiple
   match_proposed events (one per turn); applyMatchProposed replaces
   the entry each time. getActiveMatchCount thus reports 1 active
   intake, not 3.

   Confirm/reject decrement: Item 11 cosmetic ships separately and
   consumes applyMatchConfirmed / applyMatchRejected. They behave
   identically for badge purposes — both filter the counterparty
   from record_ids and decrement candidate_count. Entries with
   count=0 stay in the map for audit history; getActiveMatchCount
   filters them out.
*/

export type MatchCandidateState = {
  candidate_count: number;
  record_ids: string[];
  last_updated: string;  // ISO timestamp
};

export type MatchCandidatesMap = Record<string, MatchCandidateState>;

export const INITIAL_MATCH_CANDIDATES: MatchCandidatesMap = {};

/**
 * Apply a match_proposed event to the candidates map.
 * Latest-wins per intake_id: replaces any existing entry.
 *
 * @param state current map
 * @param intakeId record_ids[0] from the audit event
 * @param candidateCount candidate_count from the audit event
 * @param recordIds full record_ids array (incl. intakeId at [0])
 * @param at ISO timestamp
 */
export function applyMatchProposed(
  state: MatchCandidatesMap,
  intakeId: string,
  candidateCount: number,
  recordIds: string[],
  at: string,
): MatchCandidatesMap {
  return {
    ...state,
    [intakeId]: {
      candidate_count: candidateCount,
      record_ids: recordIds,
      last_updated: at,
    },
  };
}

/**
 * Apply a match_confirmed action — removes counterparty from
 * record_ids and decrements candidate_count (floor 0). Entry stays
 * in the map even at count=0 for audit history.
 */
export function applyMatchConfirmed(
  state: MatchCandidatesMap,
  intakeId: string,
  counterpartyId: string,
): MatchCandidatesMap {
  const entry = state[intakeId];
  if (!entry) return state;
  return {
    ...state,
    [intakeId]: {
      candidate_count: Math.max(0, entry.candidate_count - 1),
      record_ids: entry.record_ids.filter((id) => id !== counterpartyId),
      last_updated: entry.last_updated,
    },
  };
}

/**
 * Apply a match_rejected action — same shape as confirmed for
 * badge purposes. Item 11 cosmetic may differentiate semantically
 * later (e.g., audit-event categorization); for the badge derivation
 * they're identical.
 */
export function applyMatchRejected(
  state: MatchCandidatesMap,
  intakeId: string,
  counterpartyId: string,
): MatchCandidatesMap {
  return applyMatchConfirmed(state, intakeId, counterpartyId);
}

/**
 * Derived selector for the queue rail badge value.
 * Counts intakes with at least one active candidate.
 */
export function getActiveMatchCount(state: MatchCandidatesMap): number {
  let count = 0;
  for (const entry of Object.values(state)) {
    if (entry.candidate_count > 0) count++;
  }
  return count;
}
