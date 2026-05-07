/* IntakePanel — self-contained intake-rendering surface.

   Owns its own SSE subscription via useEventStream and renders
   VoicePanel, ChicletRibbon, Save button, RecordCard from the
   hook's reducer state.

   Tent differentiation (split-view): tent="a" vs tent="b" picks the
   header accent color and font; both panels share the same
   high-contrast body theme.

   S19: useVoicePhase lifted to IntakePanel so the Save button (above
   the RecordCard) can call phaseSaved() directly alongside onSave().
*/
import { useCallback, useEffect, useRef, useState } from 'react';
import { Chip } from './primitives';
import { RecordCard } from './RecordCard';
import { ChicletRibbon } from './ChicletRibbon';
import { StructlogSidebar } from './StructlogSidebar';
import { ToolCallsSidebar } from './ToolCallsSidebar';
import { deriveToolCalls } from '../state/toolCalls';
import { IconLock } from './icons';
import { useEventStream, type EventSourceFactory } from '../hooks/useEventStream';
import { useMicCapture } from '../hooks/useMicCapture';
import {
  useVoicePhase,
  type PostStatus,
  type VoicePhase,
} from '../hooks/useVoicePhase';
import { formatTimestamp, type Tent } from '../lib/formatters';
import { containsNonLatinScript } from '../lib/script';
import { uploadAudioBlob } from '../lib/api';
import { voiceCopy } from '../lib/voiceCopy';
import { t } from '../lib/i18n';
import type {
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
  /* S13: Save button — shown when phase is "done". */
  phase?: string;
  onSave?: () => void;
  /* S19: post-save voice panel transition — called after save commits. */
  onSaved?: () => void;
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
  timerSec: _timerSec,
  timerRunning: _timerRunning,
  crisisOpen,
  eventSourceFactory,
  fallbackRecord,
  fallbackJustPopulated = null,
  phase: externalPhase,
  onSave,
  onSaved,
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

  const hasMinor = record.missingPersons.some(
    m => typeof m.age === 'number' && m.age > 0 && m.age < 18
  );
  // Dual-path guard: also check record.age for SSE records not yet using family-network schema.
  const minor = hasMinor || (!!record.age && parseInt(record.age, 10) > 0 && parseInt(record.age, 10) < 18);

  const detailedCount = record.missingPersons.filter(
    m => !!m.lastSeen || (m.marks && m.marks.length > 0)
  ).length;

  // ── Voice phase (lifted from SimpleVoicePanel so Save button can call phaseSaved) ──

  const [lastPostStatus, setLastPostStatus] = useState<PostStatus | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const intakeIdRef = useRef<string | null>(state.intakeId);
  intakeIdRef.current = state.intakeId;

  const { state: micState, start, stop, error: micError } = useMicCapture({
    onStop: useCallback(async (blob: Blob) => {
      if (!sourceDeviceId) {
        setUploadError('sourceDeviceId not configured for this panel; cannot post audio');
        return;
      }
      try {
        await uploadAudioBlob({
          blob,
          lang: speakerLanguage,
          sourceDeviceId,
          intakeId: intakeIdRef.current,
        });
        setUploadError(null);
        setLastPostStatus('completed');
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : String(err));
      }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sourceDeviceId, speakerLanguage]),
  });

  const {
    phase: voicePhase,
    onBegin: phaseBegin,
    onStop: phaseStop,
    onSaved: phaseSaved,
  } = useVoicePhase({
    micState,
    auditEvents: state.auditEvents,
    structlogEvents: state.structlogEvents,
    lastPostStatus,
  });

  const handleBegin = () => {
    phaseBegin();
    setLastPostStatus(null);
    void start();
  };
  const handleStop = () => {
    phaseStop();
    stop();
  };
  const handleSave = () => {
    onSave?.();
    phaseSaved();
    onSaved?.();
  };

  const showSave = (externalPhase === 'done' || voicePhase === 'done') && !!onSave;

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

      {/* Voice panel: compact mic-capture row */}
      <div className="mb-5">
        <SimpleVoicePanel
          workerLanguage={workerLanguage}
          speakerLanguage={speakerLanguage}
          voicePhase={voicePhase}
          micError={micError}
          uploadError={uploadError}
          onBegin={handleBegin}
          onStop={handleStop}
        />
      </div>

      {/* Chiclet ribbon — family-network completeness (replaces CompletenessMeter) */}
      <div className="mb-4">
        <ChicletRibbon
          searcherName={record.searcherName}
          missingPersonsCount={record.missingPersons.length}
          detailedCount={detailedCount}
        />
      </div>

      {/* Save button — outside card, anchored top-right of record-card area */}
      <div className="flex items-end justify-between mb-2 min-h-[40px]">
        <div />
        {showSave && (
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

      {/* Record card — enriched with metadata from SSE state */}
      <RecordCard
        record={{
          ...record,
          recordId: state.intakeId ?? undefined,
          capturedAt: state.capturedAt ?? undefined,
          syncStatus: 'local',
        }}
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

      {/* Per-panel structlog sidebar — system event log */}
      <div className="mt-4">
        <StructlogSidebar events={state.structlogEvents} />
      </div>

      {/* Per-panel tool-calls sidebar — LLM function-call observability */}
      <div className="mt-4">
        <ToolCallsSidebar calls={deriveToolCalls(state.structlogEvents)} />
      </div>
    </div>
  );
}

/* Compact mic-capture row — purely presentational.
   All state lives in IntakePanel; this renders captions and buttons only.
*/
function SimpleVoicePanel({
  workerLanguage,
  speakerLanguage,
  voicePhase,
  micError,
  uploadError,
  onBegin,
  onStop,
}: {
  workerLanguage: Language;
  speakerLanguage: Language;
  voicePhase: VoicePhase;
  micError: string | null;
  uploadError: string | null;
  onBegin: () => void;
  onStop: () => void;
}) {
  const caption = voiceCopy[voicePhase].en;
  const showBegin = voicePhase === 'ready' || voicePhase === 'done' || voicePhase === 'saved';
  const showStop = voicePhase === 'recording';
  const beginLabel = voicePhase === 'saved' ? 'Begin new intake' : t('voice.begin', workerLanguage);

  return (
    <div className="flex items-center justify-between p-3 bg-card border border-line rounded-kin">
      <div className="flex items-center gap-3">
        <div className="text-[14px] font-medium text-ink" aria-live="polite">
          {caption}
        </div>
        <div className="text-[12px] text-muted uppercase tracking-wider">
          {speakerLanguage}
        </div>
        {(micError ?? uploadError) && (
          <div className="text-[12px] text-red">
            {micError ?? uploadError}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        {showBegin ? (
          <button
            onClick={onBegin}
            className="text-[12px] font-medium text-primary hover:text-primary-2"
          >
            {beginLabel}
          </button>
        ) : null}
        {showStop ? (
          <button
            onClick={onStop}
            className="text-[12px] font-medium text-red hover:opacity-80"
          >
            {t('voice.stop', workerLanguage)}
          </button>
        ) : null}
      </div>
    </div>
  );
}
