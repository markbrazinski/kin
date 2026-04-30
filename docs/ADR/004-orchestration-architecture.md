# ADR-004: Orchestration architecture (extraction + matching trigger + crisis path)

**Date:** April 30, 2026 (Day 13)
**Status:** LOCKED
**Records:** S2-S5 orchestration build (commits `9615bcd`, `cd82c3a`, `c97f86e`, S5 commit)

## Context

The Apr 29-30 orchestration build (S2-S5) wired four subsystems into a
single async entry point — `ingest_audio()` in
`src/integration/transcription_pipeline.py`. Three architectural
decisions surfaced during planning that needed to be recorded so future
readers (and the SSE-wiring brief downstream) inherit the constraints
cleanly:

1. **Where does extraction logic live?** The Apr 28 hello-world cleared
   GREEN on Gemma 4 E2B native tool-calling for Spanish; the Apr 29
   multilang sweep cleared GREEN across EN/AR/FA. Building extraction
   on top of that surface (vs. the alternatives) was the decision to
   record.
2. **Where does the matching trigger fire?** Day 11 prereq verification
   surfaced that `match_records` had zero non-test callers; Part 1 REV 4
   §"Required matching trigger behavior" specified *what* the trigger
   must do but not *where* it should live. Storage layer vs. orchestration
   layer was the live design question.
3. **What does the crisis path skip?** Part 1 REV 4 §Beat 7 specifies
   the crisis-path audit-event sequence; the orchestration concern is
   ensuring extraction and matching trigger are correctly bypassed.

A fourth question — bulk vs. progressive `field_extracted` event
emission — surfaced during S4 planning and is locked here for the
SSE-wiring brief to inherit.

## Decision

### 1. Extraction via Gemma native tool-calling

`OllamaAdapter.tool_call(messages, tools) -> ToolCallResult` lives in
`src/integration/ollama_adapter.py` (S3 commit `cd82c3a`).
`extraction_tools.py` defines the `EXTRACT_INTAKE_FIELDS_TOOL` JSON
Schema dict, lifted verbatim from the Apr 28 hello-world that cleared
GREEN. `ExtractIntakeFieldsArgs` Pydantic model validates the raw
arguments dict in `ingest_audio` (S4).

Alternatives rejected:

- **`format=<schema>` structured output:** the Days 8-9 "structured-
  output saga" showed silent dropping of the `format` parameter under
  `think=False` (ADR-003 lock). 0/3 schema-valid envelopes across
  multiple probes. Tool-calling is a different daemon code path; the
  Apr 28 hello-world specifically tested for the Days-8-9 echo and
  did not see it.
- **Regex / grammar parsing of free-text completion:** brittle on
  multilang input, fails on transliteration variance, doesn't compose
  with the Pydantic-validated schemas downstream.

Tool-calling preserves source-script identity in `full_name` (Apr 29
sweep validated محمد, رضا, hijo, ابن, پسر emitted verbatim), which the
storage spec's `full_name_source_script` field requires.

### 2. Matching trigger placement: orchestration, not storage

`_trigger_matching(new_record, *, storage) -> list[MatchLink]` lives
in `src/integration/transcription_pipeline.py` alongside `ingest_audio`,
NOT in `src/integration/storage_adapter.py`.

Rationale:

- **Matching is a domain decision** (which records correspond to the
  same person), not a persistence operation. Putting the trigger in
  `storage_adapter` would couple persistence to domain logic.
- **`storage_adapter` would need to know the matching algorithm** to
  fire it on the right CRUD operations — both a layer-boundary smell
  and a tight coupling that would make storage tests depend on
  matching's confidence bands.
- **Orchestration already knows what a "new record" is.** It knows
  when extraction completes, knows the crisis branch should skip
  matching, and knows when to advance the record to `complete`. The
  trigger's six-line filter (drop self, drop crisis-paused) lives
  comfortably alongside these concerns.

Concrete placement: `_trigger_matching` runs as Stage 7 of
`ingest_audio`, between the `minor_flagged` structlog emission (Stage 6)
and the optional `status="complete"` promotion (Stage 8). The crisis
branch returns earlier at `_persist_crisis_record`, so the trigger
never runs for crisis records.

`_to_rfl_record(intake) -> RFLRecord` bridges `IntakeRecord` (flat
storage shape per Part 1 REV 4) to `RFLRecord` (nested matching domain
shape per `core.matching`). Storage and matching both stay unchanged;
the bridge is an orchestration helper.

### 3. Crisis-path branching skips extraction + matching

When `safety_rules.classify(transcription, lang=lang)` returns
`is_crisis=True`, `ingest_audio` invokes `_persist_crisis_record` and
returns. No `tool_call` invocation. No `_trigger_matching` call.

Per Part 1 REV 4 §"Required matching trigger behavior" point 5
(paused_for_crisis records excluded from the candidate pool), this
also ensures crisis records don't pollute future matching runs — a
crisis-paused record sitting in storage will be skipped both as the
new record (it never triggers matching) and as a candidate (it's
filtered out of the pool).

The crisis-path identity fields are left empty (per Part 1 §Beat 7
"whatever Whisper produced"); referral fields are populated from the
`_REFERRAL_ORG_BY_LANG` mapping.

### 4. Bulk vs. progressive `field_extracted` emission

Orchestration emits all `field_extracted` events at once after a single
`tool_call` (one bulk update via `update_intake_record(id, **fields)`).
The number of events depends on which fields the model populated; a
typical Carlos case (Latin script, age omitted) emits 4 events
(`full_name_source_script`, `full_name_transliteration`,
`relationship_to_seeker`, `is_minor`).

Beat 5's progressive turn-by-turn field appearance is NOT an
orchestration concern. The SSE-wiring brief (separate, May 2-4) will
achieve progressive rendering via either:

- (a) three sequential audio files processed in sequence per Part 3
  Issue 1, each producing its own `intake_created` + N
  `field_extracted` burst, OR
- (b) staggered SSE rendering of the bulk `field_extracted` batch from
  a single audio file.

Either approach keeps orchestration's contract simple: one extraction
call → one bulk update → one event burst.

## Consequences

**Positive:**

- Single audit-event ordering invariant per ingest path:
  - non-crisis: `intake_created` → `field_extracted ×N` →
    `match_proposed ×0..N` → optional silent status promotion
  - crisis: `intake_created` → `intake_paused` → `crisis_detected` →
    `referral_issued` → `field_extracted ×4`
- Extraction and matching independently testable via stubs; neither
  needs the other to validate.
- Crisis path is a clean early-return; no defensive guards scattered
  through later stages.
- `_trigger_matching` is observable via structlog
  (`matching_trigger_fired`) regardless of match count, so trigger
  execution is auditable even when no matches result.

**Negative / accepted:**

- `_trigger_matching` does N storage list reads per ingest (no caching
  layer; linear scan of `list_intake_records()`). Acceptable for demo
  scale (≤10 records). Production scale would need an index or a
  materialized matching graph; out of scope for May 17 submission.
- The flat-IntakeRecord ↔ nested-RFLRecord bridge is hand-written in
  `_to_rfl_record`. If either schema evolves, the bridge needs
  updating. Accepted — both schemas are locked at the planning gate;
  evolution is a separate brief.
- Bulk `field_extracted` emission means there is no orchestration-side
  affordance for per-field timing. SSE downstream owns this.

## Followup

None. The four decisions land in code and tests in the S5 commit;
ADR-004 preserves the rationale.

## REV 2 — Crisis branch invokes Gemma for referral formatting (S6, 2026-04-29)

**Status:** Accepted

### Change

The crisis branch in `transcription_pipeline.ingest_audio` now invokes
Gemma via `ollama.tool_call()` with the `escalate_crisis` tool when
`safety_rules.classify` returns `is_crisis=True`. Gemma returns a
`referral_organization` (locale-aware NGO name in the speaker's
language) and a `locale_aware_message`. The `referral_organization`
is passed to `_persist_crisis_record`, which writes it to the
existing `IntakeRecord.referral_organization` field. The
`locale_aware_message` is emitted via structlog (event name
`crisis_referral_formatted`) and rides the SSE bridge to the
frontend sidebar; it is NOT persisted to `IntakeRecord` or to
`audit_events.jsonl`.

Previously the crisis branch was deterministic-only: classify →
static `_REFERRAL_ORG_BY_LANG` lookup → triple-emit → return.

### Why this is not a safety-gate regression

The deterministic keyword classifier (`safety_rules.classify`)
remains the **sole safety gate**. Gemma's role on the crisis path is
structured-output formatting only: it picks an NGO name and writes a
short calm message in the speaker's language. Gemma does NOT decide
whether a turn is a crisis. That decision is made by `classify` and
is fully auditable by reading `matched_keywords` in the structlog
trail (and via the `crisis_match_path="keyword"` field on the
persisted `IntakeRecord`).

If the Gemma `escalate_crisis` tool_call fails (timeout, schema
validation failure, model unavailable), `_format_crisis_referral`
catches `InferenceTimeout` / `InferenceFailed` / `InvalidToolCall` /
`ValidationError` and falls back to the static `_REFERRAL_ORG_BY_LANG`
lookup. The crisis flag still fires, the audit triple still emits,
the user still sees a referral organization — only the message
text degrades from Gemma-generated to absent (empty string), and
the organization name degrades from locale-tuned to template.

`crisis_match_path` stays `"keyword"` regardless — the keyword
classifier still decided. There is no "semantic" path in S6.

### Why this is reversible

If a future review concludes that Gemma-generated output on the
safety path is too risky even bounded to formatting, the change is
straightforward to revert:

1. Remove the `_format_crisis_referral` call from the crisis branch
   in `ingest_audio` (5 lines)
2. `_persist_crisis_record(referral_organization=None)` is the
   default; the static fallback path runs on its own
3. Optionally delete `_format_crisis_referral`,
   `_build_crisis_messages`, `_CRISIS_SYSTEM_PROMPT`, and
   `escalate_crisis_tool.py`

No data migration needed. No persisted record schema depends on
Gemma output. The audit triple is unchanged.

### Forward note for future agents

**Do not roll back this REV 2 thinking it is drift.** The criterion
for revert is: "is Gemma's output on the safety path causing harm
we cannot detect?" Not: "did we recently add a Gemma call we should
remove for cleanliness?" Reverting is straightforward (remove
`_format_crisis_referral` call from the crisis branch;
`_persist_crisis_record` falls back automatically). The work to
revert is small; the work to re-add was bounded and intentional.

## REV 3 — `locale_aware_message` also rides the POST response (S6-fix2, 2026-04-29)

**Status:** Accepted

### Change

REV 2 stated that `locale_aware_message` "rides on the existing
structlog → SSE bridge to the frontend." That channel is wired and
unchanged: `crisis_referral_formatted` is emitted with the message
at `transcription_pipeline.py:443-449`, broadcast verbatim by
`sse.py`, and surfaced in the frontend structlog sidebar.

REV 3 adds a **second delivery channel**: `ingest_audio` now returns
`tuple[IntakeRecord, str | None]` (the optional message is non-None
only on the crisis branch), and the `/intake/audio` POST handler
surfaces it on its response model `AudioUploadResponse` when
`status="paused_for_crisis"`. The frontend overlay
(`CrisisReferralCard`) reads the message from the synchronous POST
response and renders it as the displaced-person-facing body, with
`CRISIS_COPY[lang].body` as the fallback when no message is
provided (Gemma tool_call failure → `_format_crisis_referral`
returns `""` → normalized to `None` → component falls back).

The message remains **ephemeral**: not written to `IntakeRecord`,
not written to `audit_events.jsonl`, not written to any persistent
store. Both the SSE event and the POST response carry it across
the request/response cycle only.

### Why this is not a regression

The POST response channel and the SSE channel are independent
deliveries of the same payload. Neither persists. The ephemerality
lock from REV 2 is constraint on **storage**, not on transient
delivery channels — and was always ambiguous about whether the SSE
channel was the only allowed transport.

The deterministic safety gate is unchanged: `safety_rules.classify`
still decides the crisis branch, Gemma is still formatter-only,
fallback to `_REFERRAL_ORG_BY_LANG` and empty message still holds
on tool_call failure.

The only architectural shift is the route handler unpacking a
two-tuple instead of a single record. All other `ingest_audio`
callers (today: tests only) update to the same unpack.

### Why two channels instead of one

The overlay needs the message at open time. The POST response is
synchronous with the trigger that opens the overlay (the crisis
status discriminator). SSE arrivals are not ordered against the
POST response — the structlog event for `crisis_referral_formatted`
fires on the backend during `_format_crisis_referral` (before the
route returns), but its arrival at the frontend SSE consumer is
network-bound and asynchronous. The race window is small (~5-50ms
on localhost) but real, and produces user-visible artifacts: the
overlay either opens with empty body and pops in the message, or
opens before the message lands and looks broken.

Anchoring the overlay-open trigger to the POST response makes the
trigger-and-content arrive atomically. The SSE channel stays for
two reasons: (1) it backs the structlog sidebar, which is a
demo-credibility surface ("you can see Gemma's tool call landing
live"); (2) it is the documented reversion path if a future review
prefers the simpler architecture.

### Why this is reversible

Removing the POST response channel is a deletion:

1. Revert `ingest_audio` to return `IntakeRecord` (drop the tuple)
2. Drop the optional `locale_aware_message` field from
   `AudioUploadResponse` and the route handler's status-gated
   population
3. Drop the optional `message` prop from `CrisisReferralCard`
4. Drop the App-level `crisisMessage` state and the
   `onCrisisResponse` callback wiring; the SSE consumer reads the
   message from the `crisis_referral_formatted` structlog event
   payload that already arrives via `useEventStream`

The structlog event is unchanged across REV 2 / REV 3, so the SSE
fallback path requires no backend touch on revert.

### Forward note for future agents

REV 3 does NOT relax the ephemerality lock. If you find yourself
adding `locale_aware_message` to `IntakeRecord`, `AuditEvent.details`,
JSONL, or any other persistent store, you are violating REV 2 — not
REV 3. The two transient channels (SSE event payload, POST response)
are the only places this string may appear.

The Gap 3 fix that ships with REV 3 (clearing `intakeId` after a
crisis turn so the next turn takes the create-path, see
`transcription_pipeline.py:258-266`) is part of the wiring commit,
not part of this ADR — it preserves S5 lock #4 (crisis path is
create-only) by ensuring the frontend never POSTs an `intake_id`
referencing a `paused_for_crisis` record.

## References

- Part 1 REV 4 (storage state spec): `intake_record` fields,
  `match_link` fields, `audit_event.event_type` enum, matching trigger
  contract.
- Part 2 REV 3 (production audit): audit-event mapping table, sidebar
  event names.
- Apr 28 hello-world: `results/gemma_extraction_helloworld_2026-04-28.md`
- Apr 29 multilang sweep:
  `results/gemma_extraction_multilang_sweep_2026-04-29.md`
- Day 11 prereq verification:
  `results/day11_prereq_verification_2026-04-27.md`
- ADR-001 (web UI as primary demo surface)
- ADR-003 (`think=False` lock)
- `docs/matching.md` §9 (runtime trigger entry point)
