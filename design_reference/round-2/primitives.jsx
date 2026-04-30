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
