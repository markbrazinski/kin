/* IntakePanel — self-contained intake-rendering surface.

   Owns its own SSE subscription via useEventStream and renders
   IntakeTimer, MinorStrip, VoicePanel, CompletenessMeter, RecordCard
   from the hook's reducer state.

   Tent differentiation (split-view): tent="a" vs tent="b" picks the
   header accent color and font; both panels share the same
   high-contrast body theme.
*/
import { useEffect, useRef, useState } from 'react';
import { CompletenessMeter, Chip } from './primitives';
import { RecordCard } from './RecordCard';
import { StructlogSidebar } from './StructlogSidebar';
import { IconLock } from './icons';
import { useEventStream, type EventSourceFactory } from '../hooks/useEventStream';
import { useMicCapture } from '../hooks/useMicCapture';
import {
  useVoicePhase,
  type PostStatus,
} from '../hooks/useVoicePhase';
import { formatTimestamp, type Tent } from '../lib/formatters';
import { containsNonLatinScript } from '../lib/script';
import { uploadAudioBlob } from '../lib/api';
import { voiceCopy } from '../lib/voiceCopy';
import { t } from '../lib/i18n';
import type {
  AuditEnvelope,
  StructlogEnvelope,
} from '../lib/sseEnvelope';
import type {
  CompletenessSegment,
  Language,
  RecordData,
} from '../lib/types';

export type IntakePanelProps = {
  /* Optional — when undefined, the underlying SSE stream is unfiltered. */
  sourceDeviceId?: string;
  /* Single-panel mode passes no tent (defaults to 'a' look). Split mode
     passes 'a' or 'b' explicitly. */
  tent?: Tent;
  panelLabel?: string;
  /* Bundle 1.5 S6 split: workerLanguage drives chrome (caption +
     button labels in SimpleVoicePanel). speakerLanguage is the
     language Whisper/Gemma/safety see via the POST and the chip
     metadata showing what the speaker is saying. */
  workerLanguage: Language;
  speakerLanguage: Language;
  timerSec: number;
  timerRunning: boolean;
  crisisOpen: boolean;
  /* Test DI seam — optional. */
  eventSourceFactory?: EventSourceFactory;
  /* Optional fallback record for offline (runDemo) mode in single-panel. */
  fallbackRecord?: RecordData;
  fallbackJustPopulated?: string | null;
};

const ACCENT_BY_TENT: Record<Tent, 'primary' | 'amber'> = {
  a: 'primary',
  b: 'amber',
};

const HEADER_FONT_BY_TENT: Record<Tent, string> = {
  a: 'font-sans',
  b: 'font-mono',
};

export function IntakePanel({
  sourceDeviceId,
  tent = 'a',
  panelLabel = 'Intake',
  workerLanguage,
  speakerLanguage,
  timerSec,
  timerRunning,
  crisisOpen,
  eventSourceFactory,
  fallbackRecord,
  fallbackJustPopulated = null,
}: IntakePanelProps) {
  const { state } = useEventStream({
    sourceDeviceId,
    eventSourceFactory,
  });

  /* Prefer the SSE-driven record when ANY audit event has arrived;
     fall back to the App-level demo record otherwise (single-panel
     offline mode). */
  const record =
    state.auditEvents.length > 0 || !fallbackRecord
      ? state.record
      : fallbackRecord;

  /* Highlight-key on most recent field_extracted, with auto-clear. */
  const [justPopulated, setJustPopulated] = useState<string | null>(null);
  useEffect(() => {
    const last = state.auditEvents[state.auditEvents.length - 1];
    if (!last || last.payload.event_type !== 'field_extracted') return;
    const fieldName = (last.payload.details as { field_name?: string })
      .field_name;
    if (!fieldName) return;
    setJustPopulated(fieldName);
    const handle = setTimeout(
      () => setJustPopulated((j) => (j === fieldName ? null : j)),
      2500,
    );
    return () => clearTimeout(handle);
  }, [state.auditEvents.length]);

  const populatedKey = justPopulated ?? fallbackJustPopulated;

  /* Worker-entered Latin-script transliteration. Local component
     state in S4 — pipeline POST integration is post-bundle. */
  const [transliteration, setTransliteration] = useState('');
  const showTransliterationField =
    !!record.name && containsNonLatinScript(record.name);

  const minor = !!record.age && parseInt(record.age, 10) > 0 && parseInt(record.age, 10) < 18;
  const guardianFilled =
    minor && Object.values(record.guardian).every((v) => !!v && v.trim() !== '');

  const segments: CompletenessSegment[] = [
    { key: 'name', label: 'Name', filled: !!record.name },
    { key: 'age', label: 'Age', filled: !!record.age },
    { key: 'rel', label: 'Relationship', filled: !!record.relationship },
    {
      key: 'ls',
      label: 'Last seen',
      filled: !!(record.lastSeenLocation && record.lastSeenDate),
    },
    {
      key: 'marks',
      label: 'Marks',
      filled: !!(record.physicalDesc && record.features),
    },
    ...(minor
      ? [{ key: 'guard', label: 'Guardian/CP', filled: !!guardianFilled }]
      : []),
  ];

  const accent = ACCENT_BY_TENT[tent];
  const headerFont = HEADER_FONT_BY_TENT[tent];
  const now = new Date();

  return (
    <div data-tent={tent} className="w-full">
      {/* Header strip — tent-differentiated chrome */}
      <div
        className={`flex items-center justify-between gap-3 mb-4 pb-3 border-b border-line ${headerFont}`}
      >
        <div className="flex items-center gap-2">
          <Chip tone={accent === 'primary' ? 'primary' : 'amber'}>
            {panelLabel}
          </Chip>
          <span className="text-[12px] text-muted">
            {formatTimestamp(now, tent)}
          </span>
        </div>
        <div className="text-[11px] text-muted uppercase tracking-wider">
          {sourceDeviceId ?? 'unfiltered'}
        </div>
      </div>

      {/* Voice panel: simplified, mic-capture-driven (S5). Begin/Stop
          internalizes useMicCapture. */}
      <div className="mb-5">
        <SimpleVoicePanel
          workerLanguage={workerLanguage}
          speakerLanguage={speakerLanguage}
          sourceDeviceId={sourceDeviceId}
          intakeId={state.intakeId}
          auditEvents={state.auditEvents}
          structlogEvents={state.structlogEvents}
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
        justPopulatedKey={populatedKey}
        disabled={crisisOpen}
      />

      {/* Worker-entered transliteration (non-Latin source-script names) */}
      {showTransliterationField && (
        <div className="mt-4 p-3 bg-card border border-line rounded-kin">
          <label className="block">
            <span className="text-[12px] font-medium text-ink">
              Transliteration (worker entry)
            </span>
            <span className="block text-[11px] text-muted mb-1.5">
              Latin-script name for the registry — type as you hear it.
            </span>
            <input
              type="text"
              value={transliteration}
              onChange={(e) => setTransliteration(e.target.value)}
              placeholder="e.g. Mohammed"
              aria-label="Transliteration"
              className="w-full h-9 px-2 text-[14px] text-ink border border-line rounded-kin focus:outline-none focus:border-primary"
            />
          </label>
        </div>
      )}

      <div className="mt-6 text-[12px] text-muted flex items-center gap-2">
        <IconLock size={12} />
        <span>
          Record stored on this device. Will sync when you next connect to the local hub.
        </span>
      </div>

      {/* Per-panel structlog sidebar — credibility surface */}
      <div className="mt-4">
        <StructlogSidebar events={state.structlogEvents} />
      </div>
    </div>
  );
}

/* Compact mic-capture row used inside IntakePanel.

   Internalizes useMicCapture (per S5 lock #4: Begin = real intake;
   runDemo() reachable only via DemoDock's Start demo button). Begin
   button toggles to Stop while recording. On stop, the captured Blob
   is POSTed to /intake/audio with the panel's current intake_id (if
   any). Backend either creates a new record (turn 1) or extends the
   existing one (subsequent turns).
*/
function SimpleVoicePanel({
  workerLanguage,
  speakerLanguage,
  sourceDeviceId,
  intakeId,
  auditEvents,
  structlogEvents,
}: {
  /* S6 split: workerLanguage drives caption + button labels;
     speakerLanguage flows to the POST and surfaces as the chip
     metadata showing what language the speaker is using. */
  workerLanguage: Language;
  speakerLanguage: Language;
  sourceDeviceId: string | undefined;
  intakeId: string | null;
  auditEvents: AuditEnvelope[];
  structlogEvents: StructlogEnvelope[];
}) {
  /* Read intake_id from a ref so the most-recent value is used on
     stop, not whatever was current at render-time. */
  const intakeIdRef = useRef<string | null>(intakeId);
  intakeIdRef.current = intakeId;

  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastPostStatus, setLastPostStatus] = useState<PostStatus | null>(null);

  const { state: micState, start, stop, error } = useMicCapture({
    onStop: async (blob) => {
      if (!sourceDeviceId) {
        setUploadError(
          'sourceDeviceId not configured for this panel; cannot post audio',
        );
        return;
      }
      try {
        const resp = await uploadAudioBlob({
          blob,
          lang: speakerLanguage,
          sourceDeviceId,
          intakeId: intakeIdRef.current,
        });
        setUploadError(null);
        setLastPostStatus(
          resp.status === 'paused_for_crisis' ? 'paused_for_crisis' : 'completed',
        );
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

  const caption = voiceCopy[phase].en;
  const showBegin = phase === 'ready' || phase === 'done';
  const showStop = phase === 'recording';

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
    <div className="flex items-center justify-between p-3 bg-card border border-line rounded-kin">
      <div className="flex items-center gap-3">
        <div className="text-[14px] font-medium text-ink" aria-live="polite">
          {caption}
        </div>
        {/* Chip showing what language the speaker is using —
            metadata about the speaker, not chrome. */}
        <div className="text-[12px] text-muted uppercase tracking-wider">
          {speakerLanguage}
        </div>
        {(error ?? uploadError) && (
          <div className="text-[12px] text-red">
            {error ?? uploadError}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        {showBegin ? (
          <button
            onClick={handleBegin}
            className="text-[12px] font-medium text-primary hover:text-primary-2"
          >
            {t('voice.begin', workerLanguage)}
          </button>
        ) : null}
        {showStop ? (
          <button
            onClick={handleStop}
            className="text-[12px] font-medium text-red hover:opacity-80"
          >
            {t('voice.stop', workerLanguage)}
          </button>
        ) : null}
      </div>
    </div>
  );
}
