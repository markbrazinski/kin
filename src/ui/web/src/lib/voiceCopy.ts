/* Voice-panel caption strings keyed by VoicePhase.

   English only this session. S6 (worker/speaker language) extends
   with worker_language variants once the locale split is wired. */
import type { VoicePhase } from '../hooks/useVoicePhase';

export const voiceCopy: Record<VoicePhase, { en: string }> = {
  ready:        { en: 'Ready to begin intake' },
  awaiting:     { en: 'Listening — speak when ready' },
  recording:    { en: 'Recording' },
  transcribing: { en: 'Transcribing audio…' },
  extracting:   { en: 'Structuring record…' },
  done:         { en: 'Intake complete' },
  saved:        { en: 'Record saved — ready for next intake' },
};
