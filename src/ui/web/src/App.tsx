/* KIN — app shell. Top bar, main layout, demo sequencer, keyboard shortcuts. */
import React, { useState, useEffect, useReducer, useRef, useCallback, useMemo } from 'react';
import {
  IconMic, IconLock, IconLanguages, IconInfo, IconSparkle, IconCheck, IconShield,
  IconArrowRight, IconPlay, IconAlert, IconRotate, IconLink,
} from './components/icons';
import { Chip, Button, Waveform, CompletenessMeter } from './components/primitives';
import { RecordCard } from './components/RecordCard';
import { CrisisReferralCard, TransliterationMatch } from './components/CrisisAndTranslit';
import { TracePanel } from './components/DevTrace';

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

export default App;
