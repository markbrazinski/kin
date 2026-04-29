# KIN — Handoff

**Project:** KIN — Offline multilingual family-reunification intake copilot
**Hackathon:** Gemma 4 Good Hackathon (Google DeepMind / Kaggle)
**Submission deadline:** May 17, 2026
**Solo developer:** Mark Brazinski (Twilio PM, non-developer; Claude Code is implementer)
**Hardware:** MacBook Air M4
**Last updated:** May 1, 2026 — Phase 1 certified

---

## Read this first

You are picking up a hackathon project that ships in 16 days. The runtime
spine landed May 1 (commits `9615bcd` → `bfa50e9`). The next bundle is
Bundle 1: SSE wiring + four UI affordances (May 2-4). After that, Bundle 2
(Tent A snapshot + smoke test, May 5-6), then safety-net video window
(May 7-9), feature freeze May 10, polish window May 10-12, final video
production May 13-15, submit May 16.

The discipline that produced Phase 1 cleanly is plan-approve-execute,
session-by-session, with cross-session decisions locked at the planning
gate and pre-flight Boss-mode questions surfaced before each session.
Mark approves; Claude Code executes; verdict returns. No silent commits,
no scope drift mid-session. Replicate this in every bundle.

---

## Current state (May 1, post-Phase 1)

**Backend pipeline complete.** `ingest_audio(audio_path, lang, source_device_id, *, whisper, ollama, storage)` runs end-to-end from audio file → persisted IntakeRecord with full audit trail, validated against real Whisper + real Gemma 4 E2B in 4.5 seconds wall-clock (warm).

Pipeline stages:
1. Whisper transcription (source-language text)
2. Gemma translation (source → English; skipped if `lang="en"`)
3. `safety_rules.classify` on source text — crisis path branches early
4. Gemma `tool_call(extract_intake_fields, source_text)` — returns ToolCallResult
5. Map extracted args → IntakeRecord fields (Latin / non-Latin transliteration logic)
6. Persist: `create_intake_record(status="partial")` + bulk `update_intake_record(...fields)`
7. Matching trigger: pairwise fan-out, persist hits as proposed MatchLinks
8. Promote to `status="complete"` if both required identity fields populated

Crisis records skip 4-7. All audit events auto-emit per Part 1 REV 4 mapping.

**Frontend still on setTimeout fakes.** React app shell, audio waveform, field-population animations, completeness meter, color-coded safety beats, end card — all stable from Days 1-7. SSE not yet wired. The four high-risk affordances (merge animation, two-device differentiation, structlog sidebar, JSON function-call sidebar) are unbuilt. Bundle 1 fixes this.

**Storage runtime.** `storage/` directory at repo root, gitignored. Three JSONL files: `intake_records.jsonl`, `match_links.jsonl`, `audit_events.jsonl`. Single-writer assumption. No concurrency.

**Tent A Mohammed snapshot mechanism unbuilt.** Waits on Fiverr Arabic audio (May 5+). Bundle 2 territory.

**Demo audio.** `audio_samples/spanish_intake_tts_01.wav` is TTS-generated Spanish ("Estoy buscando a mi hijo. Se llama Carlos."). Functional for smoke test; will swap to real audio when Fiverr Spanish lands or Mark self-records.

---

## Test counts

| State | Count |
|---|---|
| Pre-S2 baseline | 75 |
| Post-S2 (storage layer) | 97 |
| Post-S3 (extraction tool-calling) | 107 |
| Post-S4 (orchestration) | 113 |
| Post-S5 (matching trigger + audit verification) | 118 |
| Post-S6 (Phase 1 smoke) | 119 (118 fast + 1 smoke) |

**Run modes:**
- `pytest` → 118 fast tests in ~8s (smoke excluded by default)
- `pytest -m smoke` → 1 real-models smoke test in ~14s cold / ~8s warm

All 8 audit_event types from Part 1 REV 4 enum have ≥1 test asserting emission. Layer boundary test green throughout (8/8). Zero regressions across S2-S6.

---

## Locked decisions (do not relitigate)

### Architecture Decision Records

| ADR | Subject | Status |
|---|---|---|
| ADR-001 | Web UI primary demo surface (Claude Code IDE for caseworker review) | LOCKED |
| ADR-003 | Gemma `think=False` enforcement | LOCKED |
| ADR-004 | Orchestration architecture (extraction-via-tool-calling, matching-trigger placement, crisis-path branching, bulk vs progressive field_extracted emission) | LOCKED |

### Cross-session decisions from Phase 1 brief

These were locked at the Apr 29 planning gate. They govern any code that touches the pipeline.

- **IntakeRecord shape:** flat per Part 1 REV 4 spec. No nested RFLRecord. Pydantic v2, `ConfigDict(extra='ignore')`.
- **RFLRecord** stays as the in-flight extraction model. Storage owns persistence (flat); matching owns the algorithm domain (nested). The bridge `_to_rfl_record(intake)` in `transcription_pipeline.py` translates between them.
- **Storage location:** `storage/` at repo root, gitignored. Three JSONL files.
- **UUID + timestamps:** `uuid4()` for IDs. Timestamps via Clock-injected `now()` (extended Protocol). `StorageAdapter` accepts a Clock in its constructor; FakeClock for tests.
- **Concurrency model:** none. Read-modify-write for updates. Single-writer assumption documented in `storage_adapter.py` module docstring.
- **Audit-event mapping ownership:** lives in `storage_adapter` (auto-write on CRUD operations). Pipeline never writes audit events directly — it triggers them via storage operations. The Part 1 REV 4 audit-event mapping table is the contract.
- **Matching-trigger placement:** orchestration, not storage. `_trigger_matching` lives in `transcription_pipeline.py` next to `ingest_audio`. ADR-004 records the rationale.
- **Crisis-path branching:** when `safety_rules.classify` returns `is_crisis=True`, `ingest_audio` persists a `paused_for_crisis` record with referral fields and returns. No tool_call invocation, no `_trigger_matching` call.
- **Bulk vs progressive `field_extracted` emission:** orchestration emits all field_extracted events at once after a single tool_call. Beat 5's progressive turn-by-turn appearance is NOT an orchestration concern — Bundle 1's SSE-wiring brief inherits this constraint and resolves it via either three sequential audio files or staggered SSE rendering.
- **Mapping rules:**
  - Latin-script langs (en, es, fr): `full_name_source_script = full_name_transliteration = args.full_name`
  - Non-Latin langs (ar, fa, uk): `full_name_source_script = args.full_name`, `full_name_transliteration = ""` (worker-entered later)
  - `is_minor = (args.age is not None and args.age < 18)`
  - `crisis_match_path = "keyword"` if `safety_result.matched_keywords` non-empty, else `None`. (`"semantic"` enum value defined but unwritten until Day 8-9 future work.)
  - `minor_flagged` event emitted via structlog only, not persisted as audit_event (per Part 1 REV 4 enum constraint).

### Demo and prize strategy decisions

- **Primary prize target:** Digital Equity & Inclusivity ($10K)
- **Demo script v2 locked at 2:20 target** (9 segments)
- **6 supported languages:** en, es, ar, fa, fr, uk. Demo features en/es/ar/fa.
- **Matching algorithm:** Jaro-Winkler ≥0.85 gate + composite ≥0.70, source-script preservation, NO LLM in matching path. Locked at `matching.py`.

---

## Working discipline

### Plan-approve-execute (mandatory)

1. Mark sends a brief with sessions S1-Sn defined.
2. Agent enters S1, returns a plan (file changes, test counts, pre-flight resolutions, exit criteria, escalation triggers, commit message).
3. Mark reviews plan, surfaces Boss-mode questions if needed, approves.
4. Agent executes S1, returns verdict (test counts, files changed, regressions, pre-flight resolutions held).
5. Mark approves S1 commit, agent commits locally.
6. Repeat for S2..Sn.

No silent decisions. No surprise scope expansion. No git push without explicit "push it" from Mark.

### Pre-flight Boss-mode questions

Surface decisions BEFORE writing code, not during. The Phase 1 pattern: when an agent encounters a fork that affects multiple sessions or contradicts an ambient assumption, it returns a question with options and a recommendation. Mark answers in seconds; the alternative is hours of mid-session rework.

Examples from Phase 1 that earned their keep:
- Pydantic v2 enum/datetime serialization probe before S2 (resolved: Literal types round-trip cleanly)
- Source-text vs English-translation for extraction before S4 (resolved: source text)
- Failure-mode for Whisper exceptions before S4 (resolved: propagate, no defensive record)
- File placement for `_trigger_matching` before S5 (resolved: same file as `ingest_audio`)
- Spanish fixture choice before S6 (resolved: spanish_01.wav, then re-pointed to TTS when content gap surfaced)
- Smoke marker default before S6 (resolved: exclude by default)

### Test budget caps

Each session names a test count target (e.g. "10-12"). Hit the lower bound. If tests creep past the upper bound, that's an escalation trigger — pull back rather than over-cover. Phase 1 sessions hit:

| Session | Budget | Actual |
|---|---|---|
| S2 | 15-20 | 20 storage + 9 Clock = 29 (Clock surplus from Protocol extension, called out in pre-flight) |
| S3 | 10-12 | 10 |
| S4 | 5-7 | 6 |
| S5 | 3-4 + 1 | 4 + 1 |
| S6 | 1 | 1 |

### One commit per session

Clean rollback boundaries. Each session = one commit with `phase-Sn:` prefix. Phase 1 commit chain:

```
bfa50e9 phase-S6 followup: TTS fixture re-point + smoke GREEN  ← Phase 1 closure
2a48878 phase-S6: Phase 1 smoke test infrastructure
eeafcc4 phase-S5: matching trigger + ADR-004 + matching docs §9
c97f86e phase-S4: ingest_audio orchestration
cd82c3a phase-S3: ollama tool_call() + extract_intake_fields tool
9615bcd phase-S2: storage layer (IntakeRecord/MatchLink/AuditEvent + Clock.now())
```

### Layer boundaries

Three layers: Core / Integration / UI. AST-enforced via `tests/test_layer_boundaries.py`. Core never imports from Integration or UI. Integration may import from Core. UI may import from Integration. Test must stay green after every session.

### No git push

Local commits only. Mark pushes when ready. The voice in the agent's head saying "let me push to back this up" is the enemy.

---

## Bundle map (May 1 → May 17)

| Bundle | Window | Sessions | Status |
|---|---|---|---|
| Phase 1: orchestration build | Apr 29 - May 1 | S1-S6 | ✅ DONE |
| Bundle 1: SSE + four UI affordances | May 2-4 | ~6 sessions | NEXT |
| Bundle 2: Tent A snapshot + smoke | May 5-6 | ~3-4 sessions | Pending Fiverr Arabic |
| Safety-net video window | May 7-9 | recording, light CC support | — |
| Feature freeze | May 10 | — | — |
| Polish + LLM-as-judge passes | May 10-12 | ~4-5 sessions | — |
| Final video production | May 13-15 | recording, light CC support | — |
| Submit | May 16 | — | — |
| Deadline buffer | May 17 | — | — |

LLM-as-judge passes per SKILL Phase 5.5: three total — post-orchestration (~May 6), post-freeze (~May 11), post-video (~May 15).

---

## Pending Mark async tracks

These don't block Bundle 1 but have downstream deadlines.

- **Fiverr orders.** Hold-until-May-1 over. Spanish (gigs 1, 2A) and Arabic (gigs 2B, 3) ready to release. Skip Order 4 (Farsi). Delivery May 5-7 lands before safety-net window.
- **Spanish self-recording.** 15 min, anytime. Useful to have non-TTS Spanish in `audio_samples/` before Bundle 1 ships, so SSE rendering demos against natural audio. Optional but worthwhile.
- **Caseworker outreach batch.** ~20 humanitarian-org cold emails (ICRC, IRC, UNHCR, HIAS, MSF, etc.) for 15-30 sec testimonial. Deadline May 6 to incorporate into final video. Async, no blocker.
- **PROJECT_PLAN.md.** Surgical update to replace abstract Day-counter §4 with the 17-day calendar plan, and reflect Phase 1 closure in §7. Async; doesn't block any bundle.

---

## File reference

### Code

- `src/core/` — pure logic, no I/O
  - `clock.py` — Clock Protocol with `monotonic()` + `now()`
  - `storage_schemas.py` — IntakeRecord, MatchLink, AuditEvent (Pydantic v2, Literal types)
  - `tool_calling.py` — ToolCallResult Pydantic model
  - `matching.py` — locked algorithm (Jaro-Winkler + composite); see `docs/matching.md`
  - `safety_rules.py` — keyword-based crisis classifier
  - `language_matrix.py` — language → script mapping
  - `rfl_schema.py` — in-flight extraction model

- `src/integration/` — adapters and orchestration
  - `transcription_pipeline.py` — `ingest_audio`, `_trigger_matching`, `_to_rfl_record`, `transcribe_and_translate`
  - `ollama_adapter.py` — `translate()`, `tool_call()`, retry+timeout logic, ADR-003 enforcement
  - `whisper_adapter.py` — Whisper transcription wrapper
  - `storage_adapter.py` — JSONL CRUD, audit-event auto-write
  - `system_clock.py` — production Clock implementation
  - `extraction_tools.py` — EXTRACT_INTAKE_FIELDS_TOOL JSON Schema, ExtractIntakeFieldsArgs Pydantic model
  - `_errors.py` — adapter exception hierarchy

- `tests/`
  - `tests/core/` — schema tests, pure-logic tests
  - `tests/integration/` — adapter tests, pipeline tests, smoke test
  - `tests/fakes/` — FakeClock and other test doubles
  - `tests/test_layer_boundaries.py` — AST-enforced layer rules
  - `tests/test_clock_protocol.py` — Clock conformance

### Docs

- `docs/ADR/001-web-ui-primary-demo-surface.md`
- `docs/ADR/003-gemma-think-false.md`
- `docs/ADR/004-orchestration-architecture.md`
- `docs/ADR/005-sse-tests-use-real-uvicorn.md` — Bundle 1 S1: SSE route tests use real uvicorn fixture, not httpx.ASGITransport
- `docs/matching.md` — locked matching algorithm + §9 runtime trigger entry point
- `docs/architecture-diagram.{mmd,png}` — Devpost-quality system diagram
- `docs/architecture-diagram-legend.png`
- `docs/architecture-diagram-CHANGES.md`

### Runtime (gitignored)

- `storage/intake_records.jsonl`
- `storage/match_links.jsonl`
- `storage/audit_events.jsonl`

### Demo assets

- `audio_samples/spanish_intake_tts_01.wav` — TTS Spanish, used in S6 smoke test
- `audio_samples/raw/` — Fiverr destination (empty until May 5+)
- `seeds/tent_a_mohammed_snapshot.json` — to be generated in Bundle 2

---

## Phase 1 retrospective (carry into next bundles)

What worked, in priority order:

1. **Cross-session decisions locked at planning gate.** IntakeRecord shape, audit-event mapping ownership, concurrency model, mapping rules — once decided, never relitigated. Saved hours of mid-session re-deciding.
2. **Pre-flight Boss-mode questions before each session.** ~30 seconds to answer; cost of wrong answer mid-session would've been hours.
3. **Plan-approve-execute discipline.** No silent decisions, no surprise commits. Course-correction between sessions instead of after.
4. **Test budget caps in the brief.** Pulled discipline out of the brief, not relying on agent restraint.
5. **ITEM E (audit-event mapping) as verification, not implementation.** Walking the table at S5 entry was the right move; mapping was satisfied incrementally across S2-S5.
6. **One commit per session.** Clean rollback boundaries.

What to adjust:

- S5 plan got long because three concerns (matching trigger, audit verification, ADR-004) bundled together. Worth tighter session scopes when work has natural seams. But tight coupling here was real — a fourth session would've been ceremony.
- Stub class proliferation (test_ingest_audio.py's _OllamaStub, test_matching_trigger.py's setup) is small but compounding. Worth a brief shared-test-fixtures pass somewhere in May 10-12 polish window.

---

## Open questions for next bundle (Bundle 1 planning gate)

These are not pre-resolved. They surface at Bundle 1's planning gate as Boss-mode questions.

- **SSE protocol:** raw EventSource via FastAPI StreamingResponse, or sse-starlette dependency, or asyncio-based generator? Trade-off: dependency weight vs implementation complexity.
- **Reconnection strategy:** auto-reconnect with backoff, or manual reconnect on user action? Demo needs deterministic behavior; production would want auto-reconnect.
- **Event filtering:** does the SSE endpoint serve all audit events, or filter by `source_device_id` server-side? Two-device differentiation (Bundle 1 affordance b) needs per-device streams.
- **Frontend state management:** plain useReducer, Zustand, or other? Existing React app's pattern from Days 1-7 dictates.
- **Beat 5 progressive-fill mechanism:** three sequential audio files (per Part 3 Issue 1) or SSE-side staggered rendering? ADR-004 deferred this to Bundle 1.
- **`full_name_transliteration` UI affordance state:** Day 11 prereq verification confirmed State 3 (no IntakePanel transliteration field exists) — needs build in Bundle 1 Affordance (b.1). Verify still true at Bundle 1 entry.

---

## Forward notes (active during Bundle 1, surface at relevant session entry)

These are not Boss-mode questions for the planning gate; they are short carry-forward reminders that future-session CC should encounter and decide on. Add new ones at session-end verdict; remove when resolved.

- **Split-mode IntakePanel uses SimpleVoicePanel (compact).** S3 introduced a compact voice-status row inside `IntakePanel` because two full `VoicePanel` components would dominate the viewport in split-view. If the demo storyboard wants the full `VoicePanel` visible in split mode, that is an S7 polish call (or earlier if recording reveals it). Not blocking S4-S6.

- **React `Language` type out of sync with Python `SupportedLanguage` enum.** [src/ui/web/src/lib/types.ts:9](src/ui/web/src/lib/types.ts#L9) defines `Language = 'en' | 'es' | 'ar' | 'fa'`. Python's enum at [src/core/storage_schemas.py:39](src/core/storage_schemas.py#L39) is `'en' | 'es' | 'ar' | 'fa' | 'fr' | 'uk'`. UK and FR exist as data-layer capacity only — not in the demo path — so the mismatch is harmless today, but a UK record arriving via SSE would surface a TS error somewhere. Reconcile in polish week or post-bundle handoff. Not blocking S4-S7.

---

## Contact pattern with strategy thread (Mark + Claude as orchestrator)

Mark uses Claude in two roles:

1. **Strategy thread (this is Mark's chat with Claude):** brief drafting, retrospectives, boss-mode question answering, bundle planning. Reads HANDOFF.md and bundle context docs.
2. **Implementation agent (Claude Code in IDE):** executes session plans, returns verdicts. Receives the brief from strategy thread; doesn't see strategy thread chat history.

The implementation agent is short-context. It knows what the brief tells it. The strategy thread (or successor) is long-context across the project; HANDOFF.md is what survives compaction.

---

**End of handoff. Bundle 1 brief lives in `briefs/bundle-1-context.md` (or wherever Mark places it).**
