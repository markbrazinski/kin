/* Bundle 1.5 S5 — matchCandidates state-helper tests.
   - candidate_count=0 doesn't increment getActiveMatchCount
   - candidate_count=2 for new intake_id increments by 1
   - 3 sequential events for same intake_id: latest-wins, count stays 1
   - match_confirmed removes counterparty + decrements (floors at 0)
   - match_rejected behaves identically to confirmed for badge purposes
*/
import { describe, it, expect } from 'vitest';
import {
  INITIAL_MATCH_CANDIDATES,
  applyMatchProposed,
  applyMatchConfirmed,
  applyMatchRejected,
  getActiveMatchCount,
} from './matchCandidates';

const T = (n: number) => new Date(2026, 3, 30, 12, n).toISOString();

describe('matchCandidates', () => {
  it('match_proposed with candidate_count=0 does not increment getActiveMatchCount', () => {
    const state = applyMatchProposed(
      INITIAL_MATCH_CANDIDATES,
      'intake-1',
      0,
      ['intake-1'],  // empty-result: single id (the new record)
      T(0),
    );
    expect(getActiveMatchCount(state)).toBe(0);
    // The entry IS recorded (audit history) but doesn't contribute.
    expect(state['intake-1']).toBeDefined();
    expect(state['intake-1'].candidate_count).toBe(0);
  });

  it('match_proposed with candidate_count=2 for new intake_id increments by 1', () => {
    const state = applyMatchProposed(
      INITIAL_MATCH_CANDIDATES,
      'intake-1',
      2,
      ['intake-1', 'cand-a', 'cand-b'],
      T(0),
    );
    expect(getActiveMatchCount(state)).toBe(1);
  });

  it('three sequential match_proposed events for same intake_id: latest-wins, getActiveMatchCount stays 1', () => {
    let state = INITIAL_MATCH_CANDIDATES;
    // Turn 1: 1 candidate.
    state = applyMatchProposed(state, 'intake-1', 1, ['intake-1', 'cand-a'], T(0));
    // Turn 2: 3 candidates.
    state = applyMatchProposed(state, 'intake-1', 3, ['intake-1', 'cand-a', 'cand-b', 'cand-c'], T(1));
    // Turn 3: 2 candidates.
    state = applyMatchProposed(state, 'intake-1', 2, ['intake-1', 'cand-x', 'cand-y'], T(2));

    // Latest-wins: turn 3 state is what's in the map.
    expect(state['intake-1'].candidate_count).toBe(2);
    expect(state['intake-1'].record_ids).toEqual(['intake-1', 'cand-x', 'cand-y']);
    expect(state['intake-1'].last_updated).toBe(T(2));

    // Idempotency for badge: still one intake with active candidates.
    expect(getActiveMatchCount(state)).toBe(1);
  });

  it('match_confirmed removes counterparty and decrements; floors at 0', () => {
    let state = applyMatchProposed(
      INITIAL_MATCH_CANDIDATES,
      'intake-1',
      2,
      ['intake-1', 'cand-a', 'cand-b'],
      T(0),
    );
    expect(getActiveMatchCount(state)).toBe(1);

    state = applyMatchConfirmed(state, 'intake-1', 'cand-a');
    expect(state['intake-1'].candidate_count).toBe(1);
    expect(state['intake-1'].record_ids).toEqual(['intake-1', 'cand-b']);
    expect(getActiveMatchCount(state)).toBe(1);

    state = applyMatchConfirmed(state, 'intake-1', 'cand-b');
    expect(state['intake-1'].candidate_count).toBe(0);
    expect(state['intake-1'].record_ids).toEqual(['intake-1']);
    // Entry stays in map but no longer contributes to badge.
    expect(getActiveMatchCount(state)).toBe(0);

    // Floor check: confirming again doesn't go negative.
    state = applyMatchConfirmed(state, 'intake-1', 'cand-x');
    expect(state['intake-1'].candidate_count).toBe(0);
  });

  it('match_rejected behaves identically to match_confirmed for badge purposes', () => {
    const start = applyMatchProposed(
      INITIAL_MATCH_CANDIDATES,
      'intake-1',
      2,
      ['intake-1', 'cand-a', 'cand-b'],
      T(0),
    );
    const afterConfirmed = applyMatchConfirmed(start, 'intake-1', 'cand-a');
    const afterRejected = applyMatchRejected(start, 'intake-1', 'cand-a');

    expect(afterConfirmed['intake-1'].candidate_count).toBe(
      afterRejected['intake-1'].candidate_count,
    );
    expect(afterConfirmed['intake-1'].record_ids).toEqual(
      afterRejected['intake-1'].record_ids,
    );
    expect(getActiveMatchCount(afterConfirmed)).toBe(getActiveMatchCount(afterRejected));
  });
});
