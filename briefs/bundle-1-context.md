# Bundle 1 Context — SSE wiring + four UI affordances

**Window:** May 2-4, 2026
**Sessions:** ~6 (S1-S6, plan-approve-execute per session)
**Predecessor:** Phase 1 orchestration build (commits `9615bcd` → `bfa50e9`, certified May 1)

---

## Read order

1. **`/HANDOFF.md`** — project state, locked decisions, working discipline, file map. Required.
2. **This file** — Bundle 1 spec material (Part 2 REV 3 production audit + audit-event mapping).
3. **The Bundle 1 brief** — separate doc, defines the six sessions S1-S6 with cross-session decisions and pre-flight resolutions. Strategy thread drafts this; implementation agent receives it after planning gate.

---

## Bundle 1 goal

Replace setTimeout fakes in the React frontend with real SSE-driven event flow from the runtime pipeline. Build the four high-risk UI affordances flagged by strategy thread that Beat 5, 6, 7 of the v2 demo script depend on. Land in 6 sessions across May 2-4 so May 5-6 (Bundle 2) is free for Tent A snapshot work and May 7-9 (safety-net video window) opens with a recordable UI.

After Bundle 1 ships, the demo script's nine beats divide as:
- ✅ Beats 4 and 8 (real, no work needed)
- ✅ Beats 5, 6, 7 (Bundle 1 lands their UI)
- ⏳ Pre-seeded data and Tent A Mohammed match (Bundle 2)

---

## Current pipeline contract (what Bundle 1 consumes)

`src/integration/transcription_pipeline.py::ingest_audio()` is the entry point:

```python
async def ingest_audio(
    audio_path: Path,
    lang: str,
    source_device_id: str,
    *,
    whisper: _Transcriber,
    ollama: _OllamaPort,
    storage: StorageAdapter,
) -> IntakeRecord
```

Side effects:
- Persists IntakeRecord to `storage/intake_records.jsonl`
- Writes audit events to `storage/audit_events.jsonl` (append-only, single-writer)
- Optionally writes MatchLink rows to `storage/match_links.jsonl`
- Emits structlog events (separate stream, not persisted)

The SSE backend tails `audit_events.jsonl` and pushes events to the React frontend. That's the bridge Bundle 1 builds.

**Audit-event types** (Part 1 REV 4 enum, all 8 covered by tests):

| Event type | When emitted |
|---|---|
| `intake_created` | `storage.create_intake_record()` |
| `intake_paused` | `update_intake_record(status → paused_for_crisis)` |
| `crisis_detected` | same status transition (triple-emit) |
| `referral_issued` | same status transition (triple-emit) |
| `field_extracted` | `update_intake_record(field=value)` per field changed |
| `match_proposed` | `storage.create_match_link()` |
| `match_confirmed` | `update_match_link_status(proposed → confirmed)` |
| `match_rejected` | `update_match_link_status(proposed → rejected)` |

`minor_flagged` is a structlog event only, NOT a persisted audit event (Part 1 REV 4 enum constraint). Bundle 1 must surface it to the structlog sidebar via the structlog stream, not via SSE-from-audit-log.

---

# Part 2 REV 3 — Production Audit (verbatim, with light reformatting)

**Purpose:** Specify build approach and effort for the four high-risk UI affordances flagged by strategy thread. Output feeds Bundle 1 SSE-wiring brief with must-build UI items.

**Scope:** Four items only. NOT a complete production inventory. Existing affordances from Days 1-7 React work are out of scope and assumed stable.

**Items:**
- (a) Merge animation at 1:51-1:54
- (b) Two-device differentiation 1:22-1:48
- (c) Structlog sidebar real wiring throughout
- (d) JSON function-call sidebar at 1:00 and 2:03

---

## Summary table

| # | Item | Approach | Build effort | Day-14 must-build? | Fallback |
|---|---|---|---|---|---|
| a | Merge animation 1:51-1:54 | Clean fade-merge in React (CSS keyframes) | ~1 session | No — defer to final polish | Hard cut with 200ms cross-fade |
| b | Two-device differentiation | Simulated split-view, single React app, two themed panels | ~1.5-2 sessions + 0-0.5 for (b.1) | **YES** | Two same-themed panels with header labels |
| c | Structlog sidebar real wiring | Replace setTimeout with SSE-driven event stream | ~1-2 sessions | **YES** | Keep setTimeout fakes timed to recorded audio (brittle) |
| d | JSON function-call sidebar | Real Gemma tool-call output rendered live | ~0.5-1.5 sessions | **YES** (hello-world cleared GREEN Apr 28-29) | Pretty-printed static JSON synced to audio |

**Total effort:** ~5 sessions of affordance work + ~2 sessions of SSE plumbing = ~6-7 sessions across May 2-4.

**Note on (d):** The Apr 28 hello-world test + Apr 29 multilang sweep cleared GREEN across EN/AR/FA. The S3 ITEM B work (commit `cd82c3a`) wired Gemma 4 E2B tool-calling into `OllamaAdapter.tool_call()`. Real tool-call output is available via the pipeline; Bundle 1 (d) plumbs it into the sidebar. The "static JSON fallback" listed above is no longer needed — preserved for historical context.

**Prerequisites at Bundle 1 entry:**
- (b.1) IntakePanel state for transliteration handling: Day 11 prereq verification confirmed State 3 (no transliteration field exists). Must build in Bundle 1.
- (c) existing setTimeout sequencer structure: needs code inspection at S1 planning. Determines whether (c) is a 1-session swap or 2-session refactor.

---

## (a) Merge animation at 1:51-1:54

### Storyboard requirement

"Records fly toward center. Merge into single match card. 1-sec structlog flash showing fuzzy-match + transliteration-comparison firing. Match card pulses green. Arabic محمد at top, both transliterations linked beneath."

3-second window. Must read as deliberate climax, not janky DOM movement.

### Recommendation: clean fade-merge in React

CSS keyframes only. No animation library. Implementation:

- Two-panel container with both panels visible at 1:51
- Trigger merge: each panel gets `opacity: 0; transition: opacity 500ms` simultaneously
- Match card component fades in over the same 500ms with `transform: scale(0.95) → scale(1.0)` for subtle emergence
- Match card border: green pulse via `@keyframes` (border-color cycle, 2 cycles)
- Soft chime SFX synced to match card emergence

The "1-sec structlog flash" is part of (c), not a separate animation — just a sidebar log line that appears at 1:51.

### Build effort

~1 session. Pure frontend, no backend changes beyond `match_proposed` event firing (already in the pipeline).

### Day-14 must-build? No.

Beat 6 lands without animation polish via the fallback (hard cut + 200ms cross-fade). Defer to Bundle 1 S6 polish slot or May 10-12 polish window. Bundle 1's other work takes priority.

### Fallback

Hard cut from two-panel to match card at 1:51 with 200ms CSS cross-fade. Visually adequate. Wow lands less hard but doesn't break.

---

## (b) Two-device differentiation 1:22-1:48

### Storyboard requirement

Both panels on existing high-contrast theme. Differentiation via accent color (Tent A primary blue, Tent B amber), font family (sans on A, mono accent on B header chrome), timestamp format (24h on A, 12h on B), and header label. Body content area, contrast, readability identical. Decision rationale: dark mode would regress accessibility posture for low-light field conditions; visual differentiation must not compromise readability.

This is the precondition for Beat 6 working. If panels read as columns of one app, the "two tents, two reports, same child" framing breaks.

### Recommendation: simulated split-view

Single React app with two side-by-side panels, each with independent theme, fonts, timestamp formats, cursor styles. Both panels read from same SSE stream filtered by `source_device_id`.

**Honesty principle:** the underlying records are genuinely separate intakes with separate device IDs, separate audio sources, separate ingest paths. Only the visual presentation collapses them into one viewport. Data fabrication is zero; presentation is consolidated.

### Implementation components

| Component | Detail |
|---|---|
| Layout | Split-screen container, 50/50 horizontal. Two `IntakePanel` components. |
| Theme tokens | Two CSS variable sets: `theme-light` (white bg, dark text, sans-serif font stack) and `theme-dark` (dark bg, light text, monospace font stack). Applied via theme class on each panel. |
| Timestamp format | `IntakePanel` accepts a `timestampFormat` prop (`"24h"` / `"12h"`), uses Intl.DateTimeFormat per panel. |
| Cursor style | Per-panel CSS `cursor` property with different cursor images. Trivial. |
| Data routing | Each panel subscribes to SSE filtered by `source_device_id` (`tent_a` / `tent_b`). Backend SSE endpoint takes a query param or uses separate event channels. |

### Build effort

~1.5-2 sessions. Themed panel refactor (~0.5), SSE filtering (~0.5), timestamp formatting + cursor work (~0.25), split-screen layout integration (~0.5), test/polish (~0.25).

### Day-14 must-build? **YES.**

Beat 6 doesn't communicate without two-device differentiation.

### Fallback

Two side-by-side panels with same theme but distinct headers ("Tent A — Camp Office" / "Tent B — Field Station") and different timestamps. Communicates parallel intakes via labeling, not visual styling. Cost: the "two devices" wow becomes a "two columns" wow.

### Sub-item (b.1) — Worker-entry affordance for transliteration during 2B

**Confirmed at Day 11 prereq verification:** IntakePanel does NOT have a transliteration field (State 3). Must build.

**Working hypothesis (Part 3 Issue 2 → Possibility A):** `full_name_transliteration` is worker-entered, not pipeline-derived. During Beat 6 right panel, the Tent B worker enters "Mohamad" as the Latin transliteration during 2B audio.

**Build effort:** 0.25-0.5 sessions to add transliteration field + entry mechanism to IntakePanel.

**Storyboard implication:** v2 script should annotate "worker enters transliteration" visible in the UI during right-panel animation. Flag for v2 script revision.

**Fallback if not built:** pre-populate Tent B record with `full_name_transliteration: "Mohamad"` at session start. Less authentic — viewer doesn't see human entry.

---

## (c) Structlog sidebar real wiring throughout

### Storyboard requirement

Structlog sidebar runs across Beats 5, 6, 7. Currently exists as setTimeout fake. Needs to be wired to real event stream for credibility — anyone pausing the video will read what the sidebar shows.

### Audit-event-to-UI mapping (load-bearing for Bundle 1)

This is the contract between the SSE backend and the structlog sidebar. Every event below must render correctly when its source emission fires.

| Beat | Event source | Sidebar visual |
|---|---|---|
| 5 (0:50-1:22) | `intake_created` | "Session started · es · device tent_a" log line |
| 5 | `field_extracted` (per field) | One log line per field with field name + extracted value |
| 5 | structlog `minor_flagged` | Highlighted log line, amber background |
| 6 right panel | `intake_created` | "Session started · ar · device tent_b" |
| 6 right panel | `field_extracted` (per field) | One line per field |
| 6 merge | `match_proposed` | Highlighted log line, "match proposed: high confidence — source-script identity + age + relationship" |
| 7 | `intake_created` | "Session started · ar" |
| 7 | safety_rules keyword check | "keyword check: no match" line, brief red flash |
| 7 | safety_rules semantic check | "semantic check: match (path=embedding)" line |
| 7 | `crisis_detected` | Red-highlighted line |
| 7 | `referral_issued` | "referral: IFRC Family Links Network" line |
| 7 | `intake_paused` | "session paused: crisis flow" line |

**Two streams feed the sidebar:**

1. **Audit events** from `audit_events.jsonl` (SSE-tailed): `intake_created`, `field_extracted`, `match_proposed`, `match_confirmed`, `match_rejected`, `intake_paused`, `crisis_detected`, `referral_issued`.
2. **Structlog events** from in-process logging: `minor_flagged`, `crisis_path_taken`, `matching_trigger_fired`, `tool_call_invoked`, `tool_call_returned`, safety_rules check events.

Bundle 1 must plumb both. The cleanest path is likely a unified SSE endpoint that interleaves both streams in time order, but that's a Bundle 1 planning-gate decision.

**Note on Beat 7's "semantic check" line:** the v2 script shows a `semantic` crisis match path. The current `safety_rules` is keyword-only. `crisis_match_path = "semantic"` enum value is defined but unwritten until Day 8-9 future work. Bundle 1 must decide whether to:
- (a) Leave the semantic line as a sidebar fake (acceptable; matches the current keyword-only reality)
- (b) Stub a semantic-style log emission in `safety_rules` for the demo path
- (c) Defer to a future bundle

This is a Bundle 1 Boss-mode question.

### Implementation path

**Prerequisite verification at S1 planning:** how is the existing setTimeout sequencer structured?
- If it's a `<StructlogSidebar events={...} />` component that takes events and renders them: swap the events source from setTimeout-driven to SSE-driven. ~1 session.
- If animation steps are hardcoded in the sequencer: refactor needed. ~2 sessions.

### Build effort

1-2 sessions depending on existing structure.

### Day-14 must-build? **YES.**

The structlog sidebar is the demo's credibility surface. Anyone — judges, viewers, fellow developers — who pauses the video will read it. setTimeout fakes that don't match what's actually happening will read as dishonest on close inspection.

### Fallback

Keep setTimeout sequencer with timing manually matched to recorded audio. Brittle: any audio re-record requires re-tuning timing. Acceptable only as Day-14 safety-net stopgap with real wiring committed for final.

---

## (d) JSON function-call sidebar at 1:00 and 2:03

### Storyboard requirement

Two specific moments:
- 1:00 (Beat 5): `{"name": "extract_intake_fields", "input": {"full_name": "Carlos", "relationship": "hijo"}}` rendered in sidebar
- 1:03 (Beat 5): `{"name": "extract_intake_fields", "input": {"full_name": "Carlos", "relationship": "hijo", "age": 8}}` (with minor_flagged amber)
- 2:03 (Beat 7): `escalate_crisis(language=ar, match_path=semantic)` rendered

Storyboard framing: "Native Gemma 4 tool calling visibly distinguishable from generic agent framing." The Omar-lens beat depends on this being real, not theatrical.

### Recommendation: real Gemma tool-call output

**Status (post-Phase 1):** Gemma 4 E2B tool-calling is wired in at `OllamaAdapter.tool_call()`. Apr 28 hello-world + Apr 29 multilang sweep both GREEN. S3 ITEM B (commit `cd82c3a`) committed the implementation. Real tool-call output is available via the pipeline.

Bundle 1 plumbs `tool_call_invoked` and `tool_call_returned` structlog events into the SSE stream and renders them with syntax highlighting in the sidebar.

### Note on Beat 7 `escalate_crisis(...)` rendering

`escalate_crisis` is NOT a real Gemma tool call in the current pipeline — the crisis path is keyword-driven via `safety_rules.classify`, not tool-driven. Bundle 1 must decide whether to:
- (a) Render a synthetic `escalate_crisis` JSON entry in the sidebar as a UI affordance, clearly tied to the `crisis_detected` audit event
- (b) Add a Gemma tool-call wrapper around the crisis-path decision (architectural change, scope creep)
- (c) Replace the storyboard text with what's actually happening (e.g. rendering the safety_rules classification result)

This is a Bundle 1 Boss-mode question. Recommended default: (a). The Omar-lens beat is structurally about "tool-calling visible in the sidebar"; rendering a synthetic-but-truthful tool entry tied to the crisis event preserves that semantic without architectural change.

### Build effort

~0.5-1 session. Plumb structlog tool-call events into SSE, render with syntax highlighting, gate on Beat-5 and Beat-7 timing.

### Day-14 must-build? **YES.**

(d) is the demo's strongest technical signal. Real tool-call output is available; not surfacing it loses the differentiation.

### Fallback

Pretty-printed static JSON via hardcoded sidebar entries timed to audio. Visually identical for laypeople. Technical judges who pause see static text and ding the demo. Acceptable for safety-net only.

---

## What this audit did NOT cover

- Affordances built and stable from Days 1-7: React app shell, audio waveform, field-population animations within a single panel, completeness meter, color-coded safety beats (amber/red/green), 42-min baseline label, "Minor detected" ambient label, end card. All assumed working at Bundle 1 entry.
- SSE event taxonomy details (Bundle 1 S1 plan owns this).
- Backend storage_adapter implementation (DONE in Phase 1).
- Video production pipeline tooling (DaVinci/Audacity setup).
- Recording-day setup (lighting, microphone, screen capture settings).

If any of these turn out to be unstable on inspection at Bundle 1 entry, surface for separate audit.

---

# Bundle 1 provisional session breakdown

To be refined at planning gate. Mark approves at planning gate before any session executes.

**S1: SSE backend.**
FastAPI endpoint streaming audit_events.jsonl tail + in-process structlog stream to React. Tail-following file watcher. Event filtering by `source_device_id` query param. Tests: connection setup, event delivery, reconnect behavior, audit-event filtering.

**S2: SSE frontend consumer.**
React EventSource hook, replaces setTimeout fakes. Wires audit_event + structlog stream to React state. Connection lifecycle state machine. Tests: hook behavior, state transitions on event arrival, cleanup on unmount.

**S3: Affordance (b) two-device differentiation.**
Two-pane split view, themed panels (light/dark + sans-serif/monospace + 24h/12h), per-panel SSE filter by `source_device_id`. Tests: theme rendering, panel filtering, layout integrity.

**S4: Affordance (b.1) transliteration entry + (c) structlog sidebar wiring.**
IntakePanel transliteration field (worker-entered). Structlog sidebar reads from real SSE stream per the audit-event-to-UI mapping table. Tests: field interaction, sidebar rendering against live event stream.

**S5: Affordance (d) JSON function-call sidebar.**
Plumb `tool_call_invoked` / `tool_call_returned` structlog events into SSE. Render with syntax highlighting at Beat 5 + Beat 7 moments. Resolve Beat 7 `escalate_crisis` rendering decision per Boss-mode question.

**S6: Affordance (a) merge animation + integration smoke.**
Beat 6 merge animation polish (CSS keyframes). End-to-end smoke test: real audio → ingest_audio → SSE stream → React render. Equivalent of Phase 1 S6 smoke gate. Mark records a test pass-through to verify visual timing.

---

# Boss-mode questions for Bundle 1 planning gate

These surface at Bundle 1 S1 planning. The strategy thread or Mark resolves before any session executes.

1. **SSE protocol choice:** raw FastAPI StreamingResponse, sse-starlette dependency, or asyncio-based generator? Recommendation depends on existing FastAPI version and dependency budget.
2. **Frontend state management:** plain useReducer, Zustand, or other? Existing React app's pattern dictates.
3. **Structlog → SSE bridge:** in-process structlog events get added to the same SSE stream as audit events, or served as a separate stream? Affects the sidebar's "interleaved" visual.
4. **Reconnection strategy:** auto-reconnect with backoff, or manual reconnect? Demo needs deterministic behavior.
5. **Beat 5 progressive-fill mechanism:** three sequential audio files (per Part 3 Issue 1) or SSE-side staggered rendering? ADR-004 deferred this; Bundle 1 must resolve.
6. **Beat 7 `escalate_crisis` rendering:** synthetic-but-truthful tool entry tied to crisis_detected (recommended), or Gemma tool-call wrapper, or storyboard rewrite?
7. **Beat 7 "semantic check" log line:** sidebar fake accepting current keyword-only reality, stubbed semantic emission, or defer?

---

# Out of scope for Bundle 1

- Tent A Mohammed snapshot generation (Bundle 2, May 5-6, after Fiverr Arabic audio arrives)
- Real ICRC / REFUNITE API integration (post-submission)
- Audio fixture swap from TTS to real Spanish (Bundle 2 or Mark self-recording, async)
- Beat 4 (`ollama list`) — already real, no work
- Beat 8 (Claude Code IDE) — already real, no work
- Real semantic crisis detection (Day 8-9 saga, deferred)
- Production-scale matching index (current linear scan acceptable for ≤10 records)
- Concurrent storage writes
- git push

---

# Working discipline (mandatory)

Read `/HANDOFF.md` § "Working discipline" — same plan-approve-execute pattern as Phase 1, same test budget caps, same one-commit-per-session, same no-git-push.

For Bundle 1 specifically:

- Every session returns a plan first; Mark approves before execution
- Pre-flight Boss-mode questions surface BEFORE writing code
- Test budget caps named per session at planning gate
- Each session ends with one commit prefixed `bundle1-Sn:`
- Layer boundary test green after every session
- All 118 fast tests + 1 smoke test still green after every session

---

**End of Bundle 1 context.**

Strategy thread drafts the actual Bundle 1 brief separately. This file is the spec material the brief plans against.
