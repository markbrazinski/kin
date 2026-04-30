# Round 2 Design Reference — Bundle 1.5 Session Mapping

**Generated:** Bundle 1.5 S0 (`bundle1-5-S0: design reference inventory`)
**Source:** `design_reference/round-2/*.jsx` (13 files)
**Purpose:** Map each Round 2 prototype JSX file to the Bundle 1.5 session that will adapt it.

---

## Mapping table

| File | Component name(s) | Adaptation notes (from inline comments) | Likely Bundle 1.5 session |
|---|---|---|---|
| `nav-rail.jsx` | `NavRail` | 44px width locked. Active state = bg-card + 2px primary left accent + ink text. **Two routes only: 'intake' and 'queue'** — explicitly forbids adding settings/profile/help icons (dilutes bimodal capture-vs-review story). Wordmark + sync-status dot at bottom (heartbeat-synced). aria-label per button + aria-current="page" on active. | **S1** (rail nav + EventSource cleanup) |
| `nav-app.jsx` | Top-level shell (Round 2 canonical) | Layout grid: `[44px nav-rail][main flex-1 min-w-0 overflow-y-auto][320px structlog][320px tool-calls]`. `min-w-0` on main is REQUIRED. Routes = `'intake' \| 'queue'`; **match view is a sub-state of intake** (`route === 'intake' && matchView === true`), not a separate route. Voice state machine: `ready → awaiting → recording → transcribing → extracting → done` (six phases, collapse rejected). Begin = `Button size="lg"` (48px) primary; Stop = destructive-secondary (red text + red border, white bg, NEVER filled red — reserved for crisis). Both sidebars always visible (320px each). Split-view: `splitMode` boolean toggled by presenter; per-panel device chrome with hairline accent (`oklch(0.92 0.02 75)` warm for Tent A, `oklch(0.92 0.015 220)` cool for Tent B — NOT primary color). Single shared structlog + tool-calls; events get `[A]`/`[B]` mono prefix. | **shared — S1 shell, S2 voice phases, S5 split, S7 shortcuts** |
| `app.jsx` | Round 1 shell (kept for reference only) | Round 1 single-screen prototype. CC implements against `nav-app.jsx`, not this. Documents original demo sequencer (Beat 1–5 narration timing), keyboard shortcut map, reducer-based intake state shape (source of truth even in Round 2). Reducer action names are integration contract: `BEGIN`, `STOP`, `TRANSCRIBED`, `EXTRACTED`, `MINOR_DETECTED`, `CRISIS_FIRE`, `CRISIS_DISMISS`, `MATCH_FOUND`, `RESET`. **DO NOT MERGE into nav-app.jsx** — kept parallel for QA regression. | **shared — reference only, no session adapts directly** |
| `primitives.jsx` | `Button`, `Chip`, `SectionHeader`, `Field`, `CompletenessMeter`, `Waveform`, `Divider` | Tailwind tokens (paper, card, hair, line, ink, muted, subtle, primary, primary-soft, amber, amber-soft, red, red-soft, green, green-soft) + radii (`rounded-kin`=6px, `rounded-kin-lg`=8px). **Port to `tailwind.config.ts` as named tokens** — do NOT inline as arbitrary values. Disabled = structural (border-line + text-muted + cursor-not-allowed), NEVER opacity. Chip never uses color alone (icon + text + tone; five tones: neutral/primary/amber/red/green). Button heights: sm=36, md=40, lg=48 (lg reserved for Begin/Stop). Waveform state machine: `idle \| recording \| processing \| playback`; animation-delay stagger `(i % 8) * 70ms`. Field empty state = `—` (intentional, stays visible). CompletenessMeter shows segment count, NEVER percentage (no confidence numbers in front of workers). | **shared — referenced across multiple sessions** |
| `icons.jsx` | `Icon` wrapper + named icon components | Inline Lucide-style, 1.75px stroke (intentional — between Lucide default 2 and Phosphor-thin). **Replace with lucide-react imports if already a dep**; otherwise port as-is. 1:1 name map provided in header (IconMic→Mic, IconShield→Shield, IconList→List, etc.). `aria-hidden="true"` on every icon — preserve. Icons in KIN are ALWAYS paired with text or have aria-label on parent button. | **shared — referenced across multiple sessions** |
| `tool-calls.jsx` | `ToolCallsSidebar`, `JsonValue`, `JsonObject` | Tool-calls and structlog are SEPARATE sidebars (resisted merge during Round 2 review). Two-state row pattern: call appears as `started` (gray, name only), resolves to full args+result with one-shot highlight pulse. JSON: 2-space indent, mono, `text-[11px]`, `bg-paper` on args/result blocks. **Explicitly forbids syntax highlighting** ("plain mono reads more 'API debugger' than 'fancy IDE'"). Status colors on left rule: gray (started) / green (ok) / red (error) — red errors NEVER silently dropped. | **S3** (tool-calls sidebar polish) |
| `structlog.jsx` | `StructlogHeartbeat`, `StructlogRow` | "Stripe API docs" typographic credibility aesthetic. Mono font for keys/values, no chrome (no card borders), status via 1px LEFT BORDER per row (not bg fill, not icon). Heartbeat: `idle`=2s pulse / `busy`=0.5s pulse / `down`=solid amber. Amber-on-disconnect critical (offline-first trust story). Row schema: `{ ts, level, msg, kv? }`; `kv` rendered as inline `key=value` pairs in muted color. **Future: rows gain `origin: 'A' \| 'B'` for split view** — don't refactor row component until split lands. | **S4** (structlog polish + match toast) — and S5 will add `origin` field |
| `record-card.jsx` | `RecordCard`, `TransliterationVariants`, `PhotoPlaceholder` | Guardian & Protection sub-section auto-expands when `minor === true` with amber-soft tint (load-bearing: glance-shows minor needs CP routing). Minor state communicated in THREE places (amber strip above card, sub-section tint, top-bar pill — triple redundancy intentional). `TransliterationVariants` only renders when `record.nameVariants` populated. `PhotoPlaceholder` is intentional stub ("Photo intake not yet implemented"). RTL handling: `nameNativeRtl` and `lastSeenLocationRtl` flip just those substrings; aid-worker chrome stays LTR (locked locale-split pattern). `disabled` prop uses opacity-50 + pointer-events-none — the ONE place opacity-as-state is allowed (carve-out for paused-during-crisis). | **S5** (match view layout — record cards side-by-side) |
| `record-readonly.jsx` | `RecordCardReadOnlyBanner` | Wraps `RecordCard` with banner; **do NOT fork RecordCard for read-only** — pass `disabled` and render banner above. Banner uses amber-soft tone (advisory, not error). Copy: "Read-only — reopen for editing." Reopen action triggers audit log entry (out of scope this build, button is placeholder). | **S7** (queue view → click-row opens read-only intake) |
| `queue-view.jsx` | `QueueView` (+ seeded data) | Schema: `{ id, name, age, sex, lastSeen, status, minor, language, ts }`; status enum `'open' \| 'matched' \| 'closed' \| 'crisis'`. Filters: All / Open / Matched / Crisis (Crisis filter shows records where flag was raised even if since-resolved — operations-review surface). Row click → opens record in Intake panel as **read-only** (`record-readonly.jsx`). Visual: hairline rows, no zebra, status as Chip on right, language muted. Density intentional (scan-many-quickly). Minor flag = Shield icon + amber tone (consistent with record-card triple-redundancy). | **S7** (queue view) |
| `crisis-and-translit.jsx` | `CrisisReferralCard`, `TransliterationMatch`, `MiniRecord`, `CRISIS_COPY` | **`CrisisReferralCard`: Round 2 verdict CANONICAL — do not redesign.** Only place `shadow-elevated` is used in entire system. Red as icon/text/thin-rule only, never filled bg (red-soft chip in header is max red surface). Two dismissal buttons explicitly "De-escalated — continue intake" and "Referral provided" — both LOGGED separately, no generic Close. `CRISIS_COPY` (en/es/ar/fa) is canonical localized copy with `dir`/`title`/`body`/`hotline`/`play`. Card positioned `fixed left-1/2 top-[140px]`, rises via `kin-rise`, does NOT modal-block (record card behind dims to opacity-50, stays mounted). **`TransliterationMatch`: phase machine `'split' → 'linking' → 'merged'`**, `MiniRecord` tone prop (warm/cool) for Intake A vs B differentiation in match view (oklch warm-neutral and cool-neutral PAPER tints, NOT primary color). **Viewport fix: change `grid-cols-2 md:grid-cols-3` → `grid-cols-2 xl:grid-cols-3`** for <1400px viewports — fold into match-view session. | **S5 — primary** (transliteration match, viewport fix); **S6 may modify** if locale separation requires changes to `CRISIS_COPY` consumption (but `<CrisisReferralCard>` itself is locked from QA-3 — reference-only adaptation) |
| `presentation-mode.jsx` | `usePresentationMode`, `PresenterHUD`, `PRESENTATION_INITIAL_QUEUE_IDS` | Intentionally thin. Three responsibilities only: (1) hide dev surfaces (DemoDock, `data-dev="true"` elements), (2) seed required demo data (Mohammed snapshot for Beat 6 match-fire — `PRESENTATION_INITIAL_QUEUE_IDS = [89]`), (3) optional presenter HUD below 1080p safe-area. **Activated by ⌘⇧P OR `?present=1` query param** (both produce identical state). Coach-mark auto-dismissed on activate (presentation-mode.jsx clears `kin.coachmark.v1.dismissed` localStorage key). **Explicitly forbids demo-step automation** ("real audio drives real pipeline"). Exit: Esc or ⌘⇧P toggle. | **S7** (presentation mode + DemoDock gating) |
| `coach-mark.jsx` | `useCoachMark`, `CoachMark` | localStorage key `kin.coachmark.v1.dismissed` (don't change without migration). Auto-cleared when presentation mode activates (handled by `presentation-mode.jsx` — don't double-clear, will race). Copy max 2 short sentences per panel. Anchored to nav-rail (left side). | **S7** (coach mark) |

---

## Component count

| Session | JSX files mapped (primary) | Shared files referenced |
|---|---|---|
| S1 (rail nav) | `nav-rail.jsx` | `nav-app.jsx`, `primitives.jsx`, `icons.jsx` |
| S2 (voice state machine) | — (logic embedded in `nav-app.jsx` voice panel) | `nav-app.jsx`, `primitives.jsx` (Waveform, Button) |
| S3 (tool-calls sidebar) | `tool-calls.jsx` | `primitives.jsx`, `icons.jsx` |
| S4 (structlog + match toast) | `structlog.jsx` | `primitives.jsx`, `icons.jsx` |
| S5 (match view + split) | `crisis-and-translit.jsx` (TransliterationMatch + viewport fix), `record-card.jsx` | `nav-app.jsx` (split logic), `structlog.jsx` (origin tags), `primitives.jsx` |
| S6 (worker/speaker language) | — (refactor existing i18n; `crisis-and-translit.jsx` reference-only — `<CrisisReferralCard>` locked from QA-3) | `crisis-and-translit.jsx` (CRISIS_COPY reference) |
| S7 (queue + presentation + DemoDock) | `queue-view.jsx`, `record-readonly.jsx`, `presentation-mode.jsx`, `coach-mark.jsx` | `nav-app.jsx` (shortcuts), `record-card.jsx` (read-only wrapper), `primitives.jsx`, `icons.jsx` |

---

## Conflicts between Bundle 1.5 brief and design reference

These are planning-gate questions for the relevant session brief, NOT for S0 to resolve. Listed for visibility before S1 starts.

### Conflict 1 — Rail icon count (S1)

- **Brief:** "Five icons: Intake (active), Queue, Match, Settings, Help."
- **Design reference (`nav-rail.jsx`):** "Two routes only: 'intake' (mic icon) and 'queue' (list icon). Do NOT add settings/profile/etc. icons here — Settings lives elsewhere (overflow on top bar). Adding rail items dilutes the bimodal (capture vs. review) story."
- **Design reference (`nav-app.jsx`):** "Routes: 'intake' \| 'queue'. Match view is a sub-state of intake (route === 'intake' && matchView === true), not a separate route."
- **Resolution path:** Surface at S1 planning gate. Design ref appears stronger (later, locks rationale). If we adopt design ref's 2-icon rail, brief's S1 test #1 ("rail renders five icons with correct labels") drops to 2 icons; S7 may need to relocate Settings/Help to the top bar overflow.

### Conflict 2 — Tool-calls syntax highlighting (S3)

- **Brief:** "Args block: collapsible JSON with syntax highlighting (use prism-react-renderer or hand-rolled)" + pre-flight question "Is `prism-react-renderer` reasonable for syntax highlighting, or hand-roll with simple regex? Hand-roll is fine for JSON only — no new deps."
- **Design reference (`tool-calls.jsx`):** "Don't add syntax highlighting — plain mono reads more 'API debugger' than 'fancy IDE.'" (The reference does color-tag types via inline classes — strings green, numbers/booleans primary blue, keys muted blue — which is closer to "lightweight type-coloring" than "syntax highlighting.")
- **Resolution path:** Surface at S3 planning gate. Design ref's type-coloring is implemented inline without a library; brief's "hand-rolled" option may map to the same outcome. Likely no real conflict once "syntax highlighting" is disambiguated from "type-coloring of JSON values."

### Conflict 3 — Voice state machine phases (S2)

- **Brief:** "States: `idle` → `recording` → `processing` → `idle`" (3 active phases).
- **Design reference (`nav-app.jsx`):** "VOICE STATE MACHINE — DO NOT CHANGE: ready → awaiting → recording → transcribing → extracting → done. These six phases each map to a structlog line and a Waveform visual state. Collapsing them was tried and rejected — judges/reviewers want to see each phase as evidence the system is doing real work."
- **Resolution path:** Surface at S2 planning gate. Brief's `processing` is design ref's `transcribing → extracting`; brief's `idle` is design ref's `ready` and `done`. Design ref's 6-phase version is richer and ties to existing SSE event names — likely the right adoption. Brief's test #1 ("state transitions follow idle → recording → processing → idle") expands to test the 6-phase walk.

### Conflict 4 — Presentation mode trigger (S7)

- **Brief:** "Keyboard shortcut. ⌘⇧P. ESC exits presentation mode."
- **Design reference (`presentation-mode.jsx`):** "Activated by ⌘⇧P or `?present=1` query param. Both should produce identical state — the URL param exists so a presenter can deep-link into a clean state from a fresh tab."
- **Resolution path:** Surface at S7 planning gate. Adding `?present=1` is small and useful (deep-link from clean tab); brief is silent rather than excluding it. Likely add both, document the URL param in DemoDock gating logic.

### Conflict 5 — DemoDock toggle keyboard shortcut (S7)

- **Brief:** "DemoDock visible only when `?dev=1` URL param OR keyboard `⌘⇧D` toggle."
- **Design reference (`nav-app.jsx`):** Lists `⌘B` (toggle structlog rail, dev only), `⌘⇧B` (toggle tool-calls rail, dev only), and `?dev=1` for DemoDock — but NO `⌘⇧D` shortcut documented for DemoDock toggle.
- **Resolution path:** Surface at S7 planning gate. `⌘⇧D` is brief-only and doesn't conflict with anything in design ref; design ref's `⌘B`/`⌘⇧B` rail-toggles are additional dev affordances. Likely adopt all three (`⌘⇧D` for DemoDock, `⌘B`/`⌘⇧B` for sidebars) — they don't collide.

### Note on Mark's prior (verified)

Mark's prior on `crisis-and-translit.jsx`: "primarily S5 (transliteration match, Beat 6 wow moment), with crisis card content as reference-only since v1's `<CrisisReferralCard>` is locked from QA-3."

**Verified.** The file's own header reads: "CrisisReferralCard (Round 2 verdict: CANONICAL — do not redesign)" — explicitly aligned with QA-3 lock. The transliteration-match component carries the active S5 work (phase machine + viewport fix). S6 may need to re-thread `lang` prop into `CrisisReferralCard` consumption if worker/speaker locale split changes how the component is invoked, but the component itself stays as-is. Mapped as "S5 — primary; S6 may modify if locale separation requires it."

---

**End MAPPING.md.**
