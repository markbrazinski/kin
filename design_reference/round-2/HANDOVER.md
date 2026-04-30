# KIN — Round 2 Prototype Handover (for CC / Bundle 1.5 implementation)

> Generated for handover. Drop this whole folder into `design-reference/round-2/`.
> Each component has an inline ADAPTATION NOTES block at the top of the file —
> read those first, they call out deliberate decisions that should not be
> re-litigated during implementation.

---

## Read order (recommended)

1. **`icons.jsx`** — visual vocabulary
2. **`primitives.jsx`** — Button / Chip / Field / Waveform tokens & rules
3. **`record-card.jsx`** — the central form, all field-UX principles in one place
4. **`crisis-and-translit.jsx`** — Crisis is canonical (locked), Match has a viewport fix to fold into Bundle 1.5
5. **`structlog.jsx`** + **`tool-calls.jsx`** — the credibility surfaces
6. **`nav-rail.jsx`** + **`nav-app.jsx`** — the canonical Round 2 shell
7. **`queue-view.jsx`**, **`record-readonly.jsx`**, **`coach-mark.jsx`** — supporting routes/states
8. **`presentation-mode.jsx`** — hackathon demo driver only
9. **`app.jsx`** — Round 1 shell, reference only

---

## Tailwind tokens to port

These are defined inline in the prototype HTML — port them to `tailwind.config.ts`
as named tokens (do not inline as arbitrary values):

```js
colors: {
  paper: 'oklch(0.985 0.002 75)',     // app background, warm off-white
  card:  'oklch(0.995 0.001 75)',     // card surface
  hair:  'oklch(0.93  0.003 75)',     // hairline divider
  line:  'oklch(0.88  0.005 75)',     // border / disabled stroke
  ink:   'oklch(0.20  0.01  280)',    // primary text
  muted: 'oklch(0.50  0.01  280)',    // secondary text
  subtle:'oklch(0.65  0.01  280)',    // tertiary text
  primary:      'oklch(0.50 0.13 235)',
  'primary-soft': 'oklch(0.94 0.04 235)',
  amber:        'oklch(0.65 0.13 75)',
  'amber-soft': 'oklch(0.94 0.06 75)',
  red:          'oklch(0.55 0.18 25)',
  'red-soft':   'oklch(0.94 0.06 25)',
  green:        'oklch(0.55 0.13 150)',
  'green-soft': 'oklch(0.94 0.05 150)',
},
borderRadius: {
  kin: '6px',
  'kin-lg': '8px',
},
boxShadow: {
  // Reserved for CrisisReferralCard ONLY. Do not use elsewhere.
  elevated: '0 12px 32px -12px oklch(0.20 0.02 280 / 0.18), 0 2px 6px -2px oklch(0.20 0.02 280 / 0.10)',
},
```

---

## Locked design decisions (do not re-litigate)

1. **Disabled = structural, never opacity** (border-line + text-muted).
   One carve-out: `RecordCard` dimmed behind crisis layer uses opacity-50.
2. **Status communicated by 1px left border in sidebars**, never by row bg fill.
3. **`shadow-elevated` reserved for `CrisisReferralCard` only.**
4. **Red is icon + text + thin accent**, never a filled surface.
5. **Crisis card has two named dismissals** ("De-escalated" / "Referral provided"),
   each logged separately. No generic Close.
6. **Minor-detected uses amber, communicated in 3 places** (top strip,
   sub-section highlight, status pill). Triple-redundancy intentional.
7. **CompletenessMeter shows segment count, never %**.
8. **Empty fields render "—" and stay visible** so the worker sees the form shape.
9. **Localized RTL is per-substring** (name, location), never whole-card flip.
10. **Structlog and tool-calls are separate sidebars** — resisted merge in Round 2.
11. **Begin/Stop are size="lg" (48px)** — most-pressed buttons in the demo.
12. **Nav rail is 44px and does not collapse.**
13. **No emoji, no illustrations, no marketing copy** anywhere in-app.

---

## Bundle 1.5 in-scope changes (small)

- **Match-view viewport fix:** in `crisis-and-translit.jsx` `TransliterationMatch`,
  change merged-card grid from `grid-cols-2 md:grid-cols-3` →
  `grid-cols-2 xl:grid-cols-3` so 1366×768 laptops don't cramp columns.
- **Sidebar collapse <1400px:** double-stacked right rail (structlog over
  tool-calls) collapses to TABS on a single rail. Don't hide either.

## Bundle 1.5 in-scope changes (larger — split-view redesign)

S3 structural is necessary but not sufficient for Beat 6. Layer on:

1. **Per-panel device chrome** — thin header strip per IntakePanel showing
   tent/site label, device id, subtle device-specific accent (Tent A: warm
   neutral hairline `oklch(0.92 0.02 75)`, Tent B: cool neutral hairline
   `oklch(0.92 0.015 220)`). NOT primary color — stays in the warm-paper system.
2. **Independent state, visibly** — each panel runs its own phase + timer +
   language. Asymmetric states (A done while B mid-extracting) are the proof.
3. **Shared structlog tags events with origin** — `[A]` / `[B]` mono prefix.
   Single sidebar, two interleaved streams. Same for tool-calls.

---

## `icons.jsx`

_Inline Lucide-style icon set. REPLACE with lucide-react in production._

```jsx
/* ============================================================================
 * KIN — icons.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC (Bundle 1.5 implementation):
 *   • This file exists ONLY because the prototype runs from a single HTML
 *     artifact with no bundler. In the real repo, REPLACE these with your
 *     existing icon imports (lucide-react if that's what the codebase uses).
 *   • Icon names map 1:1 to Lucide: IconMic→Mic, IconShield→Shield,
 *     IconAlert→TriangleAlert, IconCheck→Check, IconLock→Lock,
 *     IconLanguages→Languages, IconList→List, IconUser→User,
 *     IconMapPin→MapPin, IconCamera→Camera, IconLink→Link,
 *     IconSparkle→Sparkles, IconTerminal→Terminal, IconClock→Clock,
 *     IconArrowRight→ArrowRight, IconChevron→ChevronDown, IconRotate→RotateCw
 *   • Stroke width 1.75px is INTENTIONAL — gives a humanitarian-tool weight
 *     between Lucide's default (2) and Phosphor-thin. Don't drop to 1.5.
 *   • The base <Icon> wrapper sets `aria-hidden` — preserve this. Icons in
 *     KIN are ALWAYS paired with text or have an aria-label on the parent
 *     button; they never carry meaning alone.
 * ============================================================================
 * Inline Lucide-style icons — line, 1.75px stroke, original paths.
 * Kept in one file so the artifact has no external icon package dependency. */
const Icon = ({ children, size = 18, className = "", strokeWidth = 1.75, ...rest }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...rest}
  >
    {children}
  </svg>
);

const IconMic       = (p) => <Icon {...p}><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M8 21h8"/></Icon>;
const IconPlay      = (p) => <Icon {...p}><path d="M6 4l14 8-14 8V4z"/></Icon>;
const IconPause     = (p) => <Icon {...p}><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></Icon>;
const IconShield    = (p) => <Icon {...p}><path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z"/></Icon>;
const IconLock      = (p) => <Icon {...p}><rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></Icon>;
const IconCloudOff  = (p) => <Icon {...p}><path d="M3 3l18 18"/><path d="M7 18h10a4 4 0 0 0 .7-7.95A6 6 0 0 0 6.3 8.3"/></Icon>;
const IconCheck     = (p) => <Icon {...p}><path d="M5 12l4 4L19 6"/></Icon>;
const IconAlert     = (p) => <Icon {...p}><path d="M12 3 2 20h20L12 3z"/><path d="M12 10v5"/><circle cx="12" cy="18" r=".5" fill="currentColor"/></Icon>;
const IconInfo      = (p) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><circle cx="12" cy="8" r=".5" fill="currentColor"/></Icon>;
const IconArrowRight= (p) => <Icon {...p}><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></Icon>;
const IconChevron   = (p) => <Icon {...p}><path d="M6 9l6 6 6-6"/></Icon>;
const IconLanguages = (p) => <Icon {...p}><path d="M3 5h10"/><path d="M8 3v2"/><path d="M5 9c.5 3 2.5 5 5 6"/><path d="M11 9c-.5 3-2.5 5-5 6"/><path d="M13 21l5-10 5 10"/><path d="M15 17h6"/></Icon>;
const IconUser      = (p) => <Icon {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6"/></Icon>;
const IconMapPin    = (p) => <Icon {...p}><path d="M12 21s-7-7.5-7-12a7 7 0 1 1 14 0c0 4.5-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/></Icon>;
const IconCamera    = (p) => <Icon {...p}><path d="M4 7h3l2-2h6l2 2h3v12H4z"/><circle cx="12" cy="13" r="3.5"/></Icon>;
const IconDev       = (p) => <Icon {...p}><path d="M8 6l-5 6 5 6"/><path d="M16 6l5 6-5 6"/></Icon>;
const IconX         = (p) => <Icon {...p}><path d="M6 6l12 12"/><path d="M6 18L18 6"/></Icon>;
const IconLink      = (p) => <Icon {...p}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></Icon>;
const IconSparkle   = (p) => <Icon {...p}><path d="M12 3v4"/><path d="M12 17v4"/><path d="M3 12h4"/><path d="M17 12h4"/><path d="M6 6l2 2"/><path d="M16 16l2 2"/><path d="M6 18l2-2"/><path d="M16 8l2-2"/></Icon>;
const IconRotate    = (p) => <Icon {...p}><path d="M4 12a8 8 0 0 1 14-5.3L20 8"/><path d="M20 4v4h-4"/><path d="M20 12a8 8 0 0 1-14 5.3L4 16"/><path d="M4 20v-4h4"/></Icon>;
const IconTerminal  = (p) => <Icon {...p}><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3"/><path d="M12 15h5"/></Icon>;
const IconClock     = (p) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Icon>;

Object.assign(window, {
  Icon, IconMic, IconPlay, IconPause, IconShield, IconLock, IconCloudOff, IconCheck,
  IconAlert, IconInfo, IconArrowRight, IconChevron, IconLanguages, IconUser,
  IconMapPin, IconCamera, IconDev, IconX, IconLink, IconSparkle, IconRotate,
  IconTerminal, IconClock,
});

```

---

## `primitives.jsx`

_Button, Chip, SectionHeader, Field, CompletenessMeter, Waveform, Divider._

```jsx
/* ============================================================================
 * KIN — primitives.jsx (Button, Chip, SectionHeader, Field, CompletenessMeter,
 *                       Waveform, Divider)
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • Match existing Tailwind conventions in the repo. The custom tokens
 *     (paper, card, hair, line, ink, muted, subtle, primary, primary-soft,
 *     amber, amber-soft, red, red-soft, green, green-soft) and radii
 *     (rounded-kin = 6px, rounded-kin-lg = 8px) are defined in the
 *     <script>tailwind.config={...}</script> block of the prototype HTML —
 *     port them into tailwind.config.ts as named tokens, do NOT inline as
 *     arbitrary values.
 *   • DO NOT CHANGE: the disabled-state pattern. Disabled is structural
 *     (border-line + text-muted + cursor-not-allowed) — NEVER opacity-based.
 *     This is field-UX principle #1 and was QA'd; reverting it regresses
 *     accessibility.
 *   • DO NOT CHANGE: Chip never uses color alone. Always icon + text + tone.
 *     The five tone keys (neutral, primary, amber, red, green) are the full
 *     vocabulary — don't add more, don't swap to filled-color backgrounds.
 *   • Button heights: sm=36, md=40, lg=48. lg is reserved for Begin/Stop in
 *     the voice panel — these are the most-pressed buttons in the demo and
 *     need the 48px hit-target. Don't downsize.
 *   • Waveform: state machine is 'idle' | 'recording' | 'processing' |
 *     'playback'. The animation-delay stagger (i % 8) * 70ms is tuned to
 *     feel organic without being seasick — leave it.
 *   • Field: the "—" empty state is INTENTIONAL. Empty fields stay visible
 *     so the worker sees the shape they're filling. Don't hide them.
 *   • CompletenessMeter shows segment count, NEVER a percentage. Field-UX
 *     principle #10 — no confidence numbers in front of workers.
 * ============================================================================
 * Small primitives inspired by shadcn's composition style, Tailwind only.
 * Field-tool-flavored: borders over shadows, high contrast, no opacity-as-state. */

// --- Button ------------------------------------------------------------
// Disabled is communicated structurally (border + text) + an icon when meaningful,
// NEVER through opacity alone. Principle 1.
const Button = React.forwardRef(({ variant = "primary", size = "md", icon, className = "", children, disabled, ...rest }, ref) => {
  const base = "inline-flex items-center justify-center gap-2 font-medium rounded-kin transition-colors duration-150 select-none";
  const sizes = {
    sm: "text-[14px] px-3 h-9",
    md: "text-[15px] px-4 h-10",
    lg: "text-[16px] px-5 h-12",
  };
  const variants = {
    primary: disabled
      ? "bg-white border border-line text-muted cursor-not-allowed"
      : "bg-primary text-white border border-primary hover:bg-primary-2",
    secondary: disabled
      ? "bg-white border border-line text-muted cursor-not-allowed"
      : "bg-white border border-line text-ink hover:bg-subtle",
    ghost: disabled
      ? "text-muted cursor-not-allowed"
      : "text-ink hover:bg-subtle",
    danger: disabled
      ? "bg-white border border-line text-muted cursor-not-allowed"
      : "bg-white border border-red text-red hover:bg-red-soft",
    confirm: disabled
      ? "bg-white border border-line text-muted cursor-not-allowed"
      : "bg-green text-white border border-green hover:brightness-95",
  };
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
});

// --- Chip / Badge (icon + text + color, never color alone) --------------
const Chip = ({ icon, children, tone = "neutral", className = "" }) => {
  const tones = {
    neutral: "bg-subtle border-line text-ink",
    primary: "bg-primary-soft border-primary/20 text-primary",
    amber:   "bg-amber-soft border-amber/40 text-[oklch(0.42_0.12_75)]",
    red:     "bg-red-soft border-red/30 text-red",
    green:   "bg-green-soft border-green/30 text-[oklch(0.38_0.1_155)]",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 h-7 px-2.5 text-[13px] font-medium border rounded-kin ${tones[tone]} ${className}`}>
      {icon}
      {children}
    </span>
  );
};

// --- Section separator header -------------------------------------------
const SectionHeader = ({ title, icon, meta, expanded = true, onToggle }) => (
  <div className="flex items-center justify-between py-3">
    <button
      type="button"
      onClick={onToggle}
      className="flex items-center gap-2.5 text-ink"
    >
      <span className="text-muted">{icon}</span>
      <span className="text-[21px] font-semibold tracking-[-0.005em]">{title}</span>
      {meta}
    </button>
    {onToggle && (
      <span className={`text-muted transition-transform duration-150 ${expanded ? "" : "-rotate-90"}`}>
        <IconChevron size={18} />
      </span>
    )}
  </div>
);

// --- Field row (label above value, 18px value, "—" empty state) ---------
// Principle 10: no confidence %. If a value is awaiting verification, show a "verify" chip.
const Field = ({ label, value, extra, verify, justPopulated, subValue }) => {
  return (
    <div className={`py-2.5 px-0 -mx-0 rounded-kin ${justPopulated ? "kin-populate" : ""}`}>
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-medium uppercase tracking-wider text-muted">{label}</div>
        {verify && (
          <Chip icon={<IconInfo size={12} />} tone="amber">Verify</Chip>
        )}
      </div>
      <div className="mt-1 text-[18px] text-ink leading-snug">
        {value === null || value === undefined || value === ""
          ? <span className="text-muted">—</span>
          : value}
      </div>
      {subValue && (
        <div className="mt-1 text-[15px] text-muted leading-snug">{subValue}</div>
      )}
      {extra}
    </div>
  );
};

// --- Completeness meter (segmented, not a percentage number) ------------
// Principle 10 adjacent: avoid numeric progress. Show structure instead.
const CompletenessMeter = ({ segments }) => {
  // segments: [{key,label,filled:boolean}]
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Record completeness</div>
        <div className="text-[12px] text-muted">{segments.filter(s => s.filled).length} of {segments.length} sections</div>
      </div>
      <div className="flex gap-1.5">
        {segments.map(s => (
          <div key={s.key} className="flex-1">
            <div className={`h-2 rounded-full border ${s.filled ? "bg-primary border-primary" : "bg-white border-line"}`} />
            <div className="mt-1.5 text-[11px] text-muted truncate">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

// --- Waveform (animated bars) --------------------------------------------
const Waveform = ({ state = "idle" /* idle | recording | processing | playback */, bars = 32 }) => {
  // deterministic heights so SSR-friendly
  const heights = React.useMemo(() => {
    const out = [];
    for (let i = 0; i < bars; i++) {
      // quasi-random but stable
      const v = 0.3 + 0.7 * Math.abs(Math.sin(i * 1.37 + 2.1));
      out.push(v);
    }
    return out;
  }, [bars]);

  const active = state === "recording" || state === "playback";
  const color =
    state === "recording" ? "bg-red"
    : state === "playback" ? "bg-primary"
    : state === "processing" ? "bg-muted"
    : "bg-line";

  return (
    <div className="flex items-center gap-[3px] h-10">
      {heights.map((h, i) => (
        <div
          key={i}
          className={`w-[3px] rounded-sm ${color} ${active ? "kin-wave-bar" : ""}`}
          style={{
            height: `${Math.round(h * 32) + 6}px`,
            animationDelay: active ? `${(i % 8) * 70}ms` : undefined,
            opacity: state === "idle" ? 0.55 : 1,
          }}
        />
      ))}
    </div>
  );
};

// --- Divider ------------------------------------------------------------
const Divider = ({ className = "" }) => (
  <div className={`border-t border-hair ${className}`} />
);

Object.assign(window, { Button, Chip, SectionHeader, Field, CompletenessMeter, Waveform, Divider });

```

---

## `record-card.jsx`

_Biographic record card with auto-expanding Guardian & Protection sub-section._

```jsx
/* ============================================================================
 * KIN — record-card.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: The Guardian & Protection sub-section auto-expansion
 *     when `minor === true` is load-bearing. The amber `highlight` tint
 *     (bg-amber-soft/50) on that sub-section is intentional — it's how a
 *     glance at the screen shows "this minor still needs CP routing."
 *     Round 1 QA covered this; do not "tidy" it to match other sections.
 *   • The minor-detected state is communicated in THREE places at once:
 *     (1) the amber strip above the card (rendered by app.jsx), (2) this
 *     sub-section's highlight tint, (3) the top-bar status pill. Triple
 *     redundancy is intentional — one of them must be visible regardless
 *     of scroll position.
 *   • TransliterationVariants block under the Name field is ONLY rendered
 *     when `record.nameVariants` is populated. Don't render an empty list.
 *   • PhotoPlaceholder is a STUB by design — copy says "Photo intake not
 *     yet implemented." Don't replace with a real upload UI in this build;
 *     out of scope for hackathon and the placeholder communicates honesty.
 *   • RTL handling: `nameNativeRtl` and `lastSeenLocationRtl` flip just
 *     those substrings. The aid-worker chrome stays LTR. This is the
 *     locked locale-split pattern — DO NOT flip the entire card.
 *   • `disabled` prop dims via opacity-50 + pointer-events-none — this is
 *     the ONE place opacity-as-state is allowed (the card is paused while
 *     the crisis layer is active). Field-UX principle #1 carve-out.
 * ============================================================================
 * Biographic, last-seen, distinguishing marks, plus optional Guardian &
 * Protection sub-section that auto-expands when a minor is detected. */

function TransliterationVariants({ variants }) {
  // variants: array like [{ latin: "Mohammed", script: "محمد", rtl: true }]
  if (!variants || !variants.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="text-[12px] font-medium uppercase tracking-wider text-muted">Variants</span>
      {variants.map((v, i) => (
        <span key={i} className="inline-flex items-center gap-2 text-[15px]">
          <span className="text-ink">{v.latin}</span>
          {v.script && (
            <span className={`text-ink/90 ${v.rtl ? "rtl" : ""}`} style={{ fontSize: 17 }}>
              {v.script}
            </span>
          )}
        </span>
      ))}
    </div>
  );
}

function PhotoPlaceholder() {
  // Stub per brief: "Photo intake not yet implemented". Neutral, structural.
  return (
    <div className="mt-2 flex items-center gap-3 border border-dashed border-line rounded-kin p-3 bg-subtle/60">
      <div className="w-14 h-14 rounded-kin bg-white border border-line flex items-center justify-center text-muted">
        <IconCamera size={22} />
      </div>
      <div className="flex-1">
        <div className="text-[14px] font-medium text-ink">Photos</div>
        <div className="text-[13px] text-muted">Photo intake not yet implemented in this build.</div>
      </div>
    </div>
  );
}

function SubSection({ id, title, icon, meta, children, expandedMap, setExpandedMap, highlight }) {
  const expanded = expandedMap[id] !== false;
  const toggle = () => setExpandedMap(m => ({ ...m, [id]: !expanded }));
  return (
    <section
      className={`border-t border-hair ${highlight ? "bg-amber-soft/50" : ""}`}
    >
      <SectionHeader title={title} icon={icon} meta={meta} expanded={expanded} onToggle={toggle} />
      {expanded && <div className="pb-4">{children}</div>}
    </section>
  );
}

function GuardianProtection({ data, minor, expandedMap, setExpandedMap }) {
  if (!minor) return null;
  return (
    <SubSection
      id="guardian"
      title="Guardian & Protection Status"
      icon={<IconShield size={18} />}
      meta={<Chip icon={<IconAlert size={12} />} tone="amber" className="ml-2">Required</Chip>}
      expandedMap={expandedMap}
      setExpandedMap={setExpandedMap}
      highlight
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
        <Field label="Guardian present at intake" value={data.guardianPresent} />
        <Field label="Consent to share with UNHCR CP" value={data.cpConsent} />
        <Field label="Known to case-management system" value={data.cmKnown} />
        <Field label="Referral status" value={data.referralStatus} />
      </div>
      <div className="mt-2 text-[13px] text-muted flex items-start gap-2">
        <IconInfo size={14} className="mt-0.5 shrink-0" />
        <span>Record will remain flagged <span className="font-medium text-ink">Incomplete — Minor Protection Required</span> until all four fields complete.</span>
      </div>
    </SubSection>
  );
}

function RecordCard({ record, minor, justPopulatedKey, disabled }) {
  const [expandedMap, setExpandedMap] = React.useState({});

  return (
    <div
      className={`relative bg-card border border-line rounded-kin-lg transition-opacity duration-200 ${disabled ? "opacity-50 pointer-events-none" : ""}`}
      aria-disabled={disabled || undefined}
    >
      <div className="px-6 pt-5 pb-1 flex items-center justify-between">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Record</div>
          <div className="text-[15px] text-ink mt-0.5">
            {record.name || <span className="text-muted">Unnamed — intake in progress</span>}
          </div>
        </div>
        <Chip
          icon={<IconLock size={12} />}
          tone="neutral"
          className="!bg-white"
        >
          Local only
        </Chip>
      </div>

      <div className="px-6 pb-2">
        <SubSection
          id="bio"
          title="Biographic"
          icon={<IconUser size={18} />}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
            <Field
              label="Name"
              value={record.name}
              subValue={record.nameNative && <span className={record.nameNativeRtl ? "rtl" : ""}>{record.nameNative}</span>}
              extra={<TransliterationVariants variants={record.nameVariants} />}
              justPopulated={justPopulatedKey === "name"}
            />
            <Field label="Age" value={record.age} justPopulated={justPopulatedKey === "age"} />
            <Field label="Relationship to speaker" value={record.relationship} justPopulated={justPopulatedKey === "relationship"} />
            <Field label="Spoken language" value={record.language} />
          </div>
        </SubSection>

        <GuardianProtection
          data={record.guardian || {}}
          minor={minor}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        />

        <SubSection
          id="lastseen"
          title="Last seen"
          icon={<IconMapPin size={18} />}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
            <Field
              label="Location"
              value={record.lastSeenLocation}
              subValue={record.lastSeenLocationSource &&
                <span className={record.lastSeenLocationRtl ? "rtl" : ""}>
                  {record.lastSeenLocationSource}
                </span>}
              justPopulated={justPopulatedKey === "lastSeenLocation"}
            />
            <Field label="Date" value={record.lastSeenDate} justPopulated={justPopulatedKey === "lastSeenDate"} />
            <Field label="Circumstance" value={record.circumstance} justPopulated={justPopulatedKey === "circumstance"} />
          </div>
        </SubSection>

        <SubSection
          id="marks"
          title="Distinguishing marks"
          icon={<IconSparkle size={18} />}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        >
          <div className="grid grid-cols-1 gap-x-8">
            <Field label="Physical description" value={record.physicalDesc} justPopulated={justPopulatedKey === "physicalDesc"} />
            <Field label="Identifying features" value={record.features} justPopulated={justPopulatedKey === "features"} />
          </div>
          <PhotoPlaceholder />
        </SubSection>
      </div>
    </div>
  );
}

Object.assign(window, { RecordCard, TransliterationVariants });

```

---

## `record-readonly.jsx`

_Read-only wrapper for RecordCard (queue → reopen flow)._

```jsx
/* ============================================================================
 * KIN — record-readonly.jsx (read-only RecordCard wrapper)
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • Wraps RecordCard with a banner. Do NOT fork the RecordCard component
 *     for read-only — pass `disabled` and render the banner above it. This
 *     keeps the layout identical so the worker recognizes the form on
 *     reopen.
 *   • Banner copy: "Read-only — reopen for editing." with a primary
 *     "Reopen" button. The Reopen action in production triggers an audit
 *     log entry (out of scope this build, button is a placeholder).
 *   • Banner uses amber-soft tone (advisory, not error). Don't escalate to
 *     red — read-only is normal queue behavior, not a failure state.
 * ============================================================================
 * RecordCard read-only mode + reuse. Imports the Round 1 RecordCard as-is.
 * Adds: read-only banner when reopening from queue. */

function RecordCardReadOnlyBanner({ onResume }) {
  return (
    <div className="mb-3 bg-card border border-line rounded-kin px-4 py-3 flex items-center gap-3">
      <div className="w-8 h-8 rounded-kin border border-line bg-subtle/60 text-muted flex items-center justify-center">
        <IconLock size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[14px] font-semibold text-ink">Viewing previous record</div>
        <div className="text-[13px] text-muted mt-0.5">Read-only · open from the queue. Editing not enabled in this build.</div>
      </div>
      <Button size="sm" variant="secondary" onClick={onResume}>New intake</Button>
    </div>
  );
}

Object.assign(window, { RecordCardReadOnlyBanner });

```

---

## `crisis-and-translit.jsx`

_CrisisReferralCard (canonical, do not redesign) + TransliterationMatch view._

```jsx
/* ============================================================================
 * KIN — crisis-and-translit.jsx (CrisisReferralCard + TransliterationMatch)
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *
 *   CrisisReferralCard (Round 2 verdict: CANONICAL — do not redesign)
 *   • DO NOT CHANGE: this is the ONLY place `shadow-elevated` is used in
 *     the entire system. Crisis is the highest-elevation surface; nothing
 *     else may share it. If you find yourself adding shadow-elevated
 *     elsewhere, reach for border-line first.
 *   • DO NOT CHANGE: red is used as ICON + TEXT + thin accent rule, never
 *     as a filled background surface. The red-soft chip in the header is
 *     the maximum red surface allowed. This was a Round 1 lock.
 *   • DO NOT CHANGE: the two dismissal buttons. They are explicitly
 *     "De-escalated — continue intake" and "Referral provided" — both
 *     LOGGED separately. There is no generic Close button. Both outcomes
 *     have meaning for the audit trail.
 *   • CRISIS_COPY (en/es/ar/fa) is the canonical localized copy. Do not
 *     paraphrase for tone — these strings were chosen for plain-language
 *     calm. If product wants new languages added, the pattern is dir+title
 *     +body+hotline+play; mirror exactly.
 *   • The card is positioned `fixed left-1/2 top-[140px]` and rises via
 *     kin-rise. It does NOT modal-block the page — the record card behind
 *     dims (opacity-50) but stays mounted. This preserves spatial context.
 *
 *   TransliterationMatch
 *   • The `phase` state machine is 'split' → 'linking' → 'merged'. Driven
 *     by real algorithm output in production (jaro-winkler + transliteration
 *     bridge), simulated here via setTimeout. Wire to your match service.
 *   • VIEWPORT FIX FOR BUNDLE 1.5: the merged card's grid currently uses
 *     `grid-cols-2 md:grid-cols-3` — change to `grid-cols-2 xl:grid-cols-3`
 *     so that <1400px viewports (1366×768 laptops) don't cramp the columns.
 *     This is the ~10-line fix mentioned in the design Q&A. Fold into the
 *     match-view session, not a separate task.
 *   • The MiniRecord tone prop (warm/cool) provides subtle differentiation
 *     between Intake A and Intake B — these are oklch warm-neutral and
 *     cool-neutral PAPER tints, not primary color. Don't escalate to
 *     primary/amber for "stronger" differentiation in this match view —
 *     the differentiation belongs in the SPLIT view (different file/work).
 * ============================================================================
 * Crisis referral card + Transliteration-match view. */

// Localized crisis copy. English stays as reference; the other three are the displaced-person UI.
const CRISIS_COPY = {
  en: { dir: "ltr", title: "Help is available",
        body: "You are safe here. Trained support is available right now, in your language. Would you like to listen to a short message?",
        hotline: "IFRC Regional Support Line",
        play: "Play in English" },
  es: { dir: "ltr", title: "Ayuda disponible",
        body: "Está a salvo aquí. Hay apoyo disponible ahora mismo, en su idioma. ¿Quiere escuchar un mensaje corto?",
        hotline: "Línea de Apoyo Regional FICR",
        play: "Reproducir en español" },
  ar: { dir: "rtl", title: "المساعدة متاحة",
        body: "أنتَ في أمان هنا. الدعم متاح الآن، بلغتك. هل ترغب في الاستماع إلى رسالة قصيرة؟",
        hotline: "خط الدعم الإقليمي للاتحاد الدولي لجمعيات الصليب الأحمر والهلال الأحمر",
        play: "تشغيل بالعربية" },
  fa: { dir: "rtl", title: "کمک در دسترس است",
        body: "شما اینجا در امان هستید. همین حالا، به زبان شما، پشتیبانی در دسترس است. آیا می‌خواهید یک پیام کوتاه بشنوید؟",
        hotline: "خط پشتیبانی منطقه‌ای IFRC",
        play: "پخش به فارسی" },
};

function CrisisReferralCard({ lang, onResolved, onDeEscalated }) {
  const copy = CRISIS_COPY[lang] || CRISIS_COPY.en;
  const [playing, setPlaying] = React.useState(false);
  const rtl = copy.dir === "rtl";

  React.useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setPlaying(false), 3200);
    return () => clearTimeout(t);
  }, [playing]);

  return (
    <div
      role="dialog"
      aria-label="Crisis referral"
      className="kin-rise fixed left-1/2 top-[140px] z-30 w-[min(640px,calc(100%-48px))] bg-card border border-line rounded-kin-lg shadow-elevated"
      style={{ transform: "translateX(-50%)" }}
    >
      {/* Header: red used sparingly (icon + thin accent rule), not as a background */}
      <div className="border-b border-hair px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-kin border border-red/30 bg-red-soft text-red flex items-center justify-center">
          <IconAlert size={18} />
        </div>
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-red">Crisis signal detected</div>
          <div className="text-[14px] text-muted">Primary record paused. Surface this card to the person in front of you.</div>
        </div>
      </div>

      {/* Displaced-person-facing surface */}
      <div className={`px-6 py-5 ${rtl ? "rtl" : ""}`}>
        <div className="text-[26px] font-semibold text-ink leading-tight">{copy.title}</div>
        <p className="mt-2 text-[17px] text-ink/90 leading-relaxed" style={{ textWrap: "pretty" }}>
          {copy.body}
        </p>

        <div className="mt-4 border border-line rounded-kin p-4 bg-subtle/60">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setPlaying(true)}
              className="shrink-0 w-12 h-12 rounded-full bg-primary text-white border border-primary hover:bg-primary-2 transition-colors flex items-center justify-center"
              aria-label={copy.play}
            >
              {playing ? <IconPause size={20} /> : <IconPlay size={20} />}
            </button>
            <div className="flex-1 min-w-0">
              <div className="text-[15px] font-medium text-ink">{copy.play}</div>
              <div className="mt-1"><Waveform state={playing ? "playback" : "idle"} bars={28} /></div>
            </div>
          </div>
        </div>

        <div className={`mt-4 flex items-center gap-2 text-[14px] text-muted ${rtl ? "flex-row-reverse" : ""}`}>
          <IconInfo size={14} />
          <span>{copy.hotline} · +00 000 000 0000</span>
        </div>
      </div>

      {/* Dismissal: two explicit logged actions, no generic Close. */}
      <div className="border-t border-hair bg-subtle/60 px-6 py-3 flex flex-col sm:flex-row gap-2 sm:justify-end">
        <Button variant="secondary" onClick={onDeEscalated}>De-escalated — continue intake</Button>
        <Button variant="confirm" icon={<IconCheck size={16} />} onClick={onResolved}>Referral provided</Button>
      </div>
    </div>
  );
}

// --- Transliteration match view ------------------------------------------
function MiniRecord({ title, tone, name, script, age, lastSeen, circumstance }) {
  const toneBg = tone === "warm" ? "bg-[oklch(0.985_0.012_75)]" : "bg-[oklch(0.985_0.006_220)]";
  return (
    <div className={`flex-1 border border-line rounded-kin-lg ${toneBg}`}>
      <div className="px-5 py-3 border-b border-hair flex items-center justify-between">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">{title}</div>
        <Chip icon={<IconLock size={12} />} tone="neutral" className="!bg-white">Local only</Chip>
      </div>
      <div className="px-5 py-4">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Name</div>
        <div className="mt-1 flex items-baseline gap-3">
          <div className="text-[20px] font-semibold text-ink">{name}</div>
          <div className="rtl text-[20px] text-ink/80">{script}</div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Age</div>
            <div className="text-[16px] text-ink">{age}</div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Last seen</div>
            <div className="text-[16px] text-ink">{lastSeen}</div>
          </div>
          <div className="col-span-2">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Circumstance</div>
            <div className="text-[16px] text-ink">{circumstance}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TransliterationMatch({ phase, onBack }) {
  // phase: 'split' -> both cards + link drawing -> 'merged'
  const showLink = phase === "linking" || phase === "merged";
  const merged   = phase === "merged";

  return (
    <div className="max-w-[960px] mx-auto w-full">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Reunification candidate</div>
          <div className="text-[22px] font-semibold text-ink mt-0.5">Cross-session match under review</div>
        </div>
        <Button variant="ghost" size="sm" icon={<IconArrowRight className="rotate-180" size={16} />} onClick={onBack}>
          Back to intake
        </Button>
      </div>

      <div className={`grid grid-cols-1 md:grid-cols-2 gap-5 transition-opacity duration-300 ${merged ? "opacity-30" : ""}`}>
        <MiniRecord
          title="Intake A · Session #089"
          tone="warm"
          name="Mohammed Al-Saleh"
          script="محمد الصالح"
          age="34 (self)"
          lastSeen="Border crossing, Jordan"
          circumstance="Separated from spouse and son during transit"
        />
        <MiniRecord
          title="Intake B · Session #147"
          tone="cool"
          name="Mohamad Alsaleh"
          script="محمد الصالح"
          age="searching for brother"
          lastSeen="Zaatari reception area"
          circumstance="Looking for sibling last seen at border"
        />
      </div>

      {/* Animated link / arrow */}
      <div className="relative h-20 my-2">
        {showLink && (
          <svg viewBox="0 0 400 80" className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
            <path
              d="M 80 10 C 120 60, 280 60, 320 10"
              fill="none"
              stroke="oklch(0.55 0.11 155)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              className="kin-link-draw"
            />
            <circle cx="200" cy="40" r="14" fill="oklch(0.96 0.03 155)" stroke="oklch(0.55 0.11 155)" strokeWidth="1" />
            <g transform="translate(192,32)">
              <path d="M3 4 L7 8 L13 2" fill="none" stroke="oklch(0.55 0.11 155)" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
            </g>
          </svg>
        )}
      </div>

      {/* Merged card */}
      {merged && (
        <div className="kin-rise relative bg-card border border-green/40 rounded-kin-lg" style={{ transform: "none" }}>
          <div className="px-6 py-4 border-b border-hair bg-green-soft/60 flex items-center gap-3">
            <div className="w-8 h-8 rounded-kin bg-white border border-green/40 text-green flex items-center justify-center">
              <IconLink size={16} />
            </div>
            <div>
              <div className="text-[12px] font-medium uppercase tracking-wider text-[oklch(0.38_0.1_155)]">Match confirmed</div>
              <div className="text-[15px] text-ink mt-0.5">2 intake sessions matched via transliteration comparison.</div>
            </div>
            <div className="ml-auto"><Chip icon={<IconCheck size={12} />} tone="green">Pending caseworker review</Chip></div>
          </div>
          <div className="px-6 py-5">
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Unified identity</div>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <div className="rtl text-[28px] font-semibold text-ink">محمد الصالح</div>
              <div className="text-[22px] text-ink">Mohammed Al-Saleh</div>
              <div className="text-[16px] text-muted">· also: Mohamad Alsaleh</div>
            </div>

            <div className="mt-5 grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Source script</div>
                <div className="rtl text-[17px] text-ink mt-0.5">محمد الصالح</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Phonetic variants</div>
                <div className="text-[15px] text-ink mt-0.5">Mohammed · Mohamad</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Linked sessions</div>
                <div className="text-[15px] text-ink mt-0.5">#089 · #147</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Relationship signal</div>
                <div className="text-[15px] text-ink mt-0.5">Sibling (self-identified ↔ searched)</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Last-seen overlap</div>
                <div className="text-[15px] text-ink mt-0.5">Jordan border corridor</div>
              </div>
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Next step</div>
                <div className="text-[15px] text-ink mt-0.5">Route to caseworker for reunification review</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { CrisisReferralCard, TransliterationMatch, CRISIS_COPY });

```

---

## `structlog.jsx`

_Right-rail structured event log. "Stripe API docs" credibility surface._

```jsx
/* ============================================================================
 * KIN — structlog.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: the "Stripe API docs" typographic credibility aesthetic.
 *     Mono font for keys/values, no chrome (no card borders around rows),
 *     status communicated via 1px LEFT BORDER per row (not bg fill, not
 *     icon). This is the locked sidebar visual language.
 *   • DO NOT CHANGE: heartbeat states. 'idle' = 2s pulse, 'busy' = 0.5s
 *     pulse, 'down' = solid amber. The amber-on-disconnect is critical —
 *     it is how the operator knows the field tool is queueing locally vs
 *     synced. This is part of the trust story for offline-first.
 *   • Mono font: ui-monospace stack. If your repo has a custom mono
 *     (JetBrains Mono, Berkeley Mono, etc.), swap it in via Tailwind
 *     font-mono — but keep the size at text-[11px] for entries. The
 *     density is intentional.
 *   • Event row schema: { ts, level, msg, kv? }. `kv` is rendered as
 *     inline key=value pairs in muted color. When porting, keep the
 *     unstyled-key, styled-value pattern — flipping it makes scanning
 *     harder.
 *   • For SPLIT view (future Bundle 1.5+ work): rows will gain an
 *     `origin: 'A' | 'B'` field that prepends a mono [A]/[B] tag.
 *     Don't refactor the row component until split lands — leaving the
 *     hook obvious here.
 * ============================================================================
 * Structlog sidebar — credibility surface, "Stripe API docs" aesthetic.
 * Typographic hierarchy, status by 1px left border, no chrome.
 * Heartbeat in header: pulses 2s idle / 0.5s in-flight / amber on disconnect. */

function StructlogHeartbeat({ state /* 'idle' | 'busy' | 'down' */, since }) {
  const dotCls =
    state === "busy" ? "bg-primary" :
    state === "down" ? "bg-amber" :
    "bg-green";
  // Different pulse cadence per state via inline style
  const pulse =
    state === "busy" ? "kin-pulse-fast" :
    state === "down" ? "" :
    "kin-pulse-slow";
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-muted" aria-live="polite">
      <span className={`w-[6px] h-[6px] rounded-full ${dotCls} ${pulse}`} aria-hidden="true" />
      <span className="text-ink/70">
        {state === "down" ? "SSE down" : state === "busy" ? "SSE · in-flight" : "SSE live"}
      </span>
      {since && state !== "down" && <span>· connected {since}</span>}
    </span>
  );
}

function StructlogRow({ ev }) {
  // status: 'ok' (default) | 'started' | 'warn' | 'error'
  const borderCls =
    ev.status === "started" ? "border-l-primary" :
    ev.status === "warn"    ? "border-l-amber" :
    ev.status === "error"   ? "border-l-red" :
    "border-l-line";

  const tRel = `+${(ev.tMs / 1000).toFixed(2)}s`;
  return (
    <li className={`px-3 py-2 border-l-2 ${borderCls} hover:bg-subtle/60 transition-colors`}>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[12px] text-ink">{ev.name}</span>
        <span className="font-mono text-[10.5px] text-muted ml-auto tabular-nums">{tRel}</span>
      </div>
      {ev.subtitle && <div className="text-[12px] text-muted mt-0.5 leading-snug">{ev.subtitle}</div>}
      {ev.kvs && (
        <div className="mt-1 font-mono text-[11px] text-muted leading-relaxed">
          {Object.entries(ev.kvs).map(([k, v]) => (
            <div key={k}>
              <span className="text-[oklch(0.45_0.02_240)]">{k}</span>
              <span>=</span>
              <span className="text-ink">{typeof v === "string" ? `"${v}"` : String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </li>
  );
}

function StructlogSidebar({ events, heartbeat = "idle", since = "11:02" }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events.length]);

  return (
    <aside className="border-l border-line bg-card flex flex-col h-full" style={{ width: 320 }} aria-label="Pipeline structlog">
      <div className="px-4 h-14 border-b border-hair flex flex-col justify-center gap-0.5">
        <div className="flex items-center justify-between">
          <div className="text-[13px] font-semibold text-ink">Pipeline</div>
          <StructlogHeartbeat state={heartbeat} since={since} />
        </div>
        <div className="text-[11px] text-muted">structlog · session #147</div>
      </div>

      <div ref={ref} className="flex-1 overflow-y-auto py-1">
        {events.length === 0 ? (
          <div className="px-4 py-6 text-[12px] text-muted leading-relaxed">
            System ready. Pipeline events will appear as the intake runs.
          </div>
        ) : (
          <ol>{events.map((ev, i) => <StructlogRow key={ev.id ?? i} ev={ev} />)}</ol>
        )}
      </div>

      <div className="border-t border-hair px-4 py-2 text-[11px] text-muted font-mono flex items-center justify-between">
        <span>{events.length} events</span>
        <span>auto-scroll</span>
      </div>
    </aside>
  );
}

Object.assign(window, { StructlogSidebar, StructlogHeartbeat });

```

---

## `tool-calls.jsx`

_Right-rail LLM function-call observability. SEPARATE from structlog._

```jsx
/* ============================================================================
 * KIN — tool-calls.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: tool-calls and structlog are SEPARATE sidebars. They
 *     show different things and resisted merge during Round 2 review:
 *       structlog = system events (sync, heartbeat, save, log lines)
 *       tool-calls = LLM function-call observability (name, args, result)
 *     Merging them flattens the credibility narrative — keep them split.
 *   • DO NOT CHANGE: the two-state row pattern. A call appears first as
 *     'started' (gray, name only, no args yet) and resolves to full
 *     args+result with a one-shot highlight pulse on landing. This
 *     animates the "function call ↔ response" rhythm — it's what makes
 *     the panel read as live observability instead of a static log.
 *   • JSON formatting: 2-space indent, mono, text-[11px]. The args/result
 *     blocks have a subtle bg (bg-paper) to separate from the row chrome.
 *     Don't add syntax highlighting — plain mono reads more "API debugger"
 *     than "fancy IDE."
 *   • Status colors on the left rule: gray (started), green (ok), red
 *     (error). Red errors should NEVER be silently dropped — they're
 *     part of the honesty story.
 * ============================================================================
 * Tool-calls sidebar — JSON function-call observability, separate from structlog.
 * Each call streams in as 'started', resolves to full args+result with pulse. */

function JsonValue({ value }) {
  if (value === null) return <span className="text-muted">null</span>;
  if (typeof value === "string") return <span className="text-[oklch(0.42_0.1_155)]">"{value}"</span>;
  if (typeof value === "number" || typeof value === "boolean") return <span className="text-primary">{String(value)}</span>;
  if (Array.isArray(value)) {
    return (
      <span>
        <span className="text-muted">[</span>
        {value.map((v, i) => (
          <React.Fragment key={i}>
            <JsonValue value={v} />
            {i < value.length - 1 && <span className="text-muted">, </span>}
          </React.Fragment>
        ))}
        <span className="text-muted">]</span>
      </span>
    );
  }
  return <span className="text-ink">{JSON.stringify(value)}</span>;
}

function JsonObject({ obj, indent = 0 }) {
  const entries = Object.entries(obj || {});
  if (!entries.length) return <span className="text-muted">{"{}"}</span>;
  return (
    <div className="font-mono text-[11.5px] leading-relaxed">
      <span className="text-muted">{"{"}</span>
      <div className="ml-3">
        {entries.map(([k, v], i) => (
          <div key={k}>
            <span className="text-[oklch(0.45_0.02_240)]">"{k}"</span>
            <span className="text-muted">: </span>
            <JsonValue value={v} />
            {i < entries.length - 1 && <span className="text-muted">,</span>}
          </div>
        ))}
      </div>
      <span className="text-muted">{"}"}</span>
    </div>
  );
}

function ToolCallRow({ call, isLatest }) {
  const started = call.status === "started";
  return (
    <div className={`px-4 py-3 border-b border-hair ${isLatest && !started ? "kin-populate" : ""}`}>
      <div className="flex items-baseline gap-2">
        <span className={`font-mono text-[12.5px] font-medium ${started ? "text-muted" : "text-primary"}`}>
          {call.name}
        </span>
        {started && (
          <span className="inline-flex items-center gap-1 text-[10.5px] font-mono text-muted ml-1">
            <span className="w-1 h-1 rounded-full bg-muted animate-pulse" />
            running
          </span>
        )}
        <span className="font-mono text-[10.5px] text-muted ml-auto tabular-nums">
          +{(call.tMs / 1000).toFixed(2)}s
        </span>
      </div>

      {!started && call.args && (
        <div className="mt-1.5">
          <div className="text-[10px] uppercase tracking-wider text-muted font-medium mb-0.5">args</div>
          <JsonObject obj={call.args} />
        </div>
      )}

      {!started && call.result !== undefined && (
        <div className="mt-2">
          <div className="text-[10px] uppercase tracking-wider text-muted font-medium mb-0.5">result</div>
          <div className="font-mono text-[11.5px] text-ink">
            {typeof call.result === "object"
              ? <JsonObject obj={call.result} />
              : <JsonValue value={call.result} />}
          </div>
        </div>
      )}
    </div>
  );
}

function ToolCallsSidebar({ calls }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [calls.length]);

  return (
    <aside className="border-l border-line bg-card flex flex-col h-full" style={{ width: 320 }} aria-label="Tool calls">
      <div className="px-4 h-14 border-b border-hair flex flex-col justify-center gap-0.5">
        <div className="flex items-center justify-between">
          <div className="text-[13px] font-semibold text-ink">Tool calls</div>
          <span className="text-[11px] font-mono text-muted">gemma · e2b</span>
        </div>
        <div className="text-[11px] text-muted">function invocations · live</div>
      </div>

      <div ref={ref} className="flex-1 overflow-y-auto">
        {calls.length === 0 ? (
          <div className="px-4 py-6 text-[12px] text-muted leading-relaxed">
            No invocations yet. Tool calls land here as the model decides to use them.
          </div>
        ) : (
          calls.map((c, i) => (
            <ToolCallRow key={c.id} call={c} isLatest={i === calls.length - 1} />
          ))
        )}
      </div>

      <div className="border-t border-hair px-4 py-2 text-[11px] text-muted font-mono flex items-center justify-between">
        <span>{calls.filter(c => c.status !== "started").length} resolved</span>
        <span>{calls.filter(c => c.status === "started").length} in flight</span>
      </div>
    </aside>
  );
}

Object.assign(window, { ToolCallsSidebar });

```

---

## `nav-rail.jsx`

_44px left navigation rail (Intake / Queue)._

```jsx
/* ============================================================================
 * KIN — nav-rail.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: 44px width. This is min hit-target on touch + matches
 *     the iOS/macOS sidebar rail convention. Wider feels desktop-app
 *     bloated; narrower fails accessibility.
 *   • DO NOT CHANGE: active-state pattern = bg-card + 2px primary left
 *     accent + ink text. The 2px accent is what makes it readable from
 *     across the room during a demo. No filled-color tabs.
 *   • Two routes only: 'intake' (mic icon) and 'queue' (list icon). Do
 *     NOT add settings/profile/etc. icons here — Settings lives elsewhere
 *     (overflow on top bar). Adding rail items dilutes the bimodal
 *     (capture vs. review) story.
 *   • Bottom: KIN wordmark + sync-status dot. Dot color follows the same
 *     idle/busy/down vocabulary as the structlog heartbeat — keep them
 *     visually synced; they refer to the same underlying state.
 *   • Accessibility: each rail button gets aria-label (icons-only). The
 *     active route also sets aria-current="page". Preserve both.
 * ============================================================================
 * Navigation Rail — 44px wide, full height, hairline border, no shadow.
 * Two icons: Intake (mic), Queue (list). Active state: bg + 2px left accent. */

function NavRail({ route, setRoute, queuedCount, syncOk = true }) {
  const items = [
    { key: "intake", label: "Intake", icon: <IconMic size={18} />, hot: "⌘1" },
    { key: "queue",  label: "Queue",  icon: <IconList size={18} />, hot: "⌘2", badge: queuedCount },
  ];
  return (
    <nav
      aria-label="Primary"
      className="shrink-0 w-[44px] bg-card border-r border-line flex flex-col"
    >
      {/* Wordmark anchor — matches top bar dot pattern */}
      <div className="h-14 flex items-center justify-center border-b border-hair">
        <div className="w-6 h-6 rounded-kin border border-ink/70 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-primary" />
        </div>
      </div>

      <ul className="flex-1 py-2 flex flex-col gap-0.5">
        {items.map((it) => {
          const active = route === it.key;
          return (
            <li key={it.key} className="relative">
              {active && (
                <span aria-hidden="true" className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-primary rounded-r" />
              )}
              <button
                type="button"
                onClick={() => setRoute(it.key)}
                title={`${it.label} (${it.hot})`}
                aria-current={active ? "page" : undefined}
                className={`group w-full h-10 flex items-center justify-center relative transition-colors
                  ${active ? "text-primary bg-primary-soft" : "text-muted hover:text-ink hover:bg-subtle"}`}
              >
                {it.icon}
                {it.badge ? (
                  <span className="absolute top-1.5 right-1.5 min-w-[14px] h-[14px] px-1 rounded-full bg-primary text-white text-[9px] font-semibold flex items-center justify-center leading-none">
                    {it.badge > 9 ? "9+" : it.badge}
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>

      {/* Sync dot */}
      <div className="h-12 flex flex-col items-center justify-center gap-1 border-t border-hair">
        <div title={syncOk ? "Local hub reachable" : "Local-only"}
             className={`w-1.5 h-1.5 rounded-full ${syncOk ? "bg-green" : "bg-amber"}`} />
        <div className="text-[9px] font-mono uppercase tracking-wider text-muted">v0.4</div>
      </div>
    </nav>
  );
}

const IconList = (p) => (
  <Icon {...p}>
    <path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/>
    <circle cx="4" cy="6" r="1" fill="currentColor" stroke="none"/>
    <circle cx="4" cy="12" r="1" fill="currentColor" stroke="none"/>
    <circle cx="4" cy="18" r="1" fill="currentColor" stroke="none"/>
  </Icon>
);

Object.assign(window, { NavRail, IconList });

```

---

## `queue-view.jsx`

_Records list with filter chips. Click row → read-only intake._

```jsx
/* ============================================================================
 * KIN — queue-view.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • SEEDED_RECORDS is demo data. Replace with your records query
 *     (probably react-query against /api/records or similar). Schema:
 *       { id, name, age, sex, lastSeen, status, minor, language, ts }
 *     status enum: 'open' | 'matched' | 'closed' | 'crisis'
 *   • Filters: All / Open / Matched / Crisis. The Crisis filter shows
 *     records where the crisis flag was raised even if since-resolved —
 *     this is the operations-review surface. Don't filter to "active
 *     crisis only."
 *   • Row click → opens record in Intake panel as READ-ONLY
 *     (record-readonly.jsx). Editing from queue is a separate flow
 *     (out of scope for hackathon). The read-only banner is load-bearing
 *     here — it tells the worker they're reviewing, not capturing.
 *   • Visual: hairline rows, no zebra striping. Status is a Chip on the
 *     right, language is muted text. Density is intentional — this is a
 *     scan-many-quickly surface.
 *   • The minor flag in row badges uses Shield icon + amber tone,
 *     matching record-card. Stay consistent with the triple-redundancy
 *     pattern — same vocabulary across surfaces.
 * ============================================================================
 * Queue View — list of records with filters. Click row → read-only Intake. */

const SEEDED_RECORDS = [
  {
    id: 89,  name: "Mohammed Al-Saleh", native: "محمد الصالح", rtl: true,
    age: "34", status: "complete", statusLabel: "Complete",
    updated: "Today · 09:14", sync: "synced",
    summary: "Self-registered · separated from spouse and son · last seen Jordan border",
  },
  {
    id: 102, name: "Ana Beltrán Ruiz", age: "29", status: "complete", statusLabel: "Complete",
    updated: "Today · 10:42", sync: "syncing",
    summary: "Reuniting with brother · last seen Tuxtla Gutiérrez",
  },
  {
    id: 138, name: "Yusuf Karimi", native: "یوسف کریمی", rtl: true,
    age: "16", status: "minor", statusLabel: "Incomplete · Minor protection",
    updated: "Today · 11:08", sync: "local",
    summary: "Unaccompanied minor · Guardian/CP fields pending",
  },
  {
    id: 141, name: "Daniela Ortiz", age: "41", status: "complete", statusLabel: "Complete",
    updated: "Today · 11:55", sync: "local",
    summary: "Searching for daughter · last seen Tapachula bus terminal",
  },
];

const STATUS_TONE = {
  complete: "green",
  minor:    "amber",
  crisis:   "red",
  active:   "primary",
};

function QueueRow({ r, onOpen }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(r)}
      className="w-full text-left grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-5 py-3 border-t border-hair hover:bg-subtle transition-colors"
    >
      <div className="min-w-0">
        <div className="flex items-baseline gap-3 flex-wrap">
          <span className="text-[16px] text-ink font-medium truncate">{r.name}</span>
          {r.native && <span className={`text-[15px] text-ink/80 ${r.rtl ? "rtl" : ""}`}>{r.native}</span>}
          <span className="font-mono text-[11px] text-muted">#{r.id}</span>
        </div>
        <div className="text-[13px] text-muted truncate mt-0.5">{r.summary}</div>
      </div>
      <Chip
        icon={r.status === "minor" ? <IconShield size={12} /> :
              r.status === "crisis" ? <IconAlert size={12} /> : <IconCheck size={12} />}
        tone={STATUS_TONE[r.status] || "neutral"}
      >{r.statusLabel}</Chip>
      <div className="text-[12px] text-muted font-mono tabular-nums w-[110px] text-right">{r.updated}</div>
      <span className={`inline-flex items-center gap-1.5 text-[12px] ${
        r.sync === "synced" ? "text-green" : r.sync === "syncing" ? "text-primary" : "text-muted"
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${
          r.sync === "synced" ? "bg-green" : r.sync === "syncing" ? "bg-primary animate-pulse" : "bg-muted"
        }`} />
        {r.sync === "synced" ? "Synced" : r.sync === "syncing" ? "Syncing" : "Local-only"}
      </span>
    </button>
  );
}

function QueueView({ records, onOpen, onNew }) {
  const [filter, setFilter] = React.useState("all");
  const filtered = React.useMemo(() => {
    if (filter === "all") return records;
    if (filter === "incomplete") return records.filter(r => r.status === "minor");
    if (filter === "today") return records;
    return records;
  }, [records, filter]);

  const filters = [
    { id: "all",        label: "All",        count: records.length },
    { id: "incomplete", label: "Incomplete", count: records.filter(r => r.status === "minor").length },
    { id: "today",      label: "Today",      count: records.length },
  ];

  return (
    <div className="max-w-[1100px] mx-auto px-6 py-6">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Queue</div>
          <h1 className="text-[24px] font-semibold text-ink mt-0.5 tracking-[-0.01em]">
            Records on this device
          </h1>
          <div className="text-[14px] text-muted mt-1">
            Click any record to reopen. Local-only records will sync when the hub is reachable.
          </div>
        </div>
        <Button variant="primary" icon={<IconMic size={16} />} onClick={onNew}>New intake</Button>
      </div>

      <div className="flex items-center gap-1.5 mb-4 flex-wrap">
        {filters.map(f => {
          const active = filter === f.id;
          return (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`h-8 px-3 text-[13px] font-medium rounded-kin border transition-colors ${
                active ? "bg-primary text-white border-primary" : "bg-white text-ink border-line hover:bg-subtle"
              }`}
            >
              {f.label}
              <span className={`ml-1.5 text-[11px] font-mono ${active ? "text-white/80" : "text-muted"}`}>{f.count}</span>
            </button>
          );
        })}
      </div>

      <div className="bg-card border border-line rounded-kin-lg overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-muted">
          <div>Record</div><div>Status</div><div className="w-[110px] text-right">Updated</div><div>Sync</div>
        </div>
        {filtered.length === 0 ? (
          <div className="px-5 py-12 text-center text-[14px] text-muted border-t border-hair">
            No records match this filter.
          </div>
        ) : filtered.map(r => <QueueRow key={r.id} r={r} onOpen={onOpen} />)}
      </div>
    </div>
  );
}

Object.assign(window, { QueueView, SEEDED_RECORDS });

```

---

## `coach-mark.jsx`

_First-load orientation overlay, dismissible, localStorage-persisted._

```jsx
/* ============================================================================
 * KIN — coach-mark.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • Storage key: 'kin.coachmark.dismissed'. Don't change without
 *     migration — returning users see it again if you do.
 *   • Auto-cleared when presentation mode activates (?present=1 or
 *     ⌘⇧P). This is intentional — judges should never see the coach
 *     mark. presentation-mode.jsx handles the clear; do not also clear
 *     here, you'll race.
 *   • Copy is plain-language, max 2 short sentences per panel. Resist
 *     the urge to add more — this is first-load friction and every
 *     extra sentence costs trust.
 *   • Position: anchored to nav-rail (left side). If you move the rail
 *     to the right (RTL UI direction for full-Arabic deployments —
 *     future scope), mirror this anchor.
 * ============================================================================
 * Coach-mark — first-load orientation, dismissible. localStorage-persisted.
 * Cleared automatically when presentation mode activates. */

const COACH_KEY = "kin.coachmark.v1.dismissed";

function useCoachMark(presentationActive) {
  const [show, setShow] = React.useState(false);
  React.useEffect(() => {
    try {
      const dismissed = localStorage.getItem(COACH_KEY);
      if (!dismissed) setShow(true);
    } catch (_) {}
  }, []);
  React.useEffect(() => {
    if (presentationActive && show) {
      setShow(false);
      try { localStorage.setItem(COACH_KEY, "1"); } catch(_) {}
    }
  }, [presentationActive, show]);

  const dismiss = () => {
    setShow(false);
    try { localStorage.setItem(COACH_KEY, "1"); } catch(_) {}
  };
  return { show, dismiss };
}

function CoachMark({ show, onDismiss }) {
  if (!show) return null;
  return (
    <div
      role="dialog"
      aria-label="Quick orientation"
      className="kin-rise mx-6 mt-4 mb-1 bg-card border border-line rounded-kin-lg overflow-hidden"
    >
      <div className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-kin border border-primary/30 bg-primary-soft text-primary flex items-center justify-center shrink-0">
            <IconInfo size={16} />
          </div>
          <div className="min-w-0">
            <div className="text-[14px] font-semibold text-ink">Welcome — quick orientation</div>
            <div className="text-[13px] text-muted mt-0.5">
              Use the rail on the left to switch between <span className="text-ink font-medium">Intake</span> and the <span className="text-ink font-medium">Queue</span>. Press <span className="font-mono text-ink">Begin</span> to start an intake; the system speaks the language detected from the audio. Pipeline events stream in the right sidebars as proof of work.
            </div>
          </div>
        </div>
        <div className="sm:ml-auto flex items-center gap-2 shrink-0">
          <Button size="sm" variant="secondary" onClick={onDismiss}>Got it</Button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { useCoachMark, CoachMark });

```

---

## `presentation-mode.jsx`

_⌘⇧P + ?present=1 driver. Hides dev surfaces, seeds Beat 6 data._

```jsx
/* ============================================================================
 * KIN — presentation-mode.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: scope. This file is INTENTIONALLY thin. It is NOT a
 *     UI scripter, NOT a step-runner, NOT an animation controller. It does
 *     three things only — keep it that way:
 *       1. Hide dev surfaces (DemoDock and any data-dev="true" elements)
 *       2. Seed required demo data (Mohammed snapshot pre-loaded so the
 *          Beat 6 transliteration match has something to match against)
 *       3. Optional presenter HUD below the 1080p safe-area
 *   • Activated by ⌘⇧P or ?present=1 query param. Both should produce
 *     identical state — the URL param exists so a presenter can deep-link
 *     into a clean state from a fresh tab.
 *   • Coach-mark is auto-dismissed when presentation activates (the
 *     coach-mark file reads the same localStorage key — set it).
 *   • DO NOT add demo-step automation here. The whole point of this build
 *     is that the demo runs from REAL state transitions driven by REAL
 *     (or simulated) audio + LLM responses, not a scripted UI tour. If you
 *     find yourself adding setTimeouts to advance the UI, stop — that work
 *     belongs in your audio/LLM mock layer, not here.
 *   • Presenter HUD is OPTIONAL and lives below y=1080. Safe to omit
 *     entirely if your demo monitor crops to 1920×1080.
 *   • Exit: Esc or ⌘⇧P toggle. Restore DemoDock visibility on exit.
 * ============================================================================
 * Presentation-mode driver — ⌘⇧P only. NOT a UI scripter.
   Responsibilities (only):
     1. Hide dev surfaces (DemoDock, debug affordances)
     2. Seed required data (Mohammed snapshot pre-loaded into queue for Beat 6 match-fire)
     3. Optional presenter HUD (below the 1080p safe-area crop)
   Does NOT advance UI, does NOT script events. Real audio drives real pipeline. */

const PRESENTATION_INITIAL_QUEUE_IDS = [89]; // Mohammed pre-seed for Beat 6

function usePresentationMode() {
  const [active, setActive] = React.useState(false);
  const [hudHidden, setHudHidden] = React.useState(false);

  React.useEffect(() => {
    const onKey = (e) => {
      const isMac = /Mac/.test(navigator.platform);
      const mod = isMac ? e.metaKey : e.ctrlKey;
      if (mod && e.shiftKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault();
        setActive(v => !v);
      }
      if (active && (e.key === "h" || e.key === "H")) {
        // Only intercept H if no input is focused
        const tag = document.activeElement?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") setHudHidden(v => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  return { active, setActive, hudHidden, setHudHidden };
}

function PresenterHUD({ active, hidden, setHidden, pipelineState, onReset }) {
  if (!active || hidden) return null;
  return (
    <div className="fixed bottom-0 inset-x-0 z-40 h-6 bg-ink text-white/85 flex items-center px-3 text-[11px] font-mono gap-3 select-none">
      <span className="text-white font-semibold tracking-wide">PRESENTATION</span>
      <span className="text-white/60">dev surfaces hidden · queue seeded</span>
      <span className="ml-3 inline-flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${
          pipelineState === "busy" ? "bg-primary" :
          pipelineState === "down" ? "bg-amber" : "bg-green"
        } ${pipelineState !== "down" ? "animate-pulse" : ""}`} />
        pipeline {pipelineState}
      </span>
      <div className="flex-1" />
      <button onClick={onReset} className="px-2 py-0.5 rounded border border-white/20 hover:bg-white/10">reset</button>
      <button onClick={() => setHidden(true)} className="px-2 py-0.5 rounded border border-white/20 hover:bg-white/10" title="Hide HUD (H)">hide</button>
    </div>
  );
}

Object.assign(window, { usePresentationMode, PresenterHUD, PRESENTATION_INITIAL_QUEUE_IDS });

```

---

## `nav-app.jsx`

_ROUND 2 CANONICAL SHELL — implement against this._

```jsx
/* ============================================================================
 * KIN — nav-app.jsx (ROUND 2 CANONICAL SHELL — implement against this)
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC (Bundle 1.5):
 *
 *   STRUCTURE (don't reshape):
 *   • Layout grid: [44px nav-rail] [main flex-1 min-w-0 overflow-y-auto]
 *     [320px structlog] [320px tool-calls]. The min-w-0 on main is REQUIRED
 *     for the overflow-y-auto to work inside flex — don't remove.
 *   • Routes: 'intake' | 'queue'. Match view is a sub-state of intake
 *     (route === 'intake' && matchView === true), not a separate route.
 *     This is intentional — the match arrives in your active flow, you
 *     don't navigate to it.
 *
 *   VOICE STATE MACHINE — DO NOT CHANGE:
 *     ready → awaiting → recording → transcribing → extracting → done
 *   These six phases each map to a structlog line and a Waveform visual
 *   state. Collapsing them was tried and rejected — judges/reviewers want
 *   to see each phase as evidence the system is doing real work.
 *
 *   BEGIN/STOP BUTTONS:
 *   • These are the most-pressed buttons in the demo. Use Button size="lg"
 *     (48px). Begin is primary; Stop is destructive-secondary (red text +
 *     red border, white bg — NOT filled red, that's reserved for crisis).
 *   • Disabled state during transcribing/extracting is structural (border-
 *     line + text-muted), never opacity. See primitives.jsx adaptation note.
 *
 *   STRUCTLOG + TOOL-CALLS:
 *   • Always-visible, both sidebars, both 320px. This is the credibility
 *     surface and the most-commented-positively part of the prototype.
 *     Hiding either by default regresses Round 2 user feedback.
 *   • Bundle 1.5 viewport fix: at <1400px the right rail (640px combined)
 *     plus rail (44px) plus main padding cramps the merged-card grid.
 *     The fix is in crisis-and-translit.jsx (xl: breakpoint), not here.
 *     Do NOT reflexively collapse a sidebar on narrow viewports.
 *
 *   BUNDLE 1.5 SPLIT-VIEW (separate task, this file owns the route logic):
 *   • Add `splitMode` boolean state to this component, toggled by presenter.
 *     When true, render TWO IntakePanel instances side-by-side, each with
 *     its own intake reducer. Independent timers/phases/languages.
 *   • Per-panel device chrome: thin header strip with site label
 *     ("Tent A · Site 14" / "Tent B · Site 22"), device id, and a subtle
 *     hairline accent ONLY:
 *       Tent A: oklch(0.92 0.02 75)   /* warm neutral */
 *       Tent B: oklch(0.92 0.015 220) /* cool neutral */
 *     NOT primary color. Stays in the warm-paper system.
 *   • Single shared structlog/tool-calls — events get [A]/[B] mono prefix.
 *
 *   DEMO DOCK:
 *   • Bottom-floating, hidden under presentation mode. Shows step buttons
 *     1–9, language toggle, reset. This is dev-facing and should be removed
 *     in production builds — gate behind NODE_ENV === 'development' or a
 *     ?dev=1 query param when you port.
 *
 *   KEYBOARD SHORTCUTS (preserve):
 *     1–9       jump demo step
 *     ⌘⇧P       presentation mode
 *     ⌘B        toggle structlog rail (dev only)
 *     ⌘⇧B       toggle tool-calls rail (dev only)
 *     ?         help overlay
 *     Esc       dismiss crisis / close help / exit presentation
 * ============================================================================
 * Navigation Shell — Round 2 IA prototype. Demonstrates:
   - Thin 44px nav rail (Intake / Queue), no command palette
   - Voice panel with extended state machine (ready → awaiting → recording → transcribing → extracting → done)
   - Begin/Stop as first-class buttons, large + accessible
   - Always-visible structlog + tool-calls sidebars (credibility surfaces)
   - Auto-route on match_proposed (Beat 6 behavior)
   - Crisis as elevated layer (Beat 7)
   - ⌘⇧P presentation mode: hides DemoDock + seeds Mohammed
   - Coach-mark on first load
   - Inter-record toast on commit
*/

const { useState, useEffect, useRef, useCallback, useMemo } = React;

// ---- Top bar ------------------------------------------------------------
function TopBar({ statusLabel, statusTone, queuedCount, onQueueChip, lang, setLang }) {
  return (
    <header className="sticky top-0 z-20 bg-paper/95 backdrop-blur border-b border-line">
      <div className="px-5 h-14 flex items-center gap-5">
        <div className="text-[16px] font-semibold tracking-[-0.01em] text-ink">KIN</div>
        <div className="hidden md:block h-4 w-px bg-hair" />
        <div className="hidden md:block text-[13px] text-muted">Family reunification intake</div>

        <div className="hidden lg:flex items-center gap-3 ml-2">
          <div className="text-[13px] text-muted">Session <span className="font-mono text-ink">#147</span></div>
          <div className="h-4 w-px bg-hair" />
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${statusTone === "amber" ? "bg-amber" : statusTone === "red" ? "bg-red" : "bg-green"}`} />
            <span className="text-[13px] text-ink">{statusLabel}</span>
          </div>
        </div>

        <div className="flex-1" />

        <button onClick={onQueueChip} className="hidden sm:inline-flex items-center gap-1.5 h-7 px-2.5 text-[13px] font-medium border border-line rounded-kin bg-white hover:bg-subtle text-ink transition-colors">
          <IconLock size={12} className="text-muted" />
          <span className="font-medium">{queuedCount}</span>
          <span className="text-muted">queued locally</span>
        </button>

        <div className="flex items-center border border-line rounded-kin overflow-hidden">
          <span className="px-2 text-muted"><IconLanguages size={14} /></span>
          {["EN","ES","AR","FA"].map(code => {
            const k = code.toLowerCase();
            const active = lang === k;
            return (
              <button key={code} onClick={() => setLang(k)} aria-pressed={active}
                className={`h-9 px-2.5 text-[13px] font-medium border-l border-line transition-colors ${
                  active ? "bg-primary text-white" : "bg-white text-ink hover:bg-subtle"
                }`}>{code}</button>
            );
          })}
        </div>
      </div>
    </header>
  );
}

// ---- Voice panel with extended state machine ----------------------------
const VOICE_COPY = {
  ready:        { en: "Ready to begin intake", es: "Listo para comenzar", ar: "جاهز للبدء", fa: "آماده شروع" },
  awaiting:     { en: "Listening — speak when ready", es: "Escuchando — hable cuando esté listo", ar: "نستمع — تحدّث عندما تكون مستعدًا", fa: "در حال شنیدن — هر زمان آماده‌اید" },
  recording:    { en: "Recording", es: "Grabando", ar: "تسجيل", fa: "در حال ضبط" },
  transcribing: { en: "Transcribing audio…", es: "Transcribiendo audio…", ar: "تفريغ الصوت…", fa: "رونویسی صدا…" },
  extracting:   { en: "Structuring record…", es: "Estructurando registro…", ar: "هيكلة السجل…", fa: "ساختاردهی پرونده…" },
  done:         { en: "Intake complete", es: "Entrevista completa", ar: "اكتملت المقابلة", fa: "مصاحبه کامل شد" },
};
const BEGIN_LABEL = { en: "Begin", es: "Comenzar", ar: "ابدأ", fa: "شروع" };
const STOP_LABEL  = { en: "Stop",  es: "Detener",  ar: "إيقاف", fa: "توقف" };

function VoicePanel({ phase, lang, onBegin, onStop, elapsed }) {
  const copy = (VOICE_COPY[phase] || VOICE_COPY.ready);
  const label = copy[lang] || copy.en;
  const rtl = lang === "ar" || lang === "fa";
  const wave = phase === "recording" ? "recording" : phase === "transcribing" || phase === "extracting" ? "processing" : "idle";
  const showStop = phase === "recording" || phase === "transcribing" || phase === "extracting";

  return (
    <div className="bg-card border border-line rounded-kin-lg">
      <div className="px-5 py-4 border-b border-hair flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={`w-9 h-9 rounded-kin border flex items-center justify-center ${
            phase === "recording" ? "border-red/40 text-red bg-red-soft" :
            phase === "transcribing" || phase === "extracting" ? "border-line text-primary bg-primary-soft" :
            phase === "awaiting" ? "border-primary/30 text-primary bg-primary-soft" :
            "border-line text-ink"
          }`}>
            <IconMic size={16} />
          </div>
          <div>
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Voice intake</div>
            <div className={`text-[15px] text-ink mt-0.5 ${rtl ? "rtl" : ""}`} aria-live="polite">{label}</div>
          </div>
        </div>
        <div className="font-mono text-[14px] text-muted tabular-nums">
          {String(Math.floor(elapsed/60)).padStart(2,"0")}:{String(elapsed%60).padStart(2,"0")}
        </div>
      </div>

      <div className="px-5 py-5 flex items-center gap-5">
        <div className="flex-1">
          <Waveform state={wave} bars={42} />
        </div>
        {phase === "ready" || phase === "done" ? (
          <Button variant="primary" size="lg" icon={<IconMic size={18} />} onClick={onBegin}
            className="!h-12">{BEGIN_LABEL[lang] || BEGIN_LABEL.en}</Button>
        ) : showStop ? (
          <Button variant="danger" size="lg" icon={<IconPause size={16} />} onClick={onStop}
            className="!h-12">{STOP_LABEL[lang] || STOP_LABEL.en}</Button>
        ) : null}
      </div>
    </div>
  );
}

// ---- Match toast → auto-route -------------------------------------------
function MatchToast({ open, candidate, onOpen, onDismiss }) {
  React.useEffect(() => {
    if (!open) return;
    const t = setTimeout(onOpen, 1500); // auto-route after 1.5s
    return () => clearTimeout(t);
  }, [open, onOpen]);
  if (!open) return null;
  return (
    <div className="fixed bottom-4 right-4 z-30 w-[360px] bg-card border border-green/40 rounded-kin-lg overflow-hidden"
         style={{ boxShadow: "0 1px 2px rgba(20,30,40,0.04), 0 4px 12px -2px rgba(20,30,40,0.10)" }}>
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-[oklch(0.38_0.1_155)]">
          <IconLink size={12} /> Match candidate found
        </div>
        <div className="mt-1 text-[15px] font-medium text-ink">{candidate.name}</div>
        <div className="text-[12px] text-muted mt-0.5">#{candidate.id} · auto-opening in 1.5s</div>
      </div>
      <div className="border-t border-hair bg-subtle/60 px-3 py-2 flex justify-end gap-2">
        <button onClick={onDismiss} className="h-8 px-2.5 text-[13px] text-ink hover:bg-subtle rounded-kin">Dismiss</button>
        <button onClick={onOpen} className="h-8 px-3 text-[13px] font-medium bg-primary text-white rounded-kin border border-primary hover:bg-primary-2">Open match</button>
      </div>
    </div>
  );
}

// ---- Main App ------------------------------------------------------------
function App() {
  const [route, setRoute]     = useState("intake");
  const [phase, setPhase]     = useState("ready");
  const [lang, setLang]       = useState("en");
  const [record, setRecord]   = useState(INITIAL_RECORD);
  const [crisisOpen, setCrisisOpen] = useState(false);
  const [matchToast, setMatchToast] = useState(null);
  const [matchView, setMatchView]   = useState(null); // null | 'split' | 'linking' | 'merged'
  const [openedRecord, setOpenedRecord] = useState(null); // when reopened from queue
  const [elapsed, setElapsed] = useState(0);
  const [running, setRunning] = useState(false);
  const [structlog, setStructlog] = useState([]);
  const [toolCalls, setToolCalls] = useState([]);
  const [heartbeat, setHeartbeat] = useState("idle");
  const [justPopulated, setJustPopulated] = useState(null);
  const startedAtRef = useRef(null);
  const eidRef = useRef(0);
  const cidRef = useRef(0);

  const presentation = usePresentationMode();
  const coach = useCoachMark(presentation.active);

  // Seeded queue (Mohammed already there for Beat 6)
  const [queue, setQueue] = useState(SEEDED_RECORDS);

  // Timer
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [running]);

  const tMs = () => startedAtRef.current ? performance.now() - startedAtRef.current : 0;

  const logEvent = (ev) => {
    const id = ++eidRef.current;
    setStructlog(prev => [...prev, { id, tMs: tMs(), ...ev }]);
  };
  const startCall = (name, args) => {
    const id = ++cidRef.current;
    setToolCalls(prev => [...prev, { id, name, args, status: "started", tMs: tMs() }]);
    setHeartbeat("busy");
    return id;
  };
  const finishCall = (id, result) => {
    setToolCalls(prev => prev.map(c => c.id === id ? { ...c, result, status: "ok" } : c));
    setHeartbeat("idle");
  };

  const minor = record.age && parseInt(record.age,10) > 0 && parseInt(record.age,10) < 18;

  const reset = () => {
    setPhase("ready");
    setRecord(INITIAL_RECORD);
    setElapsed(0); setRunning(false);
    setStructlog([]); setToolCalls([]);
    setMatchToast(null); setMatchView(null);
    setCrisisOpen(false); setHeartbeat("idle");
    setOpenedRecord(null);
  };

  // Begin: phase walk simulating real pipeline (warm: ~4.5s steps).
  // In real KIN, these are fired by SSE; here we simulate the same shape.
  const onBegin = () => {
    if (phase !== "ready" && phase !== "done") return;
    reset();
    startedAtRef.current = performance.now();
    setRunning(true);
    setPhase("awaiting");
    logEvent({ name: "session.start", subtitle: "consent confirmed by aid worker", kvs: { session_id: 147 } });

    setTimeout(() => {
      setPhase("recording");
      logEvent({ name: "audio.capture.open", subtitle: "microphone stream opened", status: "started" });
    }, 700);

    // Recording → Stop happens automatically here for the demo simulation
    setTimeout(() => onStop(), 2200);
  };

  const onStop = () => {
    setPhase("transcribing");
    const c1 = startCall("whisper.transcribe", { lang_hint: lang, chunks: 6 });
    logEvent({ name: "asr.transcribe", subtitle: "Whisper streaming…", status: "started" });
    setTimeout(() => {
      finishCall(c1, "stream_complete");
      logEvent({ name: "asr.transcribe", subtitle: "transcript ready · 18 tokens" });
      setPhase("extracting");

      // Run the populate sequence (Beat 5)
      const SEQ = [
        { d: 400, key: "name", value: "Carlos Rivera Méndez", call: { name: "extract_name", args: { text: "…mi padre Carlos Rivera Méndez…" }, result: "Carlos Rivera Méndez" } },
        { d: 800, key: "age",  value: "62", call: { name: "extract_age", args: { context: "padre · 62 años" }, result: 62 } },
        { d: 1100, key: "relationship", value: "Father", call: { name: "extract_relationship", args: {}, result: "father" } },
        { d: 1500, key: "lastSeenLocation", value: "Tapachula bus terminal", call: { name: "extract_location", args: {}, result: "Tapachula, MX" } },
        { d: 1800, key: "lastSeenDate", value: "Approx. 9 days ago", call: { name: "normalize_date", args: { input: "hace nueve días" }, result: "-9d" } },
        { d: 2100, key: "circumstance", value: "Separated during transfer at terminal", call: { name: "extract_circumstance", args: {} } },
        { d: 2500, key: "physicalDesc", value: "Approx. 170 cm · gray hair, full beard", call: { name: "extract_distinguishing_marks", args: {} } },
        { d: 2900, key: "features", value: "Wears wire-frame glasses · limp in right leg", call: { name: "update_rfl_record", args: { record_id: 147 }, result: "queued_local" } },
      ];
      SEQ.forEach(s => {
        setTimeout(() => {
          const cid = startCall(s.call.name, s.call.args);
          setRecord(r => ({ ...r, [s.key]: s.value }));
          setJustPopulated(s.key);
          setTimeout(() => setJustPopulated(j => j === s.key ? null : j), 2500);
          setTimeout(() => finishCall(cid, s.call.result ?? "ok"), 250);
        }, s.d);
      });

      // Commit + match check
      setTimeout(() => {
        setPhase("done");
        logEvent({ name: "record.commit", subtitle: "queued for sync", kvs: { record_id: 147 } });
        setRunning(false);

        // Auto-match: scan queue, find Mohammed pre-seed → match_proposed
        // (For the demo flow we point at Mohammed since he's seeded.)
        const cid = startCall("fuzzy_match", { against: "queue", n: queue.length });
        setTimeout(() => {
          finishCall(cid, "candidate=#089");
          const cid2 = startCall("transliteration_comparison", { source: "محمد الصالح", variants: ["Mohammed","Mohamad"] });
          setTimeout(() => {
            finishCall(cid2, "match_confidence=high");
            logEvent({ name: "match_proposed", subtitle: "candidate #089 · auto-routing", status: "warn", kvs: { record_a: 147, record_b: 89 } });
            setMatchToast({ id: 89, name: "Mohammed Al-Saleh" });
          }, 600);
        }, 500);
      }, 3400);
    }, 1200);
  };

  const openMatchView = () => {
    setMatchToast(null);
    setMatchView("split");
    setTimeout(() => setMatchView("linking"), 600);
    setTimeout(() => setMatchView("merged"), 1600);
  };

  // Simulate crisis (would normally be triggered by safety classifier)
  const onSimulateCrisis = () => {
    if (phase === "ready") {
      setLang("ar");
      startedAtRef.current = performance.now();
      setRunning(true);
    }
    logEvent({ name: "safety.classifier", subtitle: "distress signal detected", status: "warn" });
    const cid = startCall("escalate_crisis", { signal: "distress_keyword", lang });
    setTimeout(() => finishCall(cid, "referral_card_elevated"), 400);
    setCrisisOpen(true);
  };

  const onOpenRecord = (r) => {
    setOpenedRecord(r);
    setRoute("intake");
  };

  const queuedChipCount = queue.length;
  const statusLabel = openedRecord ? "Viewing previous record"
    : minor && phase !== "done" ? "Incomplete — Minor Protection Required"
    : phase === "done" ? "Intake complete · queued for sync"
    : phase === "ready" ? "Awaiting begin"
    : "Active intake";
  const statusTone = openedRecord ? "primary" : (minor && phase !== "done") ? "amber" : "green";

  // Build a synthetic record view for opened queue records
  const displayRecord = openedRecord ? {
    name: openedRecord.name,
    nameNative: openedRecord.native, nameNativeRtl: openedRecord.rtl,
    age: openedRecord.age, relationship: "—", language: "—",
    lastSeenLocation: openedRecord.summary, lastSeenDate: openedRecord.updated,
    circumstance: openedRecord.summary,
    physicalDesc: "—", features: "—",
    guardian: { guardianPresent: "Yes", cpConsent: "Yes", cmKnown: "Yes", referralStatus: "Routed" },
  } : record;

  const displayMinor = openedRecord ? openedRecord.status === "minor" : minor;

  return (
    <div className="h-screen flex flex-col">
      <TopBar
        statusLabel={statusLabel}
        statusTone={statusTone}
        queuedCount={queuedChipCount}
        onQueueChip={() => setRoute("queue")}
        lang={lang}
        setLang={setLang}
      />

      <div className="flex-1 flex min-h-0">
        <NavRail route={route} setRoute={setRoute} queuedCount={queuedChipCount} syncOk={true} />

        <main className="flex-1 min-w-0 overflow-y-auto">
          <CoachMark show={coach.show} onDismiss={coach.dismiss} />

          {route === "intake" ? (
            matchView ? (
              <div className="px-6 py-6">
                <TransliterationMatch phase={matchView} onBack={() => { setMatchView(null); setRoute("queue"); }} />
              </div>
            ) : (
              <div className="max-w-[860px] mx-auto px-6 py-6">
                <div className="mb-5">
                  <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Intake</div>
                  <h1 className="text-[24px] font-semibold text-ink mt-0.5 tracking-[-0.01em]">
                    {openedRecord ? `Record · ${openedRecord.name}` : "Family separation report"}
                  </h1>
                </div>

                {openedRecord && <RecordCardReadOnlyBanner onResume={() => { setOpenedRecord(null); reset(); }} />}

                {!openedRecord && (
                  <div className="mb-5">
                    <VoicePanel phase={phase} lang={lang} onBegin={onBegin} onStop={onStop} elapsed={elapsed} />
                  </div>
                )}

                <RecordCard
                  record={displayRecord}
                  minor={displayMinor}
                  justPopulatedKey={justPopulated}
                  disabled={crisisOpen}
                />
              </div>
            )
          ) : (
            <QueueView records={queue} onOpen={onOpenRecord} onNew={() => { setRoute("intake"); setOpenedRecord(null); reset(); }} />
          )}
        </main>

        {/* Always-visible credibility surfaces */}
        <StructlogSidebar events={structlog} heartbeat={heartbeat} since="11:02" />
        <ToolCallsSidebar calls={toolCalls} />
      </div>

      {crisisOpen && (
        <CrisisReferralCard
          lang={lang}
          onResolved={() => { setCrisisOpen(false); logEvent({ name: "crisis.resolve", subtitle: "referral provided" }); }}
          onDeEscalated={() => { setCrisisOpen(false); logEvent({ name: "crisis.resolve", subtitle: "de-escalated" }); }}
        />
      )}

      {matchToast && (
        <MatchToast open={!!matchToast} candidate={matchToast} onOpen={openMatchView} onDismiss={() => setMatchToast(null)} />
      )}

      <PresenterHUD
        active={presentation.active}
        hidden={presentation.hudHidden}
        setHidden={presentation.setHudHidden}
        pipelineState={heartbeat}
        onReset={reset}
      />

      {/* Dev demo dock — only when ?dev=1, never in presentation */}
      {(typeof window !== "undefined" && new URLSearchParams(location.search).get("dev") === "1" && !presentation.active) && (
        <div className="fixed bottom-3 left-[60px] z-30 bg-card border border-line rounded-kin-lg px-3 py-2.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-muted mb-2">Demo (dev only)</div>
          <div className="flex flex-wrap gap-1.5">
            <Button size="sm" variant="primary" icon={<IconPlay size={14} />} onClick={onBegin}>Run intake</Button>
            <Button size="sm" variant="secondary" icon={<IconAlert size={14} />} onClick={onSimulateCrisis}>Trigger crisis</Button>
            <Button size="sm" variant="ghost" icon={<IconRotate size={14} />} onClick={reset}>Reset</Button>
          </div>
        </div>
      )}

      {/* Bottom-right legend */}
      <div className="fixed bottom-3 right-[340px] z-10 flex items-center gap-2 text-[11px] text-muted bg-paper/80 backdrop-blur border border-hair rounded-kin px-2 py-1">
        <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded border border-line bg-white text-ink">⌘⇧P</kbd>
        <span>presentation</span>
      </div>
    </div>
  );
}

const INITIAL_RECORD = {
  name: "", nameVariants: null, nameNative: null, nameNativeRtl: false,
  age: "", relationship: "", language: "Spanish (Latin America)",
  lastSeenLocation: "", lastSeenLocationSource: "", lastSeenLocationRtl: false,
  lastSeenDate: "", circumstance: "",
  physicalDesc: "", features: "",
  guardian: { guardianPresent: "", cpConsent: "", cmKnown: "", referralStatus: "" },
};

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

```

---

## `app.jsx`

_ROUND 1 reference shell. Kept for A/B; do not delete._

```jsx
/* ============================================================================
 * KIN — app.jsx (ROUND 1 SHELL — kept for reference; Round 2 is nav-app.jsx)
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • This is the Round 1 single-screen prototype. CC should implement
 *     against nav-app.jsx (Round 2 IA), but this file documents:
 *       - the original demo sequencer (kept for Beat 1–5 narration timing)
 *       - the keyboard shortcut map (1–9 jumps demo step, ⌘K palette,
 *         ⌘⇧P presentation, ? help)
 *       - the reducer-based intake state shape, which is the source of
 *         truth even in Round 2
 *   • DO NOT MERGE this file into nav-app.jsx; they are intentionally
 *     parallel so the Round 1 contract stays intact for QA regression.
 *   • DEMO_SCRIPT timings are tuned for live narration. If your real audio
 *     pipeline returns faster than ~800ms per phase, gate phase advancement
 *     on a min-duration so the structlog reads naturally.
 *   • Top bar: title + intake-id mono + status pills. Don't add user
 *     account / logout in this build — auth flow is out of scope.
 *   • Reducer actions are the integration contract. Match these names
 *     when wiring real services:
 *       BEGIN, STOP, TRANSCRIBED, EXTRACTED, MINOR_DETECTED,
 *       CRISIS_FIRE, CRISIS_DISMISS, MATCH_FOUND, RESET
 * ============================================================================
 * KIN — app shell. Top bar, main layout, demo sequencer, keyboard shortcuts. */

const { useState, useEffect, useReducer, useRef, useCallback, useMemo } = React;

// ---------- Demo script ---------------------------------------------------
// Each step mutates the record object. The sequencer runs these in order against
// a wall clock to simulate SSE streaming into React state.
const DEMO_STEPS = [
  { at: 1000, state: "recording",  trace: { name: "audio_stream.open",        args: { lang_hint: "es" } } },
  { at: 3000, state: "processing", trace: { name: "asr.transcribe",            args: { chunks: 4 }, result: "stream_complete" } },
  { at: 4000, populate: "name",     value: "María Elena Torres",
              trace: { name: "extract_name", args: { text: "…mi hija María Elena Torres…" }, result: "María Elena Torres" } },
  { at: 5000, populate: "age",      value: "8",
              trace: { name: "flag_minor",   args: { age: 8 }, result: "protection_required" } },
  { at: 6000, populate: "relationship", value: "Daughter",
              trace: { name: "extract_relationship", args: {}, result: "daughter" } },
  { at: 7000, populate: "lastSeenLocation", value: "Near Tapachula bus terminal",
              lastSeenLocationSource: "Cerca de la terminal de autobuses de Tapachula",
              trace: { name: "extract_location", args: {}, result: "Tapachula, MX" } },
  { at: 7800, populate: "lastSeenDate",    value: "Approx. 11 days ago",
              trace: { name: "normalize_date", args: { input: "hace como once días" }, result: "-11d" } },
  { at: 8400, populate: "circumstance",    value: "Separated during crowd surge at transit point",
              trace: { name: "extract_circumstance", args: {} } },
  { at: 9200, populate: "physicalDesc",    value: "Height approx. 120 cm · brown hair, shoulder length",
              trace: { name: "extract_distinguishing_marks", args: {} } },
  { at: 9800, populate: "features",        value: "Small crescent scar above left eyebrow · wearing red shoes",
              trace: { name: "update_rfl_record", args: { record_id: "147" }, result: "queued_local" } },
];

const INITIAL_RECORD = {
  name: "", nameVariants: null, nameNative: null, nameNativeRtl: false,
  age: "", relationship: "", language: "Spanish (Latin America)",
  lastSeenLocation: "", lastSeenLocationSource: "", lastSeenLocationRtl: false,
  lastSeenDate: "", circumstance: "",
  physicalDesc: "", features: "",
  guardian: { guardianPresent: "", cpConsent: "", cmKnown: "", referralStatus: "" },
};

// ---------- Top bar -------------------------------------------------------
function TopBar({ sessionLabel, statusLabel, statusTone, queued, lang, setLang }) {
  return (
    <header className="sticky top-0 z-20 bg-paper/95 backdrop-blur border-b border-line">
      <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center gap-6">
        {/* Wordmark — restrained, structural. No SVG/logo, wordmark only. */}
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-kin border border-ink/70 flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-primary" />
          </div>
          <div className="text-[16px] font-semibold tracking-[-0.01em] text-ink">KIN</div>
          <div className="hidden md:block h-4 w-px bg-hair" />
          <div className="hidden md:block text-[13px] text-muted">Family reunification intake</div>
        </div>

        {/* Session label */}
        <div className="hidden lg:flex items-center gap-3 ml-2">
          <div className="text-[13px] text-muted">Session <span className="font-mono text-ink">#147</span></div>
          <div className="h-4 w-px bg-hair" />
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${statusTone === "amber" ? "bg-amber" : statusTone === "red" ? "bg-red" : "bg-green"}`} />
            <span className="text-[13px] text-ink">{statusLabel}</span>
          </div>
        </div>

        <div className="flex-1" />

        {/* Sync state — NOT an "OFFLINE" banner (Principle 4). */}
        <div className="hidden sm:flex items-center gap-2">
          <Chip icon={<IconLock size={12} />} tone="neutral">
            <span className="font-medium">{queued}</span>
            <span className="text-muted">&nbsp;records queued locally</span>
          </Chip>
        </div>

        {/* Language switcher — affects displaced-person-facing surfaces only */}
        <div className="flex items-center border border-line rounded-kin overflow-hidden">
          <span className="px-2 text-muted"><IconLanguages size={14} /></span>
          {["EN", "ES", "AR", "FA"].map((code, i, arr) => {
            const k = code.toLowerCase();
            const active = lang === k;
            return (
              <button
                key={code}
                onClick={() => setLang(k)}
                className={`h-9 px-2.5 text-[13px] font-medium border-l border-line transition-colors ${
                  active ? "bg-primary text-white" : "bg-white text-ink hover:bg-subtle"
                }`}
                aria-pressed={active}
                title={`Person-facing prompts: ${code}`}
              >
                {code}
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
}

// ---------- Voice-note affordance ----------------------------------------
function VoicePanel({ phase, lang, onBegin, elapsedSec }) {
  // phase: 'ready' | 'recording' | 'processing' | 'done'
  const waveState =
    phase === "recording" ? "recording" :
    phase === "processing" ? "processing" :
    "idle";

  const readyCopy = {
    en: "Ready to begin intake — explain to the person in front of you what KIN does, then press Begin.",
    es: "Listo para comenzar la entrevista — explique a la persona frente a usted lo que hace KIN, y luego pulse Comenzar.",
    ar: "جاهز لبدء المقابلة — اشرح للشخص أمامك ما يفعله KIN، ثم اضغط «ابدأ».",
    fa: "آمادهٔ شروع مصاحبه — برای شخص مقابل توضیح دهید KIN چه می‌کند، سپس «شروع» را فشار دهید.",
  }[lang] || readyCopyFallback;
  const beginLabel = { en: "Begin", es: "Comenzar", ar: "ابدأ", fa: "شروع" }[lang] || "Begin";
  const rtl = lang === "ar" || lang === "fa";

  return (
    <div className="bg-card border border-line rounded-kin-lg">
      <div className="px-5 py-4 border-b border-hair flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={`w-8 h-8 rounded-kin border flex items-center justify-center ${
            phase === "recording" ? "border-red/40 text-red bg-red-soft" :
            phase === "processing" ? "border-line text-muted" :
            "border-line text-ink"
          }`}>
            <IconMic size={16} />
          </div>
          <div>
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Voice intake</div>
            <div className="text-[15px] text-ink mt-0.5">
              {phase === "ready"      && "Not recording"}
              {phase === "recording"  && <span className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-red animate-pulse" />Recording — speaker is giving testimony</span>}
              {phase === "processing" && "Listening completed — structuring record…"}
              {phase === "done"       && "Intake complete"}
            </div>
          </div>
        </div>
        <div className="font-mono text-[14px] text-muted tabular-nums">
          {formatElapsed(elapsedSec)}
        </div>
      </div>

      <div className="px-5 py-5">
        {phase === "ready" ? (
          <div className={`flex flex-col sm:flex-row sm:items-center gap-4 ${rtl ? "rtl" : ""}`}>
            <div className="flex-1 min-w-0">
              <div className="text-[17px] text-ink leading-relaxed" style={{ textWrap: "pretty" }}>
                {readyCopy}
              </div>
              <div className="mt-2 text-[13px] text-muted flex items-center gap-1.5">
                <IconInfo size={13} /> Consent to begin is logged with this record.
              </div>
            </div>
            <Button variant="primary" size="lg" icon={<IconMic size={18} />} onClick={onBegin}>
              {beginLabel}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-5">
            <div className="flex-1"><Waveform state={waveState} bars={42} /></div>
            {phase === "processing" && (
              <Chip icon={<IconSparkle size={12} />} tone="primary">Structuring</Chip>
            )}
            {phase === "done" && (
              <Chip icon={<IconCheck size={12} />} tone="green">Intake complete</Chip>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
const readyCopyFallback = "Ready to begin intake — explain what KIN does, then press Begin.";
function formatElapsed(s) {
  const m = Math.floor(s / 60); const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

// ---------- Intake timer + baseline --------------------------------------
function IntakeTimer({ seconds, running }) {
  const baseline = 42 * 60; // 42:00
  const amberThreshold = baseline * 0.9;
  const tone =
    seconds > baseline ? "red" :
    seconds > amberThreshold ? "amber" :
    "green";
  const toneCls = {
    green: "text-green",
    amber: "text-[oklch(0.42_0.12_75)]",
    red:   "text-red",
  }[tone];
  const dot = { green: "bg-green", amber: "bg-amber", red: "bg-red" }[tone];

  return (
    <div className="border border-line bg-card rounded-kin-lg px-4 py-3 min-w-[240px]">
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted">
        Median baseline · 42:00
      </div>
      <div className="flex items-baseline justify-between mt-0.5">
        <div className={`font-mono tabular-nums text-[28px] font-medium ${toneCls}`}>
          {formatElapsed(seconds)}
        </div>
        <div className="flex items-center gap-1.5 text-[12px] text-muted">
          <span className={`w-1.5 h-1.5 rounded-full ${dot} ${running ? "animate-pulse" : ""}`} />
          {running ? "Live" : "Paused"}
        </div>
      </div>
      <div className="text-[11px] text-muted mt-1">Nolting et al., 2019 (registration intake)</div>
    </div>
  );
}

// ---------- Minor-detected header strip ----------------------------------
function MinorStrip({ complete }) {
  // Persistent, not dismissible. Clears only when guardian subsection complete.
  return (
    <div className="bg-amber-soft border border-amber/40 rounded-kin px-4 py-3 flex items-start gap-3">
      <div className="shrink-0 w-8 h-8 rounded-kin bg-white border border-amber/40 text-[oklch(0.42_0.12_75)] flex items-center justify-center">
        <IconShield size={16} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[15px] font-semibold text-[oklch(0.32_0.12_75)]">
          Child protection routing required — under 18 detected
        </div>
        <div className="text-[13.5px] text-[oklch(0.42_0.08_75)] mt-0.5">
          {complete
            ? "Guardian & Protection section complete. Clearing flag…"
            : "Record will remain flagged Incomplete — Minor Protection Required until the Guardian & Protection Status sub-section is complete."}
        </div>
      </div>
      <div className="hidden sm:block">
        <Chip icon={<IconArrowRight size={12} />} tone="amber">Below: Guardian & Protection</Chip>
      </div>
    </div>
  );
}

// ---------- Keyboard hint ------------------------------------------------
function ShortcutHint({ isMac }) {
  return (
    <div className="fixed bottom-3 right-3 z-10 flex items-center gap-1.5 text-[12px] text-muted bg-paper/80 backdrop-blur border border-hair rounded-kin px-2 py-1">
      <kbd className="font-mono text-[11px] px-1.5 py-0.5 rounded border border-line bg-white text-ink">{isMac ? "⌘" : "Ctrl"}</kbd>
      <kbd className="font-mono text-[11px] px-1.5 py-0.5 rounded border border-line bg-white text-ink">D</kbd>
      <span>developer view</span>
    </div>
  );
}

// ---------- Demo control dock -------------------------------------------
function DemoDock({ visible, onStart, onReset, onMatch, onCrisis, phase, view, disabled }) {
  if (!visible) return null;
  return (
    <div className="fixed bottom-3 left-3 z-30 bg-card border border-line rounded-kin-lg shadow-elevated px-3 py-2.5 w-[min(440px,calc(100%-24px))]">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Demo controls</div>
        <div className="text-[11px] text-muted font-mono">⌘.&nbsp;to hide</div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" variant="primary" icon={<IconPlay size={14} />}
                onClick={onStart} disabled={phase !== "ready" || view !== "intake"}>
          Start demo
        </Button>
        <Button size="sm" variant="secondary" icon={<IconLink size={14} />}
                onClick={onMatch}>
          Simulate match
        </Button>
        <Button size="sm" variant="secondary" icon={<IconAlert size={14} />}
                onClick={onCrisis}>
          Simulate crisis
        </Button>
        <Button size="sm" variant="ghost" icon={<IconRotate size={14} />}
                onClick={onReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}

// ---------- Main App ------------------------------------------------------
function App() {
  const [record, setRecord]         = useState(INITIAL_RECORD);
  const [phase, setPhase]           = useState("ready"); // ready | recording | processing | done
  const [view, setView]             = useState("intake"); // intake | match
  const [matchPhase, setMatchPhase] = useState("split");  // split | linking | merged
  const [lang, setLang]             = useState("en");
  const [crisisOpen, setCrisisOpen] = useState(false);
  const [devMode, setDevMode]       = useState(false);
  const [demoDockVisible, setDemoDockVisible] = useState(true);
  const [justPopulated, setJustPopulated]     = useState(null);
  const [timerSec, setTimerSec]     = useState(0);
  const [timerRunning, setTimerRunning] = useState(false);
  const [calls, setCalls]           = useState([]);
  const [highlightedCall, setHighlightedCall] = useState(null);
  const demoStartRef = useRef(null);
  const callIdRef = useRef(0);

  const isMac = useMemo(() => typeof navigator !== "undefined" && /Mac/.test(navigator.platform), []);

  // ----- Trace logging helper
  const logCall = useCallback((call, tOffset = 0) => {
    const id = ++callIdRef.current;
    const entry = { id, t: tOffset, ...call };
    setCalls(prev => [...prev, entry]);
    if (call.highlight) {
      setHighlightedCall(id);
      setTimeout(() => setHighlightedCall(h => (h === id ? null : h)), 1200);
    }
    return id;
  }, []);

  // ----- Keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      const mod = isMac ? e.metaKey : e.ctrlKey;
      if (mod && (e.key === "d" || e.key === "D")) {
        e.preventDefault();
        setDevMode(v => !v);
      }
      if (mod && e.key === ".") {
        e.preventDefault();
        setDemoDockVisible(v => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isMac]);

  // ----- Intake timer
  useEffect(() => {
    if (!timerRunning) return;
    const t = setInterval(() => setTimerSec(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [timerRunning]);

  // ----- Derived state
  const minor = record.age && parseInt(record.age, 10) > 0 && parseInt(record.age, 10) < 18;
  const guardianFilled = minor && Object.values(record.guardian).every(v => v && v.trim());
  const statusLabel = minor && !guardianFilled
    ? "Incomplete — Minor Protection Required"
    : phase === "done" ? "Intake complete · queued for sync" : "Active intake";
  const statusTone = minor && !guardianFilled ? "amber" : phase === "done" ? "green" : "green";

  const segments = [
    { key: "name", label: "Name", filled: !!record.name },
    { key: "age",  label: "Age",  filled: !!record.age },
    { key: "rel",  label: "Relationship", filled: !!record.relationship },
    { key: "ls",   label: "Last seen", filled: !!(record.lastSeenLocation && record.lastSeenDate) },
    { key: "marks",label: "Marks", filled: !!(record.physicalDesc && record.features) },
    ...(minor ? [{ key: "guard", label: "Guardian/CP", filled: !!guardianFilled }] : []),
  ];

  // ----- Demo sequencer
  const runDemo = () => {
    // schedule steps relative to wall clock
    demoStartRef.current = performance.now();
    setPhase("recording");
    setTimerRunning(true);
    logCall({ name: "session.start", args: { session_id: 147 }, result: "ok" }, 0);

    DEMO_STEPS.forEach((step) => {
      setTimeout(() => {
        const t = performance.now() - demoStartRef.current;
        if (step.state) setPhase(step.state);
        if (step.populate) {
          setRecord(prev => {
            const next = { ...prev };
            next[step.populate] = step.value;
            if (step.lastSeenLocationSource) {
              next.lastSeenLocationSource = step.lastSeenLocationSource;
            }
            return next;
          });
          setJustPopulated(step.populate);
          setTimeout(() => setJustPopulated(j => j === step.populate ? null : j), 2500);
        }
        if (step.trace) logCall(step.trace, t);
      }, step.at);
    });

    // Final: set done
    const lastAt = DEMO_STEPS[DEMO_STEPS.length - 1].at;
    setTimeout(() => {
      setPhase("done");
      logCall({ name: "record.commit", args: { record_id: 147, status: "queued_local" }, result: "ok" },
              performance.now() - demoStartRef.current);
    }, lastAt + 600);
  };

  const onBegin = () => {
    if (phase !== "ready") return;
    logCall({ name: "consent.logged", args: { method: "aid_worker_confirmation" }, result: "ok" }, 0);
    runDemo();
  };

  const onReset = () => {
    setRecord(INITIAL_RECORD);
    setPhase("ready");
    setView("intake");
    setMatchPhase("split");
    setCrisisOpen(false);
    setTimerSec(0);
    setTimerRunning(false);
    setCalls([]);
    setJustPopulated(null);
  };

  const onSimulateMatch = () => {
    setView("match");
    setMatchPhase("split");
    const t0 = performance.now();
    logCall({ name: "fuzzy_match", args: { a: "Mohammed Al-Saleh", b: "Mohamad Alsaleh" }, result: "candidate" }, 0);
    setTimeout(() => {
      logCall({ name: "transliteration_comparison",
                args: { source: "محمد الصالح", variants: ["Mohammed", "Mohamad"] },
                result: "match_confidence=high",
                highlight: true }, performance.now() - t0);
      setMatchPhase("linking");
    }, 400);
    setTimeout(() => {
      logCall({ name: "merge_records", args: { ids: [89, 147] }, result: "pending_review" },
              performance.now() - t0);
      setMatchPhase("merged");
    }, 1400);
  };

  const onSimulateCrisis = () => {
    setCrisisOpen(true);
    logCall({ name: "escalate_crisis",
              args: { signal: "distress_keyword", lang },
              result: "referral_card_elevated" }, timerRunning ? timerSec * 1000 : 0);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar
        sessionLabel="Session #147 — Active intake"
        statusLabel={statusLabel}
        statusTone={statusTone}
        queued={3}
        lang={lang}
        setLang={setLang}
      />

      <div className="flex-1 flex">
        {/* MAIN COLUMN */}
        <main className="flex-1 min-w-0">
          <div className="max-w-[1100px] mx-auto px-6 py-6">
            {view === "intake" ? (
              <>
                {/* Header strip row: timer on right, page title on left */}
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div>
                    <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Intake</div>
                    <h1 className="text-[24px] font-semibold text-ink mt-0.5 tracking-[-0.01em]">
                      Family separation report
                    </h1>
                    <div className="text-[14px] text-muted mt-1">
                      Speaker language auto-detected. Aid-worker chrome is in English.
                    </div>
                  </div>
                  <IntakeTimer seconds={timerSec} running={timerRunning} />
                </div>

                {/* Minor-detected strip — persistent, above card */}
                {minor && (
                  <div className="mb-5">
                    <MinorStrip complete={guardianFilled} />
                  </div>
                )}

                {/* Voice panel */}
                <div className="mb-5">
                  <VoicePanel phase={phase} lang={lang} onBegin={onBegin} elapsedSec={timerSec} />
                </div>

                {/* Completeness meter */}
                <div className="mb-4 px-1">
                  <CompletenessMeter segments={segments} />
                </div>

                {/* Record card */}
                <RecordCard
                  record={record}
                  minor={minor}
                  justPopulatedKey={justPopulated}
                  disabled={crisisOpen}
                />

                <div className="mt-6 text-[12px] text-muted flex items-center gap-2">
                  <IconLock size={12} />
                  <span>Record stored on this device. Will sync when you next connect to the local hub.</span>
                </div>
              </>
            ) : (
              <TransliterationMatch
                phase={matchPhase}
                onBack={() => setView("intake")}
              />
            )}
          </div>
        </main>

        {/* DEV RAIL */}
        {devMode && (
          <TracePanel
            calls={calls}
            highlightId={highlightedCall}
            onClose={() => setDevMode(false)}
          />
        )}
      </div>

      {/* Crisis overlay — pauses the record but does not modal-block the page */}
      {crisisOpen && (
        <CrisisReferralCard
          lang={lang}
          onResolved={() => {
            setCrisisOpen(false);
            logCall({ name: "crisis.resolve", args: { outcome: "referral_provided" } },
                    timerRunning ? timerSec * 1000 : 0);
          }}
          onDeEscalated={() => {
            setCrisisOpen(false);
            logCall({ name: "crisis.resolve", args: { outcome: "de_escalated" } },
                    timerRunning ? timerSec * 1000 : 0);
          }}
        />
      )}

      <DemoDock
        visible={demoDockVisible}
        onStart={runDemo}
        onReset={onReset}
        onMatch={onSimulateMatch}
        onCrisis={onSimulateCrisis}
        phase={phase}
        view={view}
      />

      <ShortcutHint isMac={isMac} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

```

---

