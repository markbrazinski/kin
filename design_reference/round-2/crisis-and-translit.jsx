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
