/* KIN — app shell. Top bar, main layout, demo sequencer, keyboard shortcuts. */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import {
  IconMic, IconLock, IconLanguages, IconInfo, IconShield,
  IconArrowRight, IconPlay, IconAlert, IconRotate, IconLink, IconX,
} from './components/icons';
import { Chip, Button, Waveform, CompletenessMeter } from './components/primitives';
import { RecordCard } from './components/RecordCard';
import { CrisisReferralCard, TransliterationMatch } from './components/CrisisAndTranslit';
import { NetworkMatch, DEFAULT_NETWORK_RESULT } from './components/NetworkMatch';
import { TracePanel } from './components/DevTrace';
import type {
  CompletenessSegment,
  Language,
  MatchPhase,
  NetworkMatchResult,
  RecordData,
  TraceCall,
} from './lib/types';
import { INITIAL_RECORD } from './lib/initialState';
import { useEventStream } from './hooks/useEventStream';
import { useMicCapture } from './hooks/useMicCapture';
import { useVoicePhase, type PostStatus } from './hooks/useVoicePhase';
import { IntakePanel } from './components/IntakePanel';
import { RailNav, type RailRoute } from './components/RailNav';
import { QueueView, useQueueRecords } from './components/QueueView';
import { RecordReadonly } from './components/RecordReadonly';
import { PresenterHUD } from './components/PresenterHUD';
import { usePresentationMode } from './hooks/usePresentationMode';
import type { IntakeRecord } from './lib/intakeRecord';
import {
  INITIAL_MATCH_CANDIDATES,
  applyMatchProposed,
  getActiveMatchCount,
  type MatchCandidatesMap,
} from './state/matchCandidates';
import { uploadAudioBlob } from './lib/api';
import { voiceCopy } from './lib/voiceCopy';
import { dirFor, t } from './lib/i18n';
import type { AuditEnvelope, StructlogEnvelope } from './lib/sseEnvelope';

type Phase = 'ready' | 'recording' | 'processing' | 'done';
type View = 'single' | 'split' | 'match' | 'queue';
type StatusTone = 'green' | 'amber' | 'red';

// Input shape passed to logCall — id and t are added by logCall itself.
type TraceCallInput = {
  name: string;
  args?: Record<string, unknown>;
  result?: unknown;
  highlight?: boolean;
};

type DemoStep = {
  at: number;
  state?: Phase;
  populate?: keyof RecordData;
  value?: string;
  lastSeenLocationSource?: string;
  trace?: TraceCallInput;
};

// ---------- Demo script ---------------------------------------------------
// Each step mutates the record object. The sequencer runs these in order against
// a wall clock to simulate SSE streaming into React state.

// Yusuf fixture script — Arabic intake that ends in crisis escalation.
// Mirrors DEMO_STEPS shape; crisis fires after the last populate step.
const YUSUF_DEMO_STEPS: DemoStep[] = [
  { at: 1000, state: "recording",  trace: { name: "audio_stream.open",  args: { lang_hint: "ar" } } },
  { at: 3000, state: "processing", trace: { name: "asr.transcribe",      args: { chunks: 5 }, result: "stream_complete" } },
  { at: 4200, populate: "name",    value: "مريم العمر",
              trace: { name: "extract_name", args: { text: "…أبحث عن زوجتي مريم العمر…" }, result: "مريم العمر" } },
  { at: 5400, populate: "relationship", value: "زوجة",
              trace: { name: "extract_relationship", args: {}, result: "spouse" } },
  { at: 6400, populate: "age",     value: "28",
              trace: { name: "extract_age", args: {}, result: 28 } },
  { at: 7200, populate: "lastSeenLocation", value: "Syria–Lebanon border",
              lastSeenLocationSource: "الحدود السورية اللبنانية",
              trace: { name: "extract_location", args: {}, result: "SY–LB border" } },
  { at: 8000, populate: "lastSeenDate", value: "3 days ago",
              trace: { name: "normalize_date", args: { input: "قبل ثلاثة أيام" }, result: "-3d" } },
  { at: 8800, populate: "circumstance", value: "Separated at border crossing during crowd movement",
              trace: { name: "extract_circumstance", args: {} } },
  // After this last step the sequencer fires escalate_crisis (see runYusufDemo)
];

const DEMO_STEPS: DemoStep[] = [
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


// ---------- Top bar -------------------------------------------------------
type TopBarProps = {
  sessionLabel: string;
  statusLabel: string;
  statusTone: StatusTone;
  speakerLanguage: Language;
  setSpeakerLanguage: Dispatch<SetStateAction<Language>>;
};

function TopBar({ sessionLabel, statusLabel, statusTone, speakerLanguage, setSpeakerLanguage }: TopBarProps) {
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

        {/* Sync state indicator — queue count lives in the rail badge. */}

        {/* Speaker-language switcher. Drives Whisper/Gemma/safety/
            referral. Does NOT flip UI chrome — chrome is governed
            by workerLanguage (App-level const, hardcoded 'en' in v1).
            S6 expanded from 4 codes (EN/ES/AR/FA) to 6 to expose the
            FLEURS-validated FR/UK speaker coverage. */}
        <div className="flex items-center border border-line rounded-kin overflow-hidden">
          <span className="px-2 text-muted"><IconLanguages size={14} /></span>
          {["EN", "ES", "AR", "FA", "FR", "UK"].map((code) => {
            const k = code.toLowerCase() as Language;
            const active = speakerLanguage === k;
            return (
              <button
                key={code}
                onClick={() => setSpeakerLanguage(k)}
                className={`h-9 px-2.5 text-[13px] font-medium border-l border-line transition-colors ${
                  active ? "bg-primary text-white" : "bg-white text-ink hover:bg-subtle"
                }`}
                aria-pressed={active}
                title={`Speaker language: ${code}`}
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
export type VoicePanelProps = {
  /* Bundle 1.5 S6 split: workerLanguage drives chrome (caption,
     Begin/Stop button labels). speakerLanguage drives the ready-copy
     greeting (read aloud to the displaced person), and is the
     language Whisper/Gemma/safety see via the POST. */
  workerLanguage: Language;
  speakerLanguage: Language;
  elapsedSec: number;
  sourceDeviceId: string;
  intakeId: string | null;
  /* SSE state slices passed from App.tsx (which owns the
     useEventStream subscription). The voice phase machine reads these
     to advance through transcribing -> extracting -> done. */
  auditEvents: AuditEnvelope[];
  structlogEvents: StructlogEnvelope[];
  /* Fires when /intake/audio responds with status=paused_for_crisis.
     Carries Gemma's locale_aware_message (or null on tool_call
     fallback). App opens the overlay and clears intakeId in one
     state-setter chain — see ADR-004 REV 3. */
  onCrisisResponse?: (message: string | null) => void;
};

export function VoicePanel({
  workerLanguage,
  speakerLanguage,
  elapsedSec,
  sourceDeviceId,
  intakeId,
  auditEvents,
  structlogEvents,
  onCrisisResponse,
}: VoicePanelProps) {
  const intakeIdRef = useRef<string | null>(intakeId);
  intakeIdRef.current = intakeId;
  const onCrisisResponseRef = useRef(onCrisisResponse);
  onCrisisResponseRef.current = onCrisisResponse;

  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastPostStatus, setLastPostStatus] = useState<PostStatus | null>(null);

  const { state: micState, start, stop, error } = useMicCapture({
    onStop: async (blob) => {
      try {
        const resp = await uploadAudioBlob({
          blob,
          lang: speakerLanguage,
          sourceDeviceId,
          intakeId: intakeIdRef.current,
        });
        setUploadError(null);
        if (resp.status === 'paused_for_crisis') {
          setLastPostStatus('paused_for_crisis');
          onCrisisResponseRef.current?.(resp.locale_aware_message ?? null);
        } else {
          setLastPostStatus('completed');
        }
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : String(err));
      }
    },
  });

  const { phase, onBegin: phaseBegin, onStop: phaseStop } = useVoicePhase({
    micState,
    auditEvents,
    structlogEvents,
    lastPostStatus,
  });

  const waveState =
    phase === 'recording' ? 'recording' :
    phase === 'transcribing' || phase === 'extracting' ? 'processing' :
    'idle';

  /* S6 chrome split: caption + Begin/Stop button labels are operator
     chrome and read workerLanguage. The ready-copy paragraph (below)
     is the speaker-facing greeting and reads speakerLanguage; its
     dir attribute follows speakerLanguage too. */
  const caption = voiceCopy[phase].en;
  const beginLabel = t('voice.begin', workerLanguage);
  const stopLabel = t('voice.stop', workerLanguage);
  const speakerRtl = dirFor(speakerLanguage) === 'rtl';

  const showBegin = phase === 'ready' || phase === 'done';
  const showStop = phase === 'recording' || phase === 'transcribing' || phase === 'extracting';

  /* Mic-icon chrome cycles per design ref nav-app.jsx:144-149. */
  const micIconCls =
    phase === 'recording' ? 'border-red/40 text-red bg-red-soft' :
    phase === 'transcribing' || phase === 'extracting' ? 'border-line text-primary bg-primary-soft' :
    phase === 'awaiting' ? 'border-primary/30 text-primary bg-primary-soft' :
    'border-line text-ink';

  const handleBegin = () => {
    phaseBegin();
    setLastPostStatus(null);
    void start();
  };

  const handleStop = () => {
    phaseStop();
    stop();
  };

  return (
    <div className="bg-card border border-line rounded-kin-lg">
      <div className="px-5 py-4 border-b border-hair flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={`w-8 h-8 rounded-kin border flex items-center justify-center ${micIconCls}`}>
            <IconMic size={16} />
          </div>
          <div>
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Voice intake</div>
            <div className="text-[15px] text-ink mt-0.5" aria-live="polite">
              {caption}
              {(error ?? uploadError) && (
                <span className="ml-2 text-red">{error ?? uploadError}</span>
              )}
            </div>
          </div>
        </div>
        <div className="font-mono text-[14px] text-muted tabular-nums">
          {formatElapsed(elapsedSec)}
        </div>
      </div>

      <div className="px-5 py-5">
        {showBegin ? (
          <div
            dir={dirFor(speakerLanguage)}
            className={`flex flex-col sm:flex-row sm:items-center gap-4 ${speakerRtl ? 'rtl' : ''}`}
          >
            <div className="flex-1 min-w-0">
              <div className="text-[17px] text-ink leading-relaxed" style={{ textWrap: 'pretty' }}>
                {READY_COPY[speakerLanguage] ?? READY_COPY.en}
              </div>
              <div className="mt-2 text-[13px] text-muted flex items-center gap-1.5">
                <IconInfo size={13} /> Consent to begin is logged with this record.
              </div>
            </div>
            <Button variant="primary" size="lg" icon={<IconMic size={18} />} onClick={handleBegin}>
              {beginLabel}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-5">
            <div className="flex-1"><Waveform state={waveState} bars={42} /></div>
            {showStop && (
              <Button variant="danger" size="lg" onClick={handleStop}>
                {stopLabel}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* Speaker-facing greeting paragraph. Read aloud to the displaced
   person before pressing Begin. Renders in speakerLanguage (not
   workerLanguage) since it's part of the speaker-facing surface. */
const READY_COPY: Record<Language, string> = {
  en: 'Ready to begin intake — explain to the person in front of you what KIN does, then press Begin.',
  es: 'Listo para comenzar la entrevista — explique a la persona frente a usted lo que hace KIN, y luego pulse Comenzar.',
  ar: 'جاهز لبدء المقابلة — اشرح للشخص أمامك ما يفعله KIN، ثم اضغط «ابدأ».',
  fa: 'آمادهٔ شروع مصاحبه — برای شخص مقابل توضیح دهید KIN چه می‌کند، سپس «شروع» را فشار دهید.',
  fr: "Prêt à commencer l'entretien — expliquez à la personne en face de vous ce que fait KIN, puis appuyez sur Commencer.",
  uk: 'Готовий розпочати співбесіду — поясніть людині перед вами, що робить KIN, а потім натисніть «Почати».',
};
function formatElapsed(s: number) {
  const m = Math.floor(s / 60); const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

// ---------- Intake timer + baseline --------------------------------------
type IntakeTimerProps = {
  seconds: number;
  running: boolean;
};

function IntakeTimer({ seconds, running }: IntakeTimerProps) {
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
type MinorStripProps = {
  complete: boolean;
};

function MinorStrip({ complete }: MinorStripProps) {
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
type ShortcutHintProps = {
  isMac: boolean;
};

function ShortcutHint({ isMac }: ShortcutHintProps) {
  return (
    <div className="fixed bottom-3 right-3 z-10 flex items-center gap-1.5 text-[12px] text-muted bg-paper/80 backdrop-blur border border-hair rounded-kin px-2 py-1">
      <kbd className="font-mono text-[11px] px-1.5 py-0.5 rounded border border-line bg-white text-ink">{isMac ? "⌘" : "Ctrl"}</kbd>
      <kbd className="font-mono text-[11px] px-1.5 py-0.5 rounded border border-line bg-white text-ink">D</kbd>
      <span>developer view</span>
    </div>
  );
}

// ---------- Demo control dock -------------------------------------------
type DemoDockProps = {
  visible: boolean;
  onStart: () => void;
  onReset: () => void;
  onMatch: () => void;
  onNetworkMatch: () => void;
  onCrisis: () => void;
  onSplit: () => void;
  onClose: () => void;
  phase: Phase;
  view: View;
  onRunYusufDemo: () => void;
};

function DemoDock({ visible, onStart, onReset, onMatch, onNetworkMatch, onCrisis, onSplit, onClose, phase, view, onRunYusufDemo }: DemoDockProps) {
  if (!visible) return null;

  const demoReady = phase === "ready" && view === "single";

  return (
    <div className="fixed bottom-3 left-3 z-30 bg-card border border-line rounded-kin-lg shadow-elevated px-3 py-2.5 w-[min(440px,calc(100%-24px))]">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted">Demo controls</div>
        <div className="flex items-center gap-2">
          <div className="text-[11px] text-muted font-mono">⌘⇧D&nbsp;to hide</div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Hide demo controls"
            title="Hide demo controls"
            className="w-6 h-6 rounded-kin text-muted hover:text-ink hover:bg-subtle transition-colors flex items-center justify-center"
          >
            <IconX size={14} />
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" variant="primary" icon={<IconPlay size={14} />}
                onClick={onStart} disabled={!demoReady}>
          Start demo
        </Button>
        <Button size="sm" variant="secondary" icon={<IconLink size={14} />}
                onClick={onMatch}>
          Simulate match
        </Button>
        <Button size="sm" variant="secondary" icon={<IconLink size={14} />}
                onClick={onNetworkMatch}>
          Network match
        </Button>
        <Button size="sm" variant="secondary" icon={<IconArrowRight size={14} />}
                onClick={onSplit}>
          {view === "split" ? "Single view" : "Split view"}
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
      {/* Fixtures — recording-day fallback: runs Yusuf Arabic intake then fires crisis */}
      <div className="mt-2.5 pt-2 border-t border-hair">
        <div className="text-[10px] font-medium uppercase tracking-wider text-muted/60 mb-1.5">Fixtures</div>
        <div className="flex flex-wrap gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            disabled={!demoReady}
            onClick={onRunYusufDemo}
          >
            Run Yusuf intake
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------- Demo reopen pill --------------------------------------------
// Rendered when the dock is hidden. Bottom-left, same corner the dock lived in,
// so the eye finds it without scanning. Click restores the dock; ⌘. still
// toggles for users whose browser doesn't intercept Cmd+Period.
type DemoReopenPillProps = {
  onOpen: () => void;
};

function DemoReopenPill({ onOpen }: DemoReopenPillProps) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label="Show demo controls"
      className="fixed bottom-3 left-3 z-30 flex items-center gap-1.5 bg-card border border-line rounded-kin shadow-elevated px-3 h-9 text-[13px] font-medium text-ink hover:bg-subtle transition-colors"
    >
      <IconPlay size={14} />
      Demo
    </button>
  );
}

// ---------- Main App ------------------------------------------------------
function App() {
  const [record, setRecord]                   = useState<RecordData>(INITIAL_RECORD);
  const [phase, setPhase]                     = useState<Phase>("ready");
  const [view, setView]                       = useState<View>("single");
  const [matchPhase, setMatchPhase]           = useState<MatchPhase>("split");
  const [networkMatchResult, setNetworkMatchResult] = useState<NetworkMatchResult | null>(null);
  /* Bundle 1.5 S6: speakerLanguage drives Whisper/Gemma/safety/
     referral; workerLanguage drives UI chrome. workerLanguage is a
     const in v1 (no Settings UI yet); v1.1 will lift it to useState
     with a Settings selector. Defaulting to 'en' here. */
  const [speakerLanguage, setSpeakerLanguage] = useState<Language>("en");
  const workerLanguage: Language = "en";
  const [crisisOpen, setCrisisOpen]           = useState(false);
  const [crisisMessage, setCrisisMessage]     = useState<string | null>(null);
  // S7: dev surfaces hidden by default; ?dev=1 initializes visible
  const [devMode, setDevMode]                 = useState(
    () => new URLSearchParams(window.location.search).has('dev'),
  );
  const [demoDockVisible, setDemoDockVisible] = useState(
    () => new URLSearchParams(window.location.search).has('dev'),
  );
  const [selectedQueueRecordId, setSelectedQueueRecordId] = useState<string | null>(null);
  const [justPopulated, setJustPopulated]     = useState<string | null>(null);
  const [timerSec, setTimerSec]               = useState(0);
  const [timerRunning, setTimerRunning]       = useState(false);
  const [calls, setCalls]                     = useState<TraceCall[]>([]);
  const [highlightedCall, setHighlightedCall] = useState<number | null>(null);
  const demoStartRef = useRef<number | null>(null);
  const callIdRef = useRef(0);

  // Queue records — fetched on view=queue mount; drives rail badge count
  const { records: queueRecords } = useQueueRecords(view === 'queue');

  // Presentation mode — ⌘⇧P or ?present=1
  const { presentationActive, setPresentationActive, hudHidden, setHudHidden } =
    usePresentationMode(queueRecords);

  // SSE hook: opens /intake/stream and dispatches incoming envelopes
  // into a reducer. record + calls below are *also* driven imperatively
  // by runDemo() for the offline Demo button; SSE arrivals overlay via
  // the useEffect below. Disabled in split view, where each IntakePanel
  // owns its own filtered stream and the unfiltered App-level
  // subscription would be a redundant third EventSource.
  const { state: streamState, clearIntakeId, reset: resetStream } = useEventStream({
    enabled: view !== 'split',
  });
  const seenAuditCount = useRef(0);
  const seenStructlogCount = useRef(0);
  /* Bundle 1.5 S5: high-water-mark for the match_proposed dispatcher.
     Prevents replaying past events on every render of the watcher
     useEffect; advances as new events land. */
  const seenMatchProposedCount = useRef(0);
  const [matchCandidates, setMatchCandidates] =
    useState<MatchCandidatesMap>(INITIAL_MATCH_CANDIDATES);
  const activeMatchCount = getActiveMatchCount(matchCandidates);

  // Bridge SSE record into local record state. When SSE delivers a
  // field_extracted event that updates streamState.record, mirror the
  // change into local record so existing components keep working.
  useEffect(() => {
    if (streamState.auditEvents.length > seenAuditCount.current) {
      seenAuditCount.current = streamState.auditEvents.length;
      // Use the reducer's already-mapped record (full RecordData shape).
      setRecord(streamState.record);
      // Surface the most-recently-changed field for the populate animation.
      const last = streamState.auditEvents[streamState.auditEvents.length - 1];
      if (last && last.payload.event_type === 'field_extracted') {
        const fieldName = (last.payload.details as { field_name?: string }).field_name;
        if (fieldName) {
          setJustPopulated(fieldName);
          setTimeout(() => setJustPopulated((j) => (j === fieldName ? null : j)), 2500);
        }
      }
    }
  }, [streamState.record, streamState.auditEvents]);

  // Bundle 1.5 S5: dispatch each new match_proposed audit event into
  // the matchCandidates map. Latest-wins per intake_id (record_ids[0]
  // per the ordering convention locked at
  // transcription_pipeline.py:710). Empty-result events
  // (candidate_count=0, single record id) record audit history but
  // don't contribute to getActiveMatchCount. The queue rail badge
  // derives from activeMatchCount above; no toast, no auto-route.
  // The DemoDock "Simulate match" button remains operational as a
  // manual override (onSimulateMatch fires view/phase directly).
  useEffect(() => {
    const total = streamState.auditEvents.length;
    if (total <= seenMatchProposedCount.current) return;
    const fresh = streamState.auditEvents.slice(
      seenMatchProposedCount.current,
    );
    seenMatchProposedCount.current = total;
    let next: MatchCandidatesMap | null = null;
    for (const env of fresh) {
      if (env.payload.event_type !== 'match_proposed') continue;
      const recordIds = env.payload.record_ids;
      if (recordIds.length === 0) continue;
      const intakeId = recordIds[0];
      const candidateCount = env.payload.candidate_count ?? 0;
      next = applyMatchProposed(
        next ?? matchCandidates,
        intakeId,
        candidateCount,
        recordIds,
        env.payload.at,
      );
      // S12: extract network_match from audit event details.
      // Only present on match_proposed events emitted after B2-S12
      // deployed; pre-S12 events have details={} so this is a no-op.
      const networkRaw = env.payload.details?.network_match;
      if (
        networkRaw !== null &&
        networkRaw !== undefined &&
        typeof networkRaw === 'object' &&
        (networkRaw as NetworkMatchResult).matched === true
      ) {
        setNetworkMatchResult(networkRaw as NetworkMatchResult);
      }
    }
    if (next !== null) setMatchCandidates(next);
  }, [streamState.auditEvents, matchCandidates]);

  // Bridge SSE structlog events into the trace calls list.
  useEffect(() => {
    if (streamState.structlogEvents.length > seenStructlogCount.current) {
      const fresh = streamState.structlogEvents.slice(seenStructlogCount.current);
      seenStructlogCount.current = streamState.structlogEvents.length;
      const t0 = demoStartRef.current ?? performance.now();
      setCalls((prev) => {
        const next = [...prev];
        for (const env of fresh) {
          const id = ++callIdRef.current;
          next.push({
            id,
            t: performance.now() - t0,
            name: String(env.payload.event ?? 'structlog'),
            args: { ...env.payload },
          });
        }
        return next;
      });
    }
  }, [streamState.structlogEvents]);

  const isMac = useMemo(() => typeof navigator !== "undefined" && /Mac/.test(navigator.platform), []);

  // ----- Trace logging helper
  const logCall = useCallback((call: TraceCallInput, tOffset = 0): number => {
    const id = ++callIdRef.current;
    const entry: TraceCall = { id, t: tOffset, ...call };
    setCalls(prev => [...prev, entry]);
    if (call.highlight) {
      setHighlightedCall(id);
      setTimeout(() => setHighlightedCall(h => (h === id ? null : h)), 1200);
    }
    return id;
  }, []);

  // ----- Keyboard shortcuts (single handler, explicit precedence)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = isMac ? e.metaKey : e.ctrlKey;
      // ESC — crisis > presentation > nothing
      if (e.key === 'Escape') {
        if (crisisOpen) { setCrisisOpen(false); setCrisisMessage(null); return; }
        if (presentationActive) { setPresentationActive(false); return; }
        return;
      }
      if (!mod) return;
      // ⌘⇧D — DemoDock toggle. Must precede ⌘D; shift+D satisfies key==='D'.
      if (e.shiftKey && (e.key === 'D' || e.key === 'd')) {
        e.preventDefault(); setDemoDockVisible(v => !v); return;
      }
      // ⌘⇧P — presentation mode toggle
      if (e.shiftKey && (e.key === 'P' || e.key === 'p')) {
        e.preventDefault(); setPresentationActive(!presentationActive); return;
      }
      // ⌘D (no shift) — TracePanel toggle
      if (!e.shiftKey && (e.key === 'd' || e.key === 'D')) {
        e.preventDefault(); setDevMode(v => !v); return;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isMac, crisisOpen, presentationActive]);

  // ----- Intake timer
  useEffect(() => {
    if (!timerRunning) return;
    const t = setInterval(() => setTimerSec(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [timerRunning]);

  // ----- Derived state
  const minor = !!record.age && parseInt(record.age, 10) > 0 && parseInt(record.age, 10) < 18;
  const guardianFilled = minor && Object.values(record.guardian).every(v => !!v && v.trim() !== "");
  const statusLabel = minor && !guardianFilled
    ? "Incomplete — Minor Protection Required"
    : phase === "done" ? "Intake complete · queued for sync" : "Active intake";
  const statusTone: StatusTone = minor && !guardianFilled ? "amber" : phase === "done" ? "green" : "green";

  const segments: CompletenessSegment[] = [
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
        const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
        if (step.state) setPhase(step.state);
        if (step.populate) {
          const populateKey = step.populate;
          const value = step.value;
          setRecord(prev => {
            const next = { ...prev, [populateKey]: value };
            if (step.lastSeenLocationSource) {
              next.lastSeenLocationSource = step.lastSeenLocationSource;
            }
            return next;
          });
          setJustPopulated(populateKey);
          setTimeout(() => setJustPopulated(j => j === populateKey ? null : j), 2500);
        }
        if (step.trace) logCall(step.trace, t);
      }, step.at);
    });

    // Final: set done
    const lastAt = DEMO_STEPS[DEMO_STEPS.length - 1].at;
    setTimeout(() => {
      setPhase("done");
      const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
      logCall({ name: "record.commit", args: { record_id: 147, status: "queued_local" }, result: "ok" }, t);
    }, lastAt + 600);
  };

  const onReset = () => {
    // Reset clears App-level demo state (record/phase/calls/timer)
    // but leaves view mode untouched. Switching view here would
    // unmount split-view IntakePanels and destroy their per-panel
    // SSE state — see bundle1-S4-fix.
    setRecord(INITIAL_RECORD);
    setPhase("ready");
    setCrisisOpen(false);
    setCrisisMessage(null);
    setTimerSec(0);
    setTimerRunning(false);
    setCalls([]);
    setJustPopulated(null);
    setNetworkMatchResult(null);
    // Clear SSE reducer state too — without this, intakeId stays
    // pinned to the previous turn's record id and the next mic turn
    // POSTs as an extend (HTTP 500 on crisis-after-Reset).
    resetStream();
  };

  const runYusufDemo = () => {
    demoStartRef.current = performance.now();
    setPhase("recording");
    setTimerRunning(true);
    setSpeakerLanguage("ar");
    logCall({ name: "session.start", args: { session_id: 42 }, result: "ok" }, 0);

    YUSUF_DEMO_STEPS.forEach((step) => {
      setTimeout(() => {
        const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
        if (step.state) setPhase(step.state);
        if (step.populate) {
          const populateKey = step.populate;
          const value = step.value;
          setRecord(prev => {
            const next = { ...prev, [populateKey]: value };
            if (step.lastSeenLocationSource) {
              next.lastSeenLocationSource = step.lastSeenLocationSource;
            }
            return next;
          });
          setJustPopulated(populateKey);
          setTimeout(() => setJustPopulated(j => j === populateKey ? null : j), 2500);
        }
        if (step.trace) logCall(step.trace, t);
      }, step.at);
    });

    // After last field: fire crisis card. Phase stays "done" while the
    // card is open. The crisis card's onResolved/onDeEscalated handlers
    // call setCrisisOpen(false); we hook into that via a separate effect
    // by setting phase to "ready" immediately — the mic won't activate
    // until crisisOpen is also false, which the close handler ensures.
    const lastAt = YUSUF_DEMO_STEPS[YUSUF_DEMO_STEPS.length - 1].at;
    setTimeout(() => {
      const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
      logCall({ name: "escalate_crisis",
                args: { signal: "distress_keyword", lang: "ar" },
                result: "referral_card_elevated" }, t);
      setCrisisOpen(true);
      // Set ready now — crisis overlay is still visible, so the mic is
      // not accessible. Once the caseworker dismisses the card
      // (onResolved / onDeEscalated sets crisisOpen=false) the app is
      // immediately live for Mariam's intake with no extra reset needed.
      setPhase("ready");
    }, lastAt + 600);
  };

  const onSimulateMatch = () => {
    setView("match");
    setMatchPhase("split");
    const t0 = performance.now();
    logCall({ name: "fuzzy_match", args: { a: "Mohammed", b: "Mohamad" }, result: "candidate" }, 0);
    setTimeout(() => {
      logCall({ name: "transliteration_comparison",
                args: { source: "محمد", variants: ["Mohammed", "Mohamad"] },
                result: "match_confidence=high",
                highlight: true }, performance.now() - t0);
      setMatchPhase("linking");
    }, 400);
    setTimeout(() => {
      logCall({ name: "merge_records", args: { ids: [89, 147] }, result: "pending_review" },
              performance.now() - t0);
      setMatchPhase("merged");
    }, 3400);
  };

  const onSimulateNetworkMatch = () => {
    setNetworkMatchResult(DEFAULT_NETWORK_RESULT);
    setView("match");
    setMatchPhase("split");
    setTimeout(() => setMatchPhase("linking"), 400);
    setTimeout(() => setMatchPhase("merged"), 3400);
  };

  const onSimulateCrisis = () => {
    setCrisisOpen(true);
    logCall({ name: "escalate_crisis",
              args: { signal: "distress_keyword", lang: speakerLanguage },
              result: "referral_card_elevated" }, timerRunning ? timerSec * 1000 : 0);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar
        sessionLabel="Session #147 — Active intake"
        statusLabel={statusLabel}
        statusTone={statusTone}
        speakerLanguage={speakerLanguage}
        setSpeakerLanguage={setSpeakerLanguage}
      />

      <div className="flex-1 flex">
        {/* PERSISTENT NAV RAIL — bimodal (capture / review). Active state
            tracks the current view: intake covers single/split/match
            (all capture-arm surfaces, per design ref nav-app.jsx note
            "Match view is a sub-state of intake, not a separate route");
            queue is its own destination. */}
        <RailNav
          route={view === 'queue' ? 'queue' : 'intake'}
          setRoute={(next: RailRoute) => {
            setView(next === 'queue' ? 'queue' : 'single');
          }}
          queuedCount={queueRecords.length}
        />

        {/* MAIN COLUMN */}
        <main className="flex-1 min-w-0">
          <div className="max-w-[1100px] mx-auto px-6 py-6">
            {view === "single" && (
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

                {/* Voice panel — single-view mic capture (S5).
                    sourceDeviceId is hardcoded for the single-panel
                    workflow (no split context). intakeId comes from
                    the App-level useEventStream reducer (set by the
                    intake_created audit event after first turn). */}
                <div className="mb-5">
                  <VoicePanel
                    workerLanguage={workerLanguage}
                    speakerLanguage={speakerLanguage}
                    elapsedSec={timerSec}
                    sourceDeviceId="laptop"
                    intakeId={streamState.intakeId}
                    auditEvents={streamState.auditEvents}
                    structlogEvents={streamState.structlogEvents}
                    onCrisisResponse={(msg) => {
                      // Gap 1+2+3 in one chain: open overlay with
                      // Gemma's locale_aware_message, clear cached
                      // intakeId so next mic turn takes the create
                      // path (S5 lock #4: extend-into-crisis is
                      // ValueError). See ADR-004 REV 3.
                      setCrisisMessage(msg);
                      setCrisisOpen(true);
                      clearIntakeId();
                    }}
                  />
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
            )}

            {view === "split" && (
              <>
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div>
                    <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Split view</div>
                    <h1 className="text-[24px] font-semibold text-ink mt-0.5 tracking-[-0.01em]">
                      Two tents · same child
                    </h1>
                    <div className="text-[14px] text-muted mt-1">
                      Each panel subscribes to its own device's SSE stream.
                    </div>
                  </div>
                  <IntakeTimer seconds={timerSec} running={timerRunning} />
                </div>
                <div className="grid grid-cols-2 gap-6">
                  <IntakePanel
                    sourceDeviceId="tent_a"
                    tent="a"
                    panelLabel="Tent A"
                    workerLanguage={workerLanguage}
                    speakerLanguage={speakerLanguage}
                    timerSec={timerSec}
                    timerRunning={timerRunning}
                    crisisOpen={crisisOpen}
                  />
                  <IntakePanel
                    sourceDeviceId="tent_b"
                    tent="b"
                    panelLabel="Tent B"
                    workerLanguage={workerLanguage}
                    speakerLanguage={speakerLanguage}
                    timerSec={timerSec}
                    timerRunning={timerRunning}
                    crisisOpen={crisisOpen}
                  />
                </div>
              </>
            )}

            {view === "match" && (
              networkMatchResult && networkMatchResult.node_matches.length >= 2
                ? <NetworkMatch
                    phase={matchPhase}
                    onBack={() => setView("single")}
                    workerLanguage={workerLanguage}
                    networkResult={networkMatchResult}
                  />
                : <TransliterationMatch
                    phase={matchPhase}
                    onBack={() => setView("single")}
                    workerLanguage={workerLanguage}
                  />
            )}

            {view === "queue" && !selectedQueueRecordId && (
              <QueueView
                records={queueRecords}
                onOpen={(r: IntakeRecord) => setSelectedQueueRecordId(r.id)}
                onNew={() => setView('single')}
              />
            )}

            {view === "queue" && selectedQueueRecordId && (() => {
              const rec = queueRecords.find(r => r.id === selectedQueueRecordId);
              if (!rec) return null;
              return (
                <RecordReadonly
                  record={rec}
                  workerLanguage={workerLanguage}
                  onBack={() => setSelectedQueueRecordId(null)}
                  onNew={() => { setSelectedQueueRecordId(null); setView('single'); }}
                />
              );
            })()}
          </div>
        </main>

        {/* DEV RAIL — hidden in presentation mode */}
        {devMode && !presentationActive && (
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
          workerLanguage={workerLanguage}
          speakerLanguage={speakerLanguage}
          message={crisisMessage}
          onResolved={() => {
            setCrisisOpen(false);
            setCrisisMessage(null);
            logCall({ name: "crisis.resolve", args: { outcome: "referral_provided" } },
                    timerRunning ? timerSec * 1000 : 0);
          }}
          onDeEscalated={() => {
            setCrisisOpen(false);
            setCrisisMessage(null);
            logCall({ name: "crisis.resolve", args: { outcome: "de_escalated" } },
                    timerRunning ? timerSec * 1000 : 0);
          }}
        />
      )}

      {/* DemoDock + reopen pill — hidden in presentation mode */}
      {demoDockVisible && !presentationActive && (
        <DemoDock
          visible={demoDockVisible}
          onStart={runDemo}
          onReset={onReset}
          onMatch={onSimulateMatch}
          onNetworkMatch={onSimulateNetworkMatch}
          onCrisis={onSimulateCrisis}
          onSplit={() => setView(v => (v === "split" ? "single" : "split"))}
          onClose={() => setDemoDockVisible(false)}
          phase={phase}
          view={view}
          onRunYusufDemo={runYusufDemo}
        />
      )}
      {!demoDockVisible && !presentationActive && (
        <DemoReopenPill onOpen={() => setDemoDockVisible(true)} />
      )}

      {/* ShortcutHint — hidden in presentation mode */}
      {!presentationActive && <ShortcutHint isMac={isMac} />}

      {/* PresenterHUD — below 1080p safe-area crop */}
      <PresenterHUD
        active={presentationActive}
        hidden={hudHidden}
        setHidden={setHudHidden}
        pipelineState={streamState.connection === 'open' ? 'busy' : 'down'}
        onReset={onReset}
      />
    </div>
  );
}

export default App;
