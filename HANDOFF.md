# HANDOFF — Bundle 1 (CLOSED)

**Last updated:** April 29, 2026 (post-S7 commit `a08b546`, Bundle 1 architecturally closed)
**Project:** KIN — offline-first multilingual family-reunification intake copilot
**Hackathon:** Gemma 4 Good Hackathon
**Submission deadline:** May 17, 2026 (target submit May 16)
**Builder:** Solo (Mark Brazinski)

---

## Why this document exists

This thread has compacted once and will compact again. HANDOFF captures the architectural state of the codebase at the end of Bundle 1 so that future-Mark, future-Claude, and future-CC can resume work without reconstructing decisions from chat history. Update at each bundle close.

This is **architectural state**, not running task list. Quality findings, polish-week tasks, and in-flight work live elsewhere (chat thread + briefs/).

---

## Build status snapshot (Bundle 1 close, post-S7)

| Layer | Lines |
|---|---|
| Python production (`src/`) | 3,781 |
| Python tests (`tests/`) | 4,676 |
| TypeScript / TSX (`src/ui/web/src/`) | 4,176 |
| CSS | 81 |
| **Total** | **12,714** |

Test ratio: 1.24:1 (tests:production).

| Test gate | Count |
|---|---|
| Python fast pass | 139 |
| Python smoke | 3 deselected (run via `pytest -m smoke`) |
| Vitest | 35 |
| AST layer boundaries | enforced via test |
| TypeScript strict | clean |
| Vite production build | 53 modules, 196KB JS |

## Hackathon target & prize strategy

**Primary prize target:** Digital Equity & Inclusivity ($10K)
**Judging panel:** Google DeepMind + humanitarian-domain reviewers
**Differentiator:** real Gemma 4 native tool-calling, source-script preservation throughout, deterministic-then-Gemma crisis path with auditable structlog
**Demo runtime target:** 2:19 (per script v3), 2:59 hard cap

---

## Workflow conventions

### Plan-approve-execute discipline (DO NOT BREAK)

Mark drafts session briefs in chat. CC enters plan mode, returns plan, awaits approval. Mark approves. CC executes. CC returns verdict.

CC never executes without an approved plan. The plan-approve gate is the last chance to catch wrong-shaped approaches before code happens.

### Test budget discipline

Every brief has a test budget range (e.g., 8-12). Hit the **floor**. Headroom exists for genuine gaps surfaced during execution, not pre-planned scope expansion. Exceeding ceiling triggers escalation.

### Commit prefix per session

- `bundle1-S{n}:` for primary session work
- `bundle1-S{n}-fix:` for QA findings on a session
- `bundle1-cleanup:` / `bundle1-cleanup-N:` for documentation, ADRs, HANDOFF updates
- `bundle1-focus-fix:` for pre-existing bugs surfaced during a session but not S{n} regressions

### Git discipline

**No `git push` without explicit Mark instruction.** All commits stay local until explicitly pushed. This is durable — survived all 6 sessions.

---

## Bundle 1 commits (chronological, all local)

| Commit | Session | Summary |
|---|---|---|
| `db200eb` | S1 | SSE backend — merged audit + structlog stream with source_device_id filter, sse-starlette, real uvicorn-in-thread test fixture |
| `f138970` | S2 | SSE frontend consumer — useEventStream hook + reducer, MockEventSource |
| `e3d613a` | S3 | Two-device split-view + themed IntakePanel (CSS variables via `data-tent` attribute, accessibility-preserving) |
| `29d9cc9` | cleanup | ADR-005 + HANDOFF.md (initial) + briefs/bundle-1-context.md |
| `309a7b8` | S4 | Transliteration field + per-panel structlog sidebar + `/qa/inject` endpoint (KIN_QA_MODE=1 gated) |
| `443f88c` | S4-fix | QA-1 findings — preserve view on reset, last-writer-wins on field re-writes |
| `c5e584a` | S5 | Pipeline progressive extend path + browser mic capture + match re-trigger + lifespan-time pre-warm |
| `b92b3b6` | S5-fix | Lifespan startup bugs |
| `a8fd161` | S5-fix2 | Additional lifespan startup fix |
| `0e7c7ca` | S6 | escalate_crisis Gemma tool + ADR-004 REV 2 |
| `d506d1d` | cleanup-2 | Post-S6 HANDOFF + Bundle 1 architectural state |
| `4f42f4c` | S6-fix2-prep | ADR-004 REV 3 — locale_aware_message also rides POST response (doc-only) |
| `4f9e38e` | S6-fix2 | Deliver locale_aware_message to crisis overlay + Gap 3 (intakeId reset on crisis) |
| `a08b546` | S7 | Beat 6 merge animation (kin-merge-pulse + prefers-reduced-motion + SSE-driven trigger) + extend smoke + crisis smoke + onBegin dead-code cleanup |

**Bundle 1 closes here. 14 commits, all local. Bundle 1.5 brief drafts next.**

---

## Architectural locks (DO NOT RELITIGATE)

### ADRs (settled, do not relitigate)

- **ADR-001:** Hexagonal architecture, Core/Integration/UI layers, AST-enforced boundaries
- **ADR-003:** JSONL append-only audit log with single-writer constraint (concurrent writes out of scope)
- **ADR-004:** Orchestration architecture — pipeline as single async coroutine, deterministic safety gate, Gemma as formatter
- **ADR-004 REV 2:** Crisis branch invokes Gemma `escalate_crisis` tool for referral formatting; deterministic `safety_rules.classify` remains sole safety gate; Gemma never decides crisis. Reversion criterion: *"is Gemma's output on the safety path causing harm we cannot detect?"* — not *"did we recently add a Gemma call we should remove for cleanliness?"*
- **ADR-004 REV 3:** `locale_aware_message` also rides the `/intake/audio` POST response (in addition to the existing structlog → SSE channel). Frontend overlay opens atomically with Gemma's locale-aware body text — eliminates the SSE race window. Ephemeral lock preserved (not persisted to IntakeRecord, AuditEvent, or JSONL).
- **ADR-005:** SSE tests use real uvicorn-in-thread fixture, not ASGITransport (mocking didn't catch real bugs)

### Bundle 1 surface locks

- **No new state library** (Zustand etc). Reducer + hook composition via `useEventStream`.
- **No new animation library** (Framer Motion etc). CSS keyframes for S7 merge animation.
- **No new dependencies without escalation.** Both Python and React.
- **No Core schema changes** during SSE work (Bundle 1). Additive Integration-layer changes are fine. **Bundle 1.5 S5 relaxation:** Lock 4's rationale is concurrent-write protection for JSONL audit logs, not absolute schema immutability. Backwards-compatible additive fields with default values are permitted (S5 added `AuditEvent.candidate_count: int = 0`; existing JSONL records remain valid because the field defaults to 0 on read).
- **Single-writer JSONL storage.** Concurrent writes out of scope.
- **127.0.0.1 localhost-only.** Never deployed. Reframed in writeup as "deliberate offline-first architecture."

### Source-language preservation (architectural commitment)

KIN preserves source language for **all** speaker-captured fields, not just names. Examples in active demo path:

- Names: `Carlos`, `محمد` (Arabic) + transliteration metadata (`Mohammed`, `Mohamad`)
- Relationships: `hijo` (not "son"), `hija` (not "daughter")
- Locations: `la frontera con Colombia` (not "the border with Colombia")
- Dates: `dos semanas` (not "two weeks ago") — `normalize_date` adds normalized metadata, source preserved
- Distinguishing features: `marca en la mejilla derecha`

UI display may add an English gloss (e.g., "hijo (son)") for non-Spanish-reading judges, but stored canonical value is always source-language. English glosses are display-time translations from a static mapping, never source of truth.

### Languages

- **Active demo path:** EN, ES, AR, FA
- **Storage capacity:** EN, ES, AR, FA, FR, UK (Python `SupportedLanguage` enum)
- **React `Language` type drift:** Currently out of sync with Python — UK/FR missing from `src/ui/web/src/lib/types.ts:9`. Polish-week reconcile, not blocking.

### Theme & design discipline

- High-contrast theme on both panels (Tent A primary blue + sans-serif + 24h timestamps; Tent B amber + monospace accent + 12h timestamps)
- Dark mode killed for accessibility (humanitarian-domain accessibility floor)
- Borders over shadows
- Warm paper surface, humanitarian teal primary
- 6px radius
- Noto Sans + mono
- 63 lines of CSS total — Tailwind utilities + design tokens, not styling soup

---

## Round 2 design decisions (locked April 28)

13 questions answered. Highlights:

1. Split-intake: one window, side-by-side panels, toggled by presenter
2. Records queue: show recently completed records with status (real, not decoration)
3. Navigation: thin icon rail (44px, always visible) — **NO command palette in user UI**
4. Presentation entry: keyboard shortcut only `⌘⇧P` (no URL param, no command palette)
5. Pacing: real interactions throughout. Phone-into-laptop-mic capture; presenter drives real Begin/Stop buttons; `⌘⇧P` only hides dev surfaces and seeds data
6. Sidebars (structlog + JSON tool calls): always visible during demo — credibility surface
7. After record completes: hybrid — stay on completed record with "Start new intake" CTA, OR auto-route to match view if `match_proposed` event fires
8. First load: empty intake panel, voice panel "Ready to begin"
9. Judge-cold: tour + seeded queue + clickable intake
10. DemoDock: keep, gate behind `?dev=1` / `⌘⇧D` — never visible by default
11. Bundle 1.5 scope: 6 sessions (Path B, full scope including queue and empty states)
12. All Round 1 locks remain
13. Custom: presenter affordances must be invisible to judges; recording crop must verify HUD invisible at 1080p; humanitarian-domain accessibility floor

### Three remaining Round 2 design questions

| # | Question | Status |
|---|---|---|
| 1 | Crisis state design | ✅ done, no work needed |
| 2 | Split view layout | ⚠️ S3 split view exists; clarify whether Round 2 redesign exists or S3 is canonical |
| 3 | Match view layout clip | ⚠️ real but minor — viewport cramp at <1400px, ~10 lines to fix in Bundle 1.5 |

---

## Schedule

**Build window:** April 23 → May 16 = 24 days. Today (April 29) is day 6 of the build window; 18 days remain at submission target.

| Phase | Calendar | Status |
|---|---|---|
| Bundle 1 (S1-S7) | April 23-29 | CLOSED (commit `a08b546`) |
| Bundle 1.5 (6 sessions, Round 2 nav refactor) | May 1-4 | Pending |
| Bundle 2 (Tent A snapshot + match smoke) | May 5-7 | Pending |
| Safety-net video recording | May 7-9 | Pending |
| Feature freeze | May 10 | Pending |
| Polish week | May 10-12 | Pending |
| Final video production | May 13-15 | Pending |
| Submit | May 16 | Pending |
| Buffer | May 17 | Pending |

---

## Key files & locations

### Production code

- **Pipeline:** `src/integration/pipeline/transcription_pipeline.py`
- **Crisis tool:** `src/integration/escalate_crisis_tool.py` (S6 new)
- **Extraction tool:** `src/integration/pipeline/extraction_tools.py`
- **Ollama adapter:** `src/integration/ollama_adapter.py` (already generic over tools, S6 finding)
- **Storage adapter:** `src/integration/storage_adapter.py`
- **Storage schemas:** `src/core/storage_schemas.py` (AuditEventType Literal, IntakeRecord)
- **Safety rules:** `src/core/safety_rules.py` (deterministic classifier, sole safety gate)
- **SSE bridge:** `src/ui/server/sse.py`
- **FastAPI app:** `src/ui/server/main.py` (lifespan warmup hook lives here)
- **Frontend hooks:** `src/ui/web/src/hooks/useEventStream.ts`, `src/ui/web/src/hooks/useMicCapture.ts` (S5 new)
- **Components:** `src/ui/web/src/components/IntakePanel.tsx`, `VoicePanel.tsx`, `StructlogSidebar.tsx`

### Documents

- **CLAUDE.md** — development guide for CC, type-strict discipline, prompt budgets
- **briefs/bundle-1-context.md** — Bundle 1 context (committed in `29d9cc9`)
- **HANDOFF.md** — this file
- **docs/ADR/001-…md** through **docs/ADR/005-…md** — architecture decision records
- **PROJECT_PLAN.md** — high-level plan

### Storage

- **Audit events:** `storage/audit_events.jsonl` (append-only)
- **Intake records:** `storage/intake_records.jsonl`

---

## Demo script v3 (locked April 28)

Saved at `/mnt/user-data/outputs/kin-demo-script-v3.md`. Three updates from v2:

1. Cold open compressed (-1s by trimming ping demonstration)
2. Beat 5 closing VO names `flag_minor` tool call
3. Queue rail glimpse (1-2s in Beat 5→6 transition, establishes Mohammed exists in queue before match fires)
4. Beat 7 expanded 10s→13s with "audits the path that fired it" auditability framing
5. Beat 8 trimmed 3s by removing "Still offline" callout (airplane icon delivers framing visually)

**Total runtime:** 2:19 target, 174 VO words, ≤2.0 wps sustainable.

**Load-bearing silences (do not fill in post):**
- 0:00–0:09 cold open
- 0:09–0:13 face-hold opening Segment 2
- 1:22–1:25 silent transition into Segment 6 (architectural pivot)
- 1:54–1:57 post-"One child. Found."

**Recording mode:** Chunked recording per segment, VO recorded separately, assembled in edit.

---

## QA history

| QA | After | Verdict | Findings |
|---|---|---|---|
| QA-1 | S4 + S4-fix | PASS | 9/11 criteria, 2 punted (font/color cosmetic); led to S4-fix (preserve view on reset, last-writer-wins) |
| QA-2 | S5 | PASS clean | First end-to-end real intake; minor flag fired correctly; source-language preservation held; "name field noise" was operator error (re-recorded same turn — extend path's last-writer-wins worked as designed) |
| QA-3 | S6-fix2 | PASS | Beat 7 Spanish crisis verified end-to-end with real audio: deterministic safety classifier fired on `quiero morir` substring match, escalate_crisis Gemma tool returned valid args, locale_aware_message rode the POST response, overlay rendered Gemma's body (not static fallback). Surfaced two polish-week items (diacritic normalization in safety_rules; SSE replay re-pinning intakeId after Reset) — both deferred to Bundle 1.5. |

---

## LLM-as-judge & demo coach passes

### Pass #1 (April 28, post-PRFAQ + initial demo script)

Three-judge panel: 8.3 (DeepMind ML) / 7.7 (Humanitarian) / 8.5 (Hackathon-feel) = 8.17 composite.

**Push-back pass corrected several recommendations:**
- ACCEPT: Pre-warm pipeline (highest leverage); name `flag_minor` in VO; recording crop verification; engineering rigor screenshot (use AST-layer-boundary-failure-on-deliberate-violation, not pytest dots)
- REJECT: Cutting Beat 6 transition (load-bearing); cutting Beat 8 (Anthropic API + multi-turn + caseworker positioning is credibility purchase for DeepMind judges)
- PARTIAL: False-positive crisis paragraph reframed as decision-support not validation promise; hardware paragraph reframed as confident quality-vs-hardware tradeoff with Gemma 4 270M as v0.5 path
- MISSED BY PANEL: Queue rail icon glimpse before Beat 6 to establish Mohammed exists in queue before match fires

**Pass #2 scheduled:** ~May 11 against revised script + Bundle 1.5 build
**Demo coach pass (Phase 5.7):** prompt undrafted; runs against v3 script before safety-net video

---

## Polish-week task list

Items accumulating; lives here as the canonical list:

1. React Language type drift reconcile (`src/ui/web/src/lib/types.ts:9`)
2. Three concurrent EventSource cleanup (App-level unfiltered hook unused in split mode) — may absorb into Bundle 1.5
3. AST-layer-boundary-violation screenshot for Devpost writeup
4. Hardware-tier paragraph (confident framing, Gemma 4 270M as v0.5 path)
5. False-positive crisis paragraph (decision-support, auditable structlog framing)
6. Recording crop verification at 1080p (HUD invisible)
7. LLM-as-judge pass #2 (~May 11, post-Bundle-1.5)
8. Demo coach pass on v3 script (Phase 5.7, separate Opus thread)
9. Match view viewport cramp at <1400px (~10 lines CSS, Bundle 1.5)
10. `mypy` not installed in `.venv` (CLAUDE.md mandates `mypy --strict`; pre-existing tooling gap from initial setup)
11. `tests/ui/server/test_sse.py` requires `KIN_DISABLE_WARMUP=1` (pre-push tier should set env var or fix fixture)
12. Verify `normalize_date` fires for relative dates ("dos semanas" captured but not normalized in QA-2)
13. Confirm spoken-language source (auto-detect vs hardcoded)
14. Verify Carlos record persisted despite "queued locally" count change observed in QA-2
15. Possibly v4 script revision based on QA-3 timing reality
16. Forward-note from S3: SimpleVoicePanel used in split mode; if demo wants full VoicePanel in split, post-Bundle-1 polish call
17. Extraction sanity-check on name field (low-confidence flag for noise outputs)
18. UK/FR `Language` type alignment between Python and React
19. Codebase stats artifact (`briefs/codebase-stats.md` if Mark wants longitudinal tracking)
20. Devpost per-prize "Why this wins" paragraphs
21. Multi-prize stacking — enter every category that remotely qualifies
22. Citation pass for all quantitative claims (PRFAQ Step 3A-2 work)
23. **(QA-3) Diacritic normalization in `safety_rules.classify`**: Whisper transcription of Spanish utterances can include accented vowels (e.g. `suicidió` instead of `suicidio`) that defeat substring keyword matching. Cleanest fix is `unicodedata.normalize('NFKD', text)` + diacritic strip before substring check. Same fix applies to all 6 implemented languages, but Spanish is the demo-bearing case.
24. **(QA-3) SSE replay re-pinning `intakeId` after Reset**: the `intake_created` reducer transition unconditionally sets `intakeId`, so an SSE reconnect (or fresh page load) over a non-empty audit log re-pins to the last record. Reset clears it, but the next replay restores it. Cleanest fix is to guard `intake_created` with `state.intakeId === null` so replay can't overwrite a manual clear. Touched naturally by Bundle 1.5's nav refactor.
25. **(S7) Last-writer-wins on extend path can clobber unrelated fields**: turn 3 extending an existing intake can have Gemma re-emit defaults for fields turn 3 didn't speak about (observed in extend smoke: turn 3 about distinguishing marks reset `is_minor` to false). Likely fix: filter `extract_intake_fields` output to only fields the model produced non-default values for, OR make the storage update path ignore explicit-null/empty assignments on extend. Smoke test acknowledges as known item.
26. **(S7) `unused phase/timerSec/timerRunning` props on `IntakePanelProps`**: vestigial layout-consistency props passed but unused inside `IntakePanel`. Pruning is mechanical; deferred from S7 to keep blast radius scoped.

---

## Bundle 1 close — what shipped, what remains

**S7 delivered:**
- Beat 6 merge animation: `kin-merge-pulse` keyframe (1100ms green box-shadow ring) + `prefers-reduced-motion` accessibility floor flattening all `kin-*` animations to instant. SSE-driven trigger in App.tsx — first `match_proposed` event arrival drives view → `match` and steps the phase machine through split → linking → merged. Idempotent via `matchAnimationFiredRef`. Existing `TransliterationMatch` component re-used; no new component needed.
- Extend smoke (3 turns Spanish, real Whisper + Gemma) + crisis smoke (single turn Spanish crisis keyword, real Whisper + Gemma + escalate_crisis). Locks the ADR-004 REV 3 contract end-to-end: `locale_aware_message` arrives non-empty on the tuple return.
- Dead `onBegin` prop indirection deleted across `VoicePanelProps` + `IntakePanelProps` + 4 call sites + 4 test fixtures. `runDemo()` itself preserved — DemoDock's "Start demo" button is the architecturally-committed offline fallback.
- QA-3 PASS verdict landed.

**Bundle 1 final state:**
- 14 commits (db200eb → a08b546)
- 12,714 total lines (3,781 prod / 4,676 tests / 4,176 TS-TSX / 81 CSS)
- 139 fast Python + 3 smokes + 35 Vitest + AST layer-boundary enforcement + TS strict + Vite 53-module 196KB build
- 4 ADRs + ADR-004 across REV 1/2/3 documenting the orchestration evolution

---

## Forward notes for Bundle 1.5

6 sessions per Round 2 design:

1. Rail nav (44px icon rail, always visible)
2. Voice panel state machine
3. Tool-calls sidebar production polish (Stripe-API-docs aesthetic)
4. Structlog sidebar polish + match toast + auto-route
5. Match view layout (Cross-session match under review) + viewport cramp fix
6. Queue view + coach-mark + `⌘⇧P` presentation mode + DemoDock gating + integration smoke

Three remaining Round 2 design questions need answers BEFORE Bundle 1.5 starts:
- Crisis state design (✅ done)
- Split view layout (clarify Round 2 vs S3 canonical)
- Match view layout clip (real but minor)

**Polish-week items naturally absorbed by Bundle 1.5 (item numbers reference list above):**
- #2 (three EventSource cleanup) — App-level state touched by nav refactor
- #9 (match view viewport cramp <1400px) — match view layout session
- #18 (UK/FR Language type alignment) — type cleanup pass
- #24 (SSE replay re-pinning intakeId) — App-level state touched by nav refactor
- #26 (vestigial IntakePanelProps) — prop hygiene during voice panel state-machine session

---

## Forward notes for Bundle 2

Tent A Mohammed pre-seed snapshot + match smoke (Carlos+scar ↔ Mohammed+scar via name + distinguishing-feature composite match).

This unblocks Beat 6 of the demo storyboard. Without Bundle 2, Beat 6 cannot record end-to-end.

---

## Critical reminders for future agents

1. **Plan-approve-execute is non-negotiable.** Never execute without an approved plan.
2. **Test budget hits floor first.** Headroom for genuine gaps, not pre-planned expansion.
3. **No `git push` without explicit instruction.** All commits local.
4. **No new dependencies without escalation.** Both Python and React.
5. **Source-language preservation is architectural commitment, not preference.** Don't translate to English on storage.
6. **`safety_rules.classify` is the sole safety gate.** Gemma is formatter on crisis path, never classifier.
7. **ADR-004 REV 2 is intentional.** Reversion criterion: harm we cannot detect, not architectural cleanness.
8. **The video IS the product.** For online Devpost hackathons, judges never run code. Demo script v3 is the artifact that determines outcome.
9. **Solo-build framing is a strength, not an apology.** "Built by one solo developer in 24 days with 12.7K lines and 1.24 test ratio" — flex it.
10. **Compaction is fine; restart is not.** When the conversation compacts, accumulated context preserves. Don't restart with a new agent unless absolutely necessary.

---

---

## Bundle 1 close marker

**Bundle 1 architecturally closed: April 29, 2026, post-S7 commit `a08b546`.**

The runtime spine — SSE pipeline, two-panel split view, mic capture, extend path, crisis branch with Gemma escalate_crisis tool, Beat 6 merge animation, integration smoke for both extend and crisis paths — is shipped. Demo-day infrastructure ready to record. Bundle 1.5 (Round 2 nav refactor) drafts next.

**End HANDOFF.**