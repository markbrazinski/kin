/* KIN — app shell. Top bar, main layout, demo sequencer, keyboard shortcuts. */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import {
  IconMic, IconLock, IconLanguages, IconInfo,
  IconArrowRight, IconPlay, IconAlert, IconRotate, IconLink, IconX,
} from './components/icons';
import { Button, Waveform } from './components/primitives';
import { ChicletRibbon } from './components/ChicletRibbon';
import { RecordCard } from './components/RecordCard';
import { CrisisReferralCard, TransliterationMatch } from './components/CrisisAndTranslit';
import { NetworkMatch, DEFAULT_NETWORK_RESULT } from './components/NetworkMatch';
import type { NetworkCardData } from './components/NetworkMatch';
import { TracePanel } from './components/DevTrace';
import type {
  Language,
  MatchPhase,
  NetworkMatchResult,
  RecordData,
  TraceCall,
} from './lib/types';
import { INITIAL_RECORD } from './lib/initialState';
import { useEventStream } from './hooks/useEventStream';
import { useMicCapture } from './hooks/useMicCapture';
import { useVoicePhase, type PostStatus, type VoicePhase } from './hooks/useVoicePhase';
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
import { uploadAudioBlob, postCrisisResolved, postDemoRunIntake } from './lib/api';
import { voiceCopy } from './lib/voiceCopy';
import { dirFor, t } from './lib/i18n';
import type { AuditEnvelope, StructlogEnvelope } from './lib/sseEnvelope';

type Phase = 'ready' | 'recording' | 'processing' | 'extracting' | 'done' | 'saved';
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
  // For array fields (missingPersons, familyRoster) and non-string scalars
  // (searcherName) that need to bypass the string-only populate path:
  populateRaw?: Partial<RecordData>;
  trace?: TraceCallInput;
  // Synthetic structlog event — pushed into demoStructlogEvents so
  // the TranscriptStrip (and StructlogSidebar) see it during demo playback.
  structlog?: { event: string; [key: string]: unknown };
};

// ---------- Demo script ---------------------------------------------------
// Each step mutates the record object. The sequencer runs these in order against
// a wall clock to simulate SSE streaming into React state.

// Yusuf al-Saleh — Arabic intake ending in crisis escalation.
// Searcher: Yusuf (35). Missing: sister Mariam (32) + nephew Mohamad (8).
// Roster: wife Aisha (32, WITH_SEARCHER). crisis fires after last step.
const YUSUF_DEMO_STEPS: DemoStep[] = [
  { at: 1000, state: "recording",
    trace: { name: "audio_stream.open", args: { lang_hint: "ar" } } },
  { at: 2200,
    structlog: { event: "transcription_chunk",
      source: "أنا يوسف العمر، عمري واحد وأربعون سنة. أبحث عن أختي مريم، عمرها اثنان وثلاثون سنة، وابن أختي محمد، عمره ثماني سنوات. معي زوجتي عائشة. آخر مرة رأيتهم كانت عند البوابة الجنوبية في المخيم، قبل ثلاثة أيام، وقت ازدحام شديد عند نقطة التفتيش. مريم طويلة، شعرها داكن على الكتفين، وعندها شامة صغيرة على خدها الأيمن. محمد قصير القامة وعنده ندبة فوق حاجبه الأيسر.",
      translation: "I am Yusuf Al-Omar, I am forty-one years old. I am looking for my sister Mariam, thirty-two years old, and my nephew Mohamad, eight years old. My wife Aisha is with me. The last time I saw them was at the southern gate of the camp, three days ago, during a severe crowd surge at the checkpoint. Mariam is tall with dark shoulder-length hair and a small mole on her right cheek. Mohamad is short with a scar above his left eyebrow." } },
  { at: 3000, state: "processing",
    trace: { name: "asr.transcribe", args: { chunks: 5 }, result: "stream_complete" } },
  { at: 4000, state: "extracting" as Phase },
  // Searcher identity
  { at: 4000,
    populateRaw: { searcherName: "يوسف العمر", searcherNameLatin: "Yusuf Al-Omar" },
    trace: { name: "extract_intake_fields", args: { searcher_name: "يوسف العمر" }, result: "ok" } },
  // Missing persons — Mariam first
  { at: 5200,
    populateRaw: { missingPersons: [
      { name: "مريم", nameLatin: "Mariam", age: 32, relationship: "أخت", status: "MISSING",
        lastSeen: "البوابة الجنوبية · Southern gate",
        marks: ["شامة صغيرة على الخد الأيمن · small mole right cheek"] },
    ]},
    trace: { name: "extract_intake_fields", args: { missing_persons: "[مريم, 32, sister]" }, result: "ok" } },
  // Missing persons — add Mohamad (flag_minor fires here)
  { at: 6400,
    populateRaw: { missingPersons: [
      { name: "مريم", nameLatin: "Mariam", age: 32, relationship: "أخت", status: "MISSING",
        lastSeen: "البوابة الجنوبية · Southern gate",
        marks: ["شامة صغيرة على الخد الأيمن · small mole right cheek"] },
      { name: "محمد", nameLatin: "Mohamad", age: 8, relationship: "ابن أخت", status: "MISSING",
        lastSeen: "البوابة الجنوبية · Southern gate",
        marks: ["ندبة فوق الحاجب الأيسر · scar above left brow"] },
    ]},
    trace: { name: "flag_minor", args: { subject: "محمد", age: 8 }, result: "protection_required", highlight: true } },
  // Roster — Aisha with searcher
  { at: 7400,
    populateRaw: { familyRoster: [
      { name: "عائشة", nameLatin: "Aisha", age: 32, relationship: "زوجة", status: "WITH_SEARCHER" },
    ]},
    trace: { name: "extract_intake_fields", args: { family_roster: "[عائشة, wife, WITH_SEARCHER]" }, result: "ok" } },
  // Last seen
  { at: 8200, populate: "lastSeenLocation", value: "Southern gate — camp perimeter",
    lastSeenLocationSource: "البوابة الجنوبية",
    trace: { name: "extract_location", args: {}, result: "southern_gate" } },
  { at: 8900, populate: "lastSeenDate", value: "3 days ago",
    trace: { name: "normalize_date", args: { input: "قبل ثلاثة أيام" }, result: "-3d" } },
  { at: 9400, populate: "circumstance", value: "Separated during crowd surge at the southern gate checkpoint",
    trace: { name: "extract_circumstance", args: {} } },
  { at: 9900, populate: "physicalDesc", value: "Mariam: approx. 165 cm, dark hair shoulder length · Mohamad: approx. 120 cm, short hair",
    trace: { name: "extract_distinguishing_marks", args: {} } },
  // crisis fires after this step — see runYusufDemo
];

// SYNTHETIC_YUSUF_STEPS — slow-paced choreography for ⌘⇧Q.
// 22 s waveform → 2 s processing pause → transcript T+24s → fields T+26–29.5s.
// Crisis fires after runSteps at T+30s (see runSyntheticYusuf).
const SYNTHETIC_YUSUF_STEPS: DemoStep[] = [
  // Phase 1 — RECORDING (waveform animates for 22 s)
  { at: 0, state: "recording" },
  // Phase 2 — PROCESSING PAUSE
  { at: 22000, state: "processing" },
  // Phase 3 — TRANSCRIPT (T+24s, two structlog events same tick)
  { at: 24000,
    structlog: { event: "whisper_transcription_start" },
    trace: { name: "whisper.transcribe", args: { lang: "ar", duration: "22s", model: "medium" }, result: "segments: 1, confidence: 0.97" } },
  { at: 24000,
    structlog: {
      event: "transcription_chunk",
      source: "أنا يوسف العمر، عمري واحد وأربعون سنة. أبحث عن أختي مريم وابن أختي محمد، عمره ثمان سنوات. زوجتي عائشة معي. آخر مرة عند البوابة الجنوبية قبل ثلاثة أيام خلال تدافع. محمد عنده ندبة فوق حاجبه الأيسر... ما عاد فيني أكمل.",
      translation: "I am Yusuf Al-Omar, forty-one years old. I am looking for my sister Mariam and my nephew Mohamad, he is eight years old. My wife Aisha is with me. Last seen at the southern gate three days ago during a crowd surge. Mohamad has a scar above his left eyebrow... I can't go on.",
    } },
  { at: 24500,
    structlog: { event: "whisper_transcription_complete" },
    trace: { name: "whisper.translate", args: { source: "ar", target: "en" }, result: "complete" } },
  // Phase 4 — EXTRACTION (T+26s)
  { at: 26000, state: "extracting",
    structlog: { event: "adapter_call_start" },
    trace: { name: "gemma.extract", args: { model: "gemma4:e2b", tool: "extract_intake_fields", searcher_name: "يوسف العمر", missing: "[مريم, محمد]", last_seen: "البوابة الجنوبية", date: "قبل ثلاثة أيام", marks: "ندبة فوق الحاجب الأيسر" }, result: "tool_call_emitted" } },
  { at: 26000,
    populateRaw: { searcherName: "يوسف العمر", searcherNameLatin: "Yusuf Al-Omar" },
    structlog: { event: "tool_call_invoked", tool: "extract_intake_fields" } },
  // T+26.5s: Mariam (no marks — scar belongs to Mohamad)
  { at: 26500,
    populateRaw: { missingPersons: [
      { name: "مريم", nameLatin: "Mariam", age: 32, relationship: "أختي",
        status: "MISSING", lastSeen: "البوابة الجنوبية", marks: [] },
    ] } },
  // T+27s: add Mohamad with scar; flag_minor fires
  { at: 27000,
    populateRaw: { missingPersons: [
      { name: "مريم", nameLatin: "Mariam", age: 32, relationship: "أختي",
        status: "MISSING", lastSeen: "البوابة الجنوبية", marks: [] },
      { name: "محمد", nameLatin: "Mohamad", age: 8, relationship: "ابن أختي",
        status: "MISSING", lastSeen: "البوابة الجنوبية",
        marks: ["ندبة فوق الحاجب الأيسر · scar above left brow"] },
    ] },
    structlog: { event: "tool_call_invoked", tool: "flag_minor", subject: "محمد", age: 8 },
    trace: { name: "flag_minor", args: { subject: "محمد", age: 8 }, result: "protection_required", highlight: true } },
  // T+27.5s: family roster — Aisha with searcher
  { at: 27500,
    populateRaw: { familyRoster: [
      { name: "عائشة", nameLatin: "Aisha", relationship: "زوجتي", status: "WITH_SEARCHER" },
    ] } },
  // T+28s: last seen location
  { at: 28000,
    populate: "lastSeenLocation", value: "Southern gate — camp perimeter",
    lastSeenLocationSource: "البوابة الجنوبية" },
  // T+28.5s: last seen date
  { at: 28500,
    populate: "lastSeenDate", value: "3 days ago" },
  // T+29s: circumstance
  { at: 29000,
    populate: "circumstance", value: "Separated during crowd surge at the southern gate" },
  // T+29.5s: physical description — crisis fires 500 ms after this
  { at: 29500,
    populate: "physicalDesc", value: "Mohamad: scar above left eyebrow" },
];

// Mariam al-Saleh — Arabic intake, complete, no crisis.
// Searcher: Mariam (32). Missing: brother Yusuf (35) + son Mohamad (8).
// Roster: empty (no one with her).
const MARIAM_DEMO_STEPS: DemoStep[] = [
  { at: 1000, state: "recording",
    trace: { name: "audio_stream.open", args: { lang_hint: "ar" } } },
  { at: 2200,
    structlog: { event: "transcription_chunk",
      source: "أنا مريم صالح، عمري ثمانية وثلاثون سنة. أبحث عن زوجي يوسف، عمره خمسة وثلاثون سنة، وابني محمد، عمره ثماني سنوات. فُقدنا قبل ثلاثة أيام عند البوابة الجنوبية في المخيم وقت ازدحام شديد. يوسف أصلع جزئياً. محمد عنده وحمة على خده الأيسر.",
      translation: "I am Mariam Saleh, I am thirty-eight years old. I am looking for my husband Yusuf, thirty-five years old, and my son Mohamad, eight years old. We were separated three days ago at the southern gate of the camp during a severe crowd surge. Yusuf has partial baldness. Mohamad has a birthmark on his left cheek." } },
  { at: 3000, state: "processing",
    trace: { name: "asr.transcribe", args: { chunks: 4 }, result: "stream_complete" } },
  { at: 4000, state: "extracting" as Phase },
  // Searcher identity
  { at: 4000,
    populateRaw: { searcherName: "مريم صالح", searcherNameLatin: "Mariam Saleh" },
    trace: { name: "extract_intake_fields", args: { searcher_name: "مريم صالح" }, result: "ok" } },
  // Missing — Yusuf (brother) — with per-person lastSeen + marks (complete intake)
  { at: 5200,
    populateRaw: { missingPersons: [
      { name: "يوسف", nameLatin: "Yusuf", age: 41, relationship: "أخ", status: "MISSING",
        lastSeen: "البوابة الجنوبية · Southern gate", marks: ["أصلع جزئياً · partial baldness"] },
    ]},
    trace: { name: "extract_intake_fields", args: { missing_persons: "[يوسف, 35, brother]" }, result: "ok" } },
  // Missing — Mohamad (son, minor) — with per-person lastSeen + marks
  { at: 6400,
    populateRaw: { missingPersons: [
      { name: "يوسف", nameLatin: "Yusuf", age: 41, relationship: "أخ", status: "MISSING",
        lastSeen: "البوابة الجنوبية · Southern gate", marks: ["أصلع جزئياً · partial baldness"] },
      { name: "محمد", nameLatin: "Mohamad", age: 8, relationship: "ابن", status: "MISSING",
        lastSeen: "البوابة الجنوبية · Southern gate", marks: ["وحمة على الخد الأيسر · birthmark left cheek"] },
    ]},
    trace: { name: "flag_minor", args: { subject: "محمد", age: 8 }, result: "protection_required", highlight: true } },
  // Last seen
  { at: 7400, populate: "lastSeenLocation", value: "Southern gate — camp perimeter",
    lastSeenLocationSource: "البوابة الجنوبية",
    trace: { name: "extract_location", args: {}, result: "southern_gate" } },
  { at: 8100, populate: "lastSeenDate", value: "3 days ago",
    trace: { name: "normalize_date", args: { input: "قبل ثلاثة أيام" }, result: "-3d" } },
  // ends at phase="done" — Save button activates (see runMariam)
];

// SYNTHETIC_MARIAM_STEPS — slow-paced choreography for ⌘⇧W.
// 16 s waveform → 2 s processing pause → transcript T+18s → fields T+20–23s.
// submit_record fires in runSyntheticMariam after lastAt+500ms.
const SYNTHETIC_MARIAM_STEPS: DemoStep[] = [
  // Phase 1 — RECORDING (waveform animates for 16 s)
  { at: 0, state: "recording" },
  // Phase 2 — PROCESSING PAUSE
  { at: 16000, state: "processing" },
  // Phase 3 — TRANSCRIPT (T+18s, two structlog events same tick)
  { at: 18000,
    structlog: { event: "whisper_transcription_start" },
    trace: { name: "whisper.transcribe", args: { lang: "ar", duration: "16s", model: "medium" }, result: "segments: 1, confidence: 0.97" } },
  { at: 18000,
    structlog: {
      event: "transcription_chunk",
      source: "أنا مريم العمر، عمري اثنان وثلاثون سنة. أبحث عن أخي يوسف وابني محمد، عمره ثمان سنوات. فقدنا قبل ثلاثة أيام عند البوابة الجنوبية. محمد عنده ندبة فوق حاجبه الأيسر.",
      translation: "I am Mariam Al-Omar, thirty-two years old. I am looking for my brother Yusuf and my son Mohamad, he is eight years old. We were separated three days ago at the southern gate. Mohamad has a scar above his left eyebrow.",
    } },
  { at: 18500,
    structlog: { event: "whisper_transcription_complete" },
    trace: { name: "whisper.translate", args: { source: "ar", target: "en" }, result: "complete" } },
  // Phase 4 — EXTRACTION (T+20s)
  { at: 20000, state: "extracting",
    structlog: { event: "adapter_call_start" },
    trace: { name: "gemma.extract", args: { model: "gemma4:e2b", tool: "extract_intake_fields", searcher_name: "مريم العمر", missing: "[يوسف, محمد]", last_seen: "البوابة الجنوبية", date: "قبل ثلاثة أيام", marks: "ندبة فوق الحاجب الأيسر" }, result: "tool_call_emitted" } },
  { at: 20000,
    populateRaw: { searcherName: "مريم العمر", searcherNameLatin: "Mariam Al-Omar" },
    structlog: { event: "tool_call_invoked", tool: "extract_intake_fields" } },
  // T+20.5s: Yusuf (no marks in this intake)
  { at: 20500,
    populateRaw: { missingPersons: [
      { name: "يوسف", nameLatin: "Yusuf", age: 41, relationship: "أخي",
        status: "MISSING", lastSeen: "البوابة الجنوبية", marks: [] },
    ] } },
  // T+21s: add Mohamad with scar; flag_minor fires
  { at: 21000,
    populateRaw: { missingPersons: [
      { name: "يوسف", nameLatin: "Yusuf", age: 41, relationship: "أخي",
        status: "MISSING", lastSeen: "البوابة الجنوبية", marks: [] },
      { name: "محمد", nameLatin: "Mohamad", age: 8, relationship: "ابن",
        status: "MISSING", lastSeen: "البوابة الجنوبية",
        marks: ["ندبة فوق الحاجب الأيسر · scar above left brow"] },
    ] },
    structlog: { event: "tool_call_invoked", tool: "flag_minor", subject: "محمد", age: 8 },
    trace: { name: "flag_minor", args: { subject: "محمد", age: 8 }, result: "protection_required", highlight: true } },
  // T+21.5s: last seen location
  { at: 21500,
    populate: "lastSeenLocation", value: "Southern gate — camp perimeter",
    lastSeenLocationSource: "البوابة الجنوبية" },
  // T+22s: last seen date
  { at: 22000,
    populate: "lastSeenDate", value: "3 days ago" },
  // T+22.5s: circumstance
  { at: 22500,
    populate: "circumstance", value: "Separated three days ago at the southern gate" },
  // T+23s: physical description — submit_record fires 500 ms after this
  { at: 23000,
    populate: "physicalDesc", value: "Mohamad: scar above left eyebrow" },
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
          <div className="text-[13px] text-muted">{sessionLabel}</div>
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

// ---------- Transcript strip ─────────────────────────────────────────────

type TranscriptChunk = {
  source: string;       // source-language utterance (Arabic, Spanish, etc.)
  translation: string;  // worker-language translation (always English in v1)
  at: string;           // ISO 8601 timestamp from the envelope
};

function extractTranscriptChunks(events: StructlogEnvelope[]): TranscriptChunk[] {
  return events
    .filter(e => e.payload.event === 'transcription_chunk')
    .map(e => ({
      source:      String(e.payload.source      ?? ''),
      translation: String(e.payload.translation ?? ''),
      at: e.at,
    }));
}

type TranscriptStripProps = {
  structlogEvents: StructlogEnvelope[];
  isSaved: boolean;
};

function TranscriptStrip({ structlogEvents, isSaved }: TranscriptStripProps) {
  const chunks = extractTranscriptChunks(structlogEvents);

  if (chunks.length === 0) {
    return (
      <div className="mt-3 pt-3 border-t border-hair">
        <div className="text-[10.5px] font-medium uppercase tracking-wider text-muted mb-1.5">
          Transcript
        </div>
        <div className="text-[12px] text-muted/70 italic">
          Transcript will appear as speech is detected
        </div>
      </div>
    );
  }

  const label = isSaved
    ? `TRANSCRIPT · ${chunks.length} utterance${chunks.length !== 1 ? 's' : ''}`
    : 'TRANSCRIPT';

  // Newest-first (consistent with S26-A ordering).
  const displayed = chunks.slice().reverse();

  return (
    <div className="mt-3 pt-3 border-t border-hair">
      <div className="text-[10.5px] font-medium uppercase tracking-wider text-muted mb-1.5">
        {label}
      </div>
      <div className="overflow-y-auto space-y-2.5" style={{ maxHeight: 180 }}>
        {displayed.map((chunk, i) => (
          <div key={`${chunk.at}-${i}`}>
            <div className="text-[13px] text-ink leading-snug" dir="auto">
              {chunk.source}
            </div>
            <div className="text-[12px] text-muted/70 leading-snug mt-0.5">
              {chunk.translation}
            </div>
          </div>
        ))}
      </div>
    </div>
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
  /* Fires when /intake/audio responds with is_crisis=true.
     Carries Gemma's locale_aware_message (or null on tool_call
     fallback). App opens the overlay and clears intakeId in one
     state-setter chain — see ADR-004 REV 3. */
  onCrisisResponse?: (message: string | null) => void;
  /* Demo sequencer display override — pure visual, does not affect the
     real useVoicePhase machine or mic capture. When undefined, the real
     internal phase governs (live intake path). */
  demoPhase?: VoicePhase;
  /* Called when Begin is pressed while displayPhase === 'saved',
     so the demo sequencer can reset App's phase back to 'ready'. */
  onBeginNewIntake?: () => void;
  /* Ref owned by App that holds a queued demo filename. VoicePanel
     checks and clears it on Begin to run the real pipeline on a
     pre-recorded file instead of starting mic capture. */
  demoFileRef?: React.MutableRefObject<'yusuf' | 'mariam' | null>;
  /* Ref owned by App that holds a queued synthetic runner (⌘⇧J/⌘⇧K).
     Checked before demoFileRef — fires the full synthetic sequencer
     instead of mic capture or real-pipeline file. */
  syntheticDemoRef?: React.MutableRefObject<(() => void) | null>;
  /* Fires on every useVoicePhase transition so App's local phase state
     stays in sync with the real pipeline (Save button, statusLabel, timer). */
  onPhaseChange?: (phase: VoicePhase) => void;
  /* Fires the moment Begin is clicked — before any phase dispatch or
     async work. App uses this to start the timer reliably without
     depending on React batching of phase transitions. */
  onBegin?: () => void;
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
  demoPhase,
  onBeginNewIntake,
  demoFileRef: externalDemoFileRef,
  syntheticDemoRef,
  onPhaseChange,
  onBegin,
}: VoicePanelProps) {
  const intakeIdRef = useRef<string | null>(intakeId);
  intakeIdRef.current = intakeId;
  const onCrisisResponseRef = useRef(onCrisisResponse);
  onCrisisResponseRef.current = onCrisisResponse;

  // demoFileRef: owned by App, passed down so the keyboard handler
  // (App scope) can set it and handleBegin (here) can read + clear it.
  const localDemoFileRef = useRef<'yusuf' | 'mariam' | null>(null);
  const demoFileRef = externalDemoFileRef ?? localDemoFileRef;

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
        setLastPostStatus('completed');
        if (resp.is_crisis) {
          onCrisisResponseRef.current?.(resp.locale_aware_message ?? null);
        }
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : String(err));
      }
    },
  });

  const { phase, onBegin: phaseBegin, onStop: phaseStop, onForceRecording: phaseForceRecording } = useVoicePhase({
    micState,
    auditEvents,
    structlogEvents,
    lastPostStatus,
  });

  useEffect(() => { onPhaseChange?.(phase); }, [phase, onPhaseChange]);

  // Demo file path: POST pre-recorded audio through the real pipeline.
  // Mirrors the onStop callback — same error handling, same crisis branch.
  // Calls phaseStop() when POST settles so POST_RESOLVED watcher fires
  // (it requires phase to be transcribing/extracting).
  const startDemoFile = async (filename: 'yusuf' | 'mariam') => {
    try {
      const resp = await postDemoRunIntake({
        filename,
        lang: speakerLanguage,
        sourceDeviceId,
        intakeId: intakeIdRef.current,
      });
      setUploadError(null);
      phaseStop();                    // recording → transcribing
      setLastPostStatus('completed'); // triggers POST_RESOLVED → done
      if (resp.is_crisis) {
        onCrisisResponseRef.current?.(resp.locale_aware_message ?? null);
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
      phaseStop(); // drop out of recording so UI doesn't stay stuck
    }
  };

  // Demo display override — pure visual, does not affect real phase machine
  const displayPhase: VoicePhase = demoPhase ?? phase;

  const waveState =
    displayPhase === 'recording' ? 'recording' :
    displayPhase === 'transcribing' || displayPhase === 'extracting' ? 'processing' :
    'idle';

  /* S6 chrome split: caption + Begin/Stop button labels are operator
     chrome and read workerLanguage. The ready-copy paragraph (below)
     is the speaker-facing greeting and reads speakerLanguage; its
     dir attribute follows speakerLanguage too. */
  const caption = voiceCopy[displayPhase].en;
  const stopLabel = t('voice.stop', workerLanguage);
  const speakerRtl = dirFor(speakerLanguage) === 'rtl';

  const showBegin = displayPhase === 'ready' || displayPhase === 'done' || displayPhase === 'saved';
  const showStop = displayPhase === 'recording' || displayPhase === 'transcribing' || displayPhase === 'extracting';
  const beginLabel = displayPhase === 'saved' ? 'Begin new intake' : t('voice.begin', workerLanguage);

  /* Mic-icon chrome cycles per design ref nav-app.jsx:144-149. */
  const micIconCls =
    displayPhase === 'recording' ? 'border-red/40 text-red bg-red-soft' :
    displayPhase === 'transcribing' || displayPhase === 'extracting' ? 'border-line text-primary bg-primary-soft' :
    displayPhase === 'awaiting' ? 'border-primary/30 text-primary bg-primary-soft' :
    'border-line text-ink';

  const handleBegin = () => {
    // "Begin new intake" in saved phase: reset, then check for queued demo.
    if (displayPhase === 'saved') {
      const syntheticQueued = syntheticDemoRef?.current;
      if (syntheticQueued) {
        syntheticDemoRef!.current = null;
        syntheticQueued();
        return;
      }
      onBeginNewIntake?.();
      return;
    }
    // Synthetic demo queued via ⌘⇧J/⌘⇧K — run it instead of mic capture.
    const syntheticQueued = syntheticDemoRef?.current;
    if (syntheticQueued) {
      syntheticDemoRef!.current = null;
      syntheticQueued();
      return;
    }
    onBegin?.();
    phaseBegin();
    setLastPostStatus(null);
    const queued = demoFileRef.current;
    if (queued) {
      demoFileRef.current = null;
      phaseForceRecording(); // awaiting → recording (waveform animates)
      void startDemoFile(queued);
      return;
    }
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
        {displayPhase !== 'ready' && (
          <TranscriptStrip
            structlogEvents={structlogEvents}
            isSaved={displayPhase === 'saved'}
          />
        )}
      </div>
    </div>
  );
}

/* Language code → display label for the SPOKEN LANGUAGE metadata field. */
const LANG_LABELS: Record<string, string> = {
  en: 'English',
  es: 'Spanish (Latin America)',
  ar: 'Arabic (Levantine)',
  fa: 'Farsi / Dari',
  fr: 'French',
  uk: 'Ukrainian',
};

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
// MinorStrip is now rendered inside RecordCard (V3 — B2-S19).

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
  onRunMariam: () => void;
};

function DemoDock({ visible, onStart, onReset, onMatch, onNetworkMatch, onCrisis, onSplit, onClose, phase, view, onRunYusufDemo, onRunMariam }: DemoDockProps) {
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
      {/* Fixtures — recording-day fallback sequencers */}
      <div className="mt-2.5 pt-2 border-t border-hair">
        <div className="text-[10px] font-medium uppercase tracking-wider text-muted/60 mb-1.5">Fixtures</div>
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" variant="ghost" disabled={!demoReady} onClick={onRunYusufDemo}>
            Run Yusuf intake
          </Button>
          <Button size="sm" variant="ghost" disabled={!demoReady} onClick={onRunMariam}>
            Run Mariam intake
          </Button>
        </div>
      </div>
    </div>
  );
}


// ---------- Main App ------------------------------------------------------
function App() {
  const [record, setRecord]                   = useState<RecordData>(INITIAL_RECORD);
  const [phase, setPhase]                     = useState<Phase>("ready");
  const [view, setView]                       = useState<View>("single");
  const [matchPhase, setMatchPhase]           = useState<MatchPhase>("split");
  const [networkMatchResult, setNetworkMatchResult] = useState<NetworkMatchResult | null>(null);
  const [demoStructlogEvents, setDemoStructlogEvents] = useState<StructlogEnvelope[]>([]);
  // Stores the record from the previous completed intake so the match graph
  // can show real node data (Side A) when two live intakes produce a match.
  const [prevRecord, setPrevRecord] = useState<RecordData | null>(null);
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
  const demoFileRef = useRef<'yusuf' | 'mariam' | null>(null);
  const callIdRef = useRef(0);
  const pendingPostCrisisRef = useRef<(() => void) | null>(null);
  const syntheticDemoRef = useRef<(() => void) | null>(null);

  // Queue records — fetched on view=queue mount; drives rail badge count
  const { records: queueRecords, refetch: refetchQueue } = useQueueRecords(view === 'queue');

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

  // Fires the moment Begin is clicked — anchors the timer and trace
  // timestamps before any phase dispatch or React batching can intervene.
  const handleBeginIntake = useCallback(() => {
    demoStartRef.current = performance.now();
    setTimerSec(0);
    setTimerRunning(true);
  }, []);

  // Stable identity prevents VoicePanel's useEffect([phase, onPhaseChange])
  // from re-firing on every App render. Timer is now owned by onBegin;
  // this callback only syncs App phase and handles the reset path.
  const handlePhaseChange = useCallback((vp: VoicePhase) => {
    const map: Record<VoicePhase, Phase> = {
      ready: 'ready', awaiting: 'recording', recording: 'recording',
      transcribing: 'processing', extracting: 'extracting',
      done: 'done', saved: 'saved',
    };
    setPhase(map[vp]);
    if (vp === 'ready') {
      // Error/reset path — stop and zero the timer.
      setTimerRunning(false);
      setTimerSec(0);
    }
  }, []);

  // ----- Keyboard shortcuts (single handler, explicit precedence)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = isMac ? e.metaKey : e.ctrlKey;
      // ESC — crisis > presentation > nothing
      if (e.key === 'Escape') {
        if (crisisOpen) {
        setCrisisOpen(false); setCrisisMessage(null);
        pendingPostCrisisRef.current?.(); pendingPostCrisisRef.current = null;
        return;
      }
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
      // ⌘⇧Y — queue Yusuf demo file (real pipeline on Begin); ?dev=1 keeps synthetic path
      if (e.shiftKey && (e.key === 'Y' || e.key === 'y')) {
        e.preventDefault();
        if (devMode) { runYusufDemo(); return; }
        demoFileRef.current = 'yusuf';
        return;
      }
      // ⌘⇧M — queue Mariam demo file; ?dev=1 keeps synthetic path
      if (e.shiftKey && (e.key === 'M' || e.key === 'm')) {
        e.preventDefault();
        if (devMode) { runMariam(); return; }
        demoFileRef.current = 'mariam';
        return;
      }
      // ⌘⇧J — queue Yusuf synthetic demo; fires on next Begin press
      if (e.shiftKey && (e.key === 'J' || e.key === 'j')) {
        e.preventDefault(); syntheticDemoRef.current = runSyntheticYusuf; return;
      }
      // ⌘⇧K — queue Mariam synthetic demo; fires on next Begin press
      if (e.shiftKey && (e.key === 'K' || e.key === 'k')) {
        e.preventDefault(); syntheticDemoRef.current = runSyntheticMariam; return;
      }
      // ⌘⇧R — reset and re-seed
      if (e.shiftKey && (e.key === 'R' || e.key === 'r')) {
        e.preventDefault(); onReset(); return;
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

  // Maps App Phase to VoicePhase for the demo display override on VoicePanel
  const voicePhasemap: Record<Phase, VoicePhase> = {
    ready:      'ready',
    recording:  'recording',
    processing: 'transcribing',
    extracting: 'extracting',
    done:       'done',
    saved:      'saved',
  };

  // ----- Derived state
  const minor = !!record.age && parseInt(record.age, 10) > 0 && parseInt(record.age, 10) < 18;
  const guardianFilled = minor && Object.values(record.guardian).every(v => !!v && v.trim() !== "");
  const statusLabel = minor && !guardianFilled
    ? "Incomplete — Minor Protection Required"
    : phase === "done" ? "Intake complete · queued for sync" : "Active intake";
  const statusTone: StatusTone = minor && !guardianFilled ? "amber" : phase === "done" ? "green" : "green";

  // ----- Demo sequencer
  const runDemo = () => {
    // schedule steps relative to wall clock
    demoStartRef.current = performance.now();
    setPhase("recording");
    setTimerRunning(true);
    // v1.1 cleanup: inject via synthetic intake_created event once useEventStream exposes dispatch
    setRecord(prev => ({
      ...prev,
      recordId: '00000000-0000-0000-0000-000000000147',
      capturedAt: new Date().toISOString(),
      syncStatus: 'queued' as const,
      language: 'Spanish (Latin America)',
    }));
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

  // Maps a completed RecordData to the NetworkCardData shape consumed by
  // the match graph. Side A = the saved record from the previous intake.
  const toNetworkCard = (r: RecordData, tone: 'warm' | 'cool'): NetworkCardData => ({
    title: r.recordId ? `Session ${r.recordId.slice(0, 8)}` : 'Intake',
    tone,
    speakerLanguage: (r.language?.toLowerCase().startsWith('ar') ? 'ar'
                    : r.language?.toLowerCase().startsWith('fa') ? 'fa'
                    : r.language?.toLowerCase().startsWith('es') ? 'es'
                    : 'en') as Language,
    searcherName: r.searcherName || undefined,
    searcherNameLatin: r.searcherNameLatin || undefined,
    missingName: r.missingPersons[0]?.name ?? r.name,
    missingNameLatin: r.missingPersons[0]?.nameLatin,
    missingAge: r.missingPersons[0]?.age,
    missingRelationship: r.missingPersons[0]?.relationship,
    age: r.missingPersons[0]?.age?.toString() ?? r.age,
    lastSeen: r.lastSeenLocationSource || r.lastSeenLocation,
    lastSeenLatin: r.lastSeenLocationSource ? r.lastSeenLocation : undefined,
    missingPersons: r.missingPersons.map(mp => ({
      name: mp.name,
      nameLatin: mp.nameLatin,
      relationship: mp.relationship,
      age: mp.age,
    })),
    rosterMembers: r.familyRoster.map(fm => ({
      name: fm.name,
      nameLatin: fm.nameLatin,
      relationship: fm.relationship,
      status: fm.status === 'WITH_SEARCHER' ? 'present'
            : fm.status === 'MISSING' ? 'missing'
            : 'known',
      age: fm.age,
    })),
  });

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
    setDemoStructlogEvents([]);
    pendingPostCrisisRef.current = null;
    // Preserve prevRecord across reset when it holds a real completed
    // intake — it becomes Side A for the next intake's match graph.
    // Synthetic demo functions always overwrite prevRecord immediately
    // after calling onReset(), so this doesn't affect them.
    setPrevRecord(prev => (prev?.recordId ? prev : null));
    // Clear SSE reducer state too — without this, intakeId stays
    // pinned to the previous turn's record id and the next mic turn
    // POSTs as an extend (HTTP 500 on crisis-after-Reset).
    resetStream();
  };

  // Shared step executor for both Yusuf and Mariam sequencers.
  // Handles scalar `populate` steps and raw `populateRaw` patch steps.
  const runSteps = (steps: DemoStep[]) => {
    steps.forEach((step) => {
      setTimeout(() => {
        const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
        if (step.state) setPhase(step.state);
        if (step.populate) {
          const populateKey = step.populate;
          const value = step.value;
          setRecord(prev => {
            const next = { ...prev, [populateKey]: value };
            if (step.lastSeenLocationSource) next.lastSeenLocationSource = step.lastSeenLocationSource;
            return next;
          });
          setJustPopulated(populateKey);
          setTimeout(() => setJustPopulated(j => j === populateKey ? null : j), 2500);
        }
        if (step.populateRaw) {
          const patch = step.populateRaw;
          setRecord(prev => ({ ...prev, ...patch }));
          // Use the first key in the patch as the highlight key
          const firstKey = Object.keys(patch)[0];
          if (firstKey) {
            setJustPopulated(firstKey);
            setTimeout(() => setJustPopulated(j => j === firstKey ? null : j), 2500);
          }
        }
        if (step.trace) logCall(step.trace, t);
        if (step.structlog) {
          const payload = step.structlog;
          setDemoStructlogEvents(prev => [...prev, {
            type: 'structlog_event' as const,
            at: new Date().toISOString(),
            source_device_id: null,
            payload: { ...payload },
          }]);
        }
      }, step.at);
    });
  };

  const runYusufDemo = () => {
    onReset();
    demoStartRef.current = performance.now();
    setPhase("recording");
    setTimerRunning(true);
    setTimerSec(0);
    setSpeakerLanguage("ar");
    // v1.1 cleanup: inject via synthetic intake_created event once useEventStream exposes dispatch
    setRecord(prev => ({
      ...prev,
      recordId: '00000000-0000-0000-0000-000000000042',
      capturedAt: new Date().toISOString(),
      syncStatus: 'queued' as const,
      language: 'Arabic (Levantine)',
    }));
    logCall({ name: "session.start", args: { session_id: 42 }, result: "ok" }, 0);

    runSteps(YUSUF_DEMO_STEPS);

    const lastAt = YUSUF_DEMO_STEPS[YUSUF_DEMO_STEPS.length - 1].at;
    setTimeout(() => {
      const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
      logCall({ name: "escalate_crisis",
                args: { signal: "distress_keyword", lang: "ar" },
                result: "referral_card_elevated" }, t);
      setCrisisOpen(true);
      setPhase("done");
      refetchQueue();
    }, lastAt + 600);
  };

  const runMariam = () => {
    onReset();
    demoStartRef.current = performance.now();
    setPhase("recording");
    setTimerRunning(true);
    setSpeakerLanguage("ar");
    // v1.1 cleanup: inject via synthetic intake_created event once useEventStream exposes dispatch
    setRecord(prev => ({
      ...prev,
      recordId: '00000000-0000-0000-0000-000000000049',
      capturedAt: new Date().toISOString(),
      syncStatus: 'queued' as const,
      language: 'Arabic (Levantine)',
    }));
    // Synthesize match candidate so activeMatchCount > 0 when Save fires
    setMatchCandidates(prev => applyMatchProposed(
      prev,
      '00000000-0000-0000-0000-000000000049',
      1,
      ['00000000-0000-0000-0000-000000000049', '00000000-0000-0000-0000-000000000042'],
      new Date().toISOString(),
    ));
    logCall({ name: "session.start", args: { session_id: 49 }, result: "ok" }, 0);

    runSteps(MARIAM_DEMO_STEPS);

    const lastAt = MARIAM_DEMO_STEPS[MARIAM_DEMO_STEPS.length - 1].at;
    setTimeout(() => {
      const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
      logCall({ name: "submit_record",
                args: { status: "complete" },
                result: "queued_local" }, t);
      setPhase("done");
      refetchQueue();
    }, lastAt + 600);
  };

  const runSyntheticYusuf = () => {
    onReset();
    demoStartRef.current = performance.now();
    setSpeakerLanguage("ar");
    setRecord(prev => ({
      ...prev,
      recordId: '00000000-0000-0000-0000-000000000042',
      capturedAt: new Date().toISOString(),
      syncStatus: 'queued' as const,
      language: 'Arabic (Levantine)',
    }));
    setTimerRunning(true);
    setTimerSec(0);
    logCall({ name: "session.start", args: { session_id: 42 }, result: "ok" }, 0);
    runSteps(SYNTHETIC_YUSUF_STEPS);
    const lastAt = SYNTHETIC_YUSUF_STEPS[SYNTHETIC_YUSUF_STEPS.length - 1].at;
    setTimeout(() => {
      const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
      setDemoStructlogEvents(prev => [...prev, {
        type: 'structlog_event' as const,
        at: new Date().toISOString(),
        source_device_id: null,
        payload: { event: "tool_call_invoked", tool: "escalate_crisis", score: 0.91, anchor: "ما عاد فيني أكمل" },
      }]);
      logCall({ name: "escalate_crisis",
                args: { score: 0.91, anchor: "ما عاد فيني أكمل", lang: "ar" },
                result: "referral_card_elevated" }, t);
      setCrisisOpen(true);
      pendingPostCrisisRef.current = () => {
        const t2 = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
        setDemoStructlogEvents(prev => [...prev,
          { type: 'structlog_event' as const, at: new Date().toISOString(), source_device_id: null,
            payload: { event: "tool_call_invoked", tool: "submit_record", status: "complete" } },
          { type: 'structlog_event' as const, at: new Date().toISOString(), source_device_id: null,
            payload: { event: "record_state", state: "complete", fields_extracted: 8 } },
        ]);
        logCall({ name: "submit_record", args: { status: "complete" }, result: "queued_local" }, t2);
        logCall({ name: "intake_records_listed", args: { count: 1 }, result: "KIN-2026-0042" }, t2 + 300);
        setPhase("done");
        refetchQueue();
      };
    }, lastAt + 500);
  };

  const runSyntheticMariam = () => {
    onReset();
    // Seed Side A with Yusuf's completed record so the match graph shows
    // "INTAKE A · YUSUF AL-OMAR" rather than falling back to the fixture.
    setPrevRecord({
      ...INITIAL_RECORD,
      recordId: '00000000-0000-0000-0000-000000000042',
      capturedAt: new Date().toISOString(),
      syncStatus: 'queued' as const,
      language: 'Arabic (Levantine)',
      searcherName: 'يوسف العمر',
      searcherNameLatin: 'Yusuf Al-Omar',
      missingPersons: [
        { name: 'مريم', nameLatin: 'Mariam', age: 32, relationship: 'أختي', status: 'MISSING',
          lastSeen: 'البوابة الجنوبية', marks: [] },
        { name: 'محمد', nameLatin: 'Mohamad', age: 8, relationship: 'ابن أختي', status: 'MISSING',
          lastSeen: 'البوابة الجنوبية', marks: ['ندبة فوق الحاجب الأيسر · scar above left brow'] },
      ],
      familyRoster: [
        { name: 'عائشة', nameLatin: 'Aisha', relationship: 'زوجتي', status: 'WITH_SEARCHER' },
      ],
      lastSeenLocation: 'Southern gate — camp perimeter',
      lastSeenLocationSource: 'البوابة الجنوبية',
      lastSeenDate: '3 days ago',
      circumstance: 'Separated during crowd surge at the southern gate',
      physicalDesc: 'Mohamad: scar above left eyebrow',
    });
    demoStartRef.current = performance.now();
    setSpeakerLanguage("ar");
    setRecord(prev => ({
      ...prev,
      recordId: '00000000-0000-0000-0000-000000000049',
      capturedAt: new Date().toISOString(),
      syncStatus: 'queued' as const,
      language: 'Arabic (Levantine)',
    }));
    setMatchCandidates(prev => applyMatchProposed(
      prev,
      '00000000-0000-0000-0000-000000000049',
      1,
      ['00000000-0000-0000-0000-000000000049', '00000000-0000-0000-0000-000000000042'],
      new Date().toISOString(),
    ));
    setTimerRunning(true);
    setTimerSec(0);
    logCall({ name: "session.start", args: { session_id: 49 }, result: "ok" }, 0);
    runSteps(SYNTHETIC_MARIAM_STEPS);
    const lastAt = SYNTHETIC_MARIAM_STEPS[SYNTHETIC_MARIAM_STEPS.length - 1].at;
    setTimeout(() => {
      const t = demoStartRef.current === null ? 0 : performance.now() - demoStartRef.current;
      setDemoStructlogEvents(prev => [...prev,
        { type: 'structlog_event' as const, at: new Date().toISOString(), source_device_id: null,
          payload: { event: "tool_call_invoked", tool: "submit_record", status: "complete" } },
        { type: 'structlog_event' as const, at: new Date().toISOString(), source_device_id: null,
          payload: { event: "record_state", state: "complete", fields_extracted: 8 } },
      ]);
      logCall({ name: "submit_record", args: { status: "complete" }, result: "queued_local" }, t);
      logCall({ name: "intake_records_listed", args: { count: 2 }, result: "KIN-2026-0049" }, t + 300);
      setPhase("done");
      refetchQueue();
    }, lastAt + 500);
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

  const fireNodeMatchCalls = () => {
    const t0 = performance.now();
    setTimeout(() => logCall({
      name: "node_match",
      args: { pair: "محمد ↔ محمد", type: "missing_person → missing_person", score: 0.85 },
      result: "primary_match", highlight: true,
    }, performance.now() - t0), 800);
    setTimeout(() => logCall({
      name: "node_match",
      args: { pair: "مريم ↔ مريم", type: "missing_person → searcher", score: 0.85 },
      result: "supporting_match",
    }, performance.now() - t0), 1800);
    setTimeout(() => logCall({
      name: "node_match",
      args: { pair: "يوسف ↔ يوسف", type: "searcher → missing_person", score: 0.85 },
      result: "supporting_match",
    }, performance.now() - t0), 2800);
  };

  const onSimulateNetworkMatch = () => {
    setNetworkMatchResult(DEFAULT_NETWORK_RESULT);
    setView("match");
    setMatchPhase("split");
    setTimeout(() => setMatchPhase("linking"), 400);
    setTimeout(() => setMatchPhase("merged"), 3400);
  };

  const handleSave = () => {
    logCall({ name: "submit_record",
              args: { status: "complete" },
              result: "queued_local" },
             timerRunning ? timerSec * 1000 : 0);
    setTimerRunning(false);
    refetchQueue();
    setPhase('saved');
    // Snapshot current record as Side A for the match graph, but only if
    // prevRecord isn't already seeded with a different intake (synthetic
    // Mariam demo pre-seeds Yusuf as Side A before Mariam's fields populate).
    setPrevRecord(prev =>
      prev && prev.recordId && prev.recordId !== record.recordId ? prev : record
    );
    // No auto-route. If activeMatchCount > 0 the queue rail badge
    // lights up; worker clicks the badge to navigate to match view.
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
        sessionLabel={streamState.intakeId
          ? `Session ${streamState.intakeId.slice(0, 8)}…`
          : 'Session —'}
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
            if (next === 'intake' && activeMatchCount > 0) {
              // Match candidate pending — intake badge click goes to match view.
              // Use the live networkMatchResult from SSE if available; fall back
              // to the demo fixture only when no live result has been received.
              if (!networkMatchResult) setNetworkMatchResult(DEFAULT_NETWORK_RESULT);
              setView('match');
              setMatchPhase('split');
              setTimeout(() => setMatchPhase('linking'), 400);
              setTimeout(() => setMatchPhase('merged'), 3400);
              fireNodeMatchCalls();
            } else {
              setView(next === 'queue' ? 'queue' : 'single');
            }
          }}
          queuedCount={queueRecords.length}
          pendingMatchCount={activeMatchCount || undefined}
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
                    structlogEvents={[...streamState.structlogEvents, ...demoStructlogEvents]}
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
                    demoPhase={phase !== 'ready' ? voicePhasemap[phase] : undefined}
                    onBeginNewIntake={() => { onReset(); }}
                    demoFileRef={demoFileRef}
                    syntheticDemoRef={syntheticDemoRef}
                    onPhaseChange={handlePhaseChange}
                    onBegin={handleBeginIntake}
                  />
                </div>

                {/* Match-ready banner — visible after save when a candidate is pending */}
                {phase === 'saved' && activeMatchCount > 0 && (
                  <div className="mb-5 flex items-center gap-3 px-4 py-3 bg-green-soft border border-green/30 rounded-kin-lg">
                    <span className="w-2 h-2 rounded-full bg-green shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="text-[13px] font-medium text-ink">Match candidate found</span>
                      <span className="text-[13px] text-muted ml-2">
                        {activeMatchCount} record{activeMatchCount > 1 ? 's' : ''} in queue may be related
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        if (!networkMatchResult) setNetworkMatchResult(DEFAULT_NETWORK_RESULT);
                        setView('match');
                        setMatchPhase('split');
                        setTimeout(() => setMatchPhase('linking'), 400);
                        setTimeout(() => setMatchPhase('merged'), 3400);
                        fireNodeMatchCalls();
                      }}
                      className="shrink-0 px-3 h-8 text-[12px] font-medium rounded-kin bg-white border border-green/40 text-[oklch(0.38_0.1_155)] hover:bg-green-soft transition-colors"
                    >
                      Review match →
                    </button>
                  </div>
                )}

                {/* Chiclet ribbon — family-network completeness (S19) */}
                <div className="mb-4">
                  <ChicletRibbon
                    searcherName={record.searcherName}
                    missingPersonsCount={record.familyRoster.filter(m => m.status !== 'WITH_SEARCHER').length}
                    detailedCount={record.familyRoster.filter(
                      m => m.status !== 'WITH_SEARCHER' && (
                        !!m.lastSeen || !!record.lastSeenLocation ||
                        (m.marks && m.marks.length > 0)
                      )
                    ).length}
                  />
                </div>

                {/* Save button — above card, top-right (S19) */}
                <div className="flex items-end justify-between mb-2 min-h-[40px]">
                  <div />
                  {phase === 'done' && (
                    <div className="flex flex-col items-end gap-0.5">
                      <button
                        type="button"
                        onClick={handleSave}
                        className="px-4 h-9 text-[13px] font-medium rounded-kin bg-primary text-white hover:bg-primary-2 transition-colors"
                      >
                        Save record
                      </button>
                      <span className="text-[11px] text-muted">Commits record and checks for matches in queue</span>
                    </div>
                  )}
                </div>

                {/* Record card — enriched with metadata */}
                <RecordCard
                  record={{
                    ...record,
                    // SSE path wins when available; demo-path setRecord patches are the fallback
                    recordId: streamState.intakeId ?? record.recordId,
                    capturedAt: streamState.capturedAt ?? record.capturedAt,
                    // syncStatus: queued once intake starts, local until then
                    syncStatus: (streamState.intakeId ?? record.recordId)
                      ? (record.syncStatus ?? 'queued')
                      : 'local',
                    // Language: derive display label from speakerLanguage once intake starts
                    language: record.language || (
                      (streamState.intakeId ?? record.recordId)
                        ? LANG_LABELS[speakerLanguage] ?? speakerLanguage
                        : ''
                    ),
                  }}
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
                    phase={phase}
                    onSave={handleSave}
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
                    phase={phase}
                    onSave={handleSave}
                  />
                </div>
              </>
            )}

            {view === "match" && (
              networkMatchResult && networkMatchResult.node_matches.length >= 2
                ? <NetworkMatch
                    phase={matchPhase}
                    onBack={() => setView("single")}
                    onNewIntake={() => { onReset(); setView("single"); }}
                    workerLanguage={workerLanguage}
                    networkResult={networkMatchResult}
                    recordA={prevRecord ? toNetworkCard(prevRecord, 'warm') : undefined}
                    recordB={toNetworkCard(record, 'cool')}
                    intakeIdA={prevRecord?.recordId}
                    intakeIdB={record.recordId}
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
            const hadPending = !!pendingPostCrisisRef.current;
            pendingPostCrisisRef.current?.(); pendingPostCrisisRef.current = null;
            // Real pipeline: pendingPostCrisisRef is null (synthetic sets it).
            // Advance phase to 'done' so Save button appears.
            if (!hadPending) setPhase('done');
            logCall({ name: "crisis.resolve", args: { outcome: "referral_provided" } },
                    timerRunning ? timerSec * 1000 : 0);
            if (streamState.intakeId) {
              void postCrisisResolved({
                intakeId: streamState.intakeId,
                resolution: 'referral_provided',
                referralOrganization: 'ICRC Family Links Network',
              });
            }
          }}
          onDeEscalated={() => {
            setCrisisOpen(false);
            setCrisisMessage(null);
            const hadPending = !!pendingPostCrisisRef.current;
            pendingPostCrisisRef.current?.(); pendingPostCrisisRef.current = null;
            // Real pipeline: pendingPostCrisisRef is null (synthetic sets it).
            // Advance phase to 'done' so Save button appears.
            if (!hadPending) setPhase('done');
            logCall({ name: "crisis.resolve", args: { outcome: "de_escalated" } },
                    timerRunning ? timerSec * 1000 : 0);
            if (streamState.intakeId) {
              void postCrisisResolved({
                intakeId: streamState.intakeId,
                resolution: 'de_escalated',
              });
            }
          }}
        />
      )}

      {/* DemoDock + reopen pill — hidden in presentation mode and without ?dev=1 */}
      {devMode && demoDockVisible && !presentationActive && (
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
          onRunMariam={runMariam}
        />
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
