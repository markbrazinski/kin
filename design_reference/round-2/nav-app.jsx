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
