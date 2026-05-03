/* Presentation-mode hook — ⌘⇧P only. NOT a UI scripter.
   Three responsibilities (prototype DO-NOT-CHANGE):
     1. Activates/deactivates via ⌘⇧P or ?present=1 URL param
     2. Verifies PRESENTATION_INITIAL_QUEUE_IDS on activation; warns if missing
     3. Dismisses the coachmark localStorage key on activation
   ESC is handled in App.tsx (crisis > presentation precedence — not here). */
import { useState, useEffect } from 'react';
import type { IntakeRecord } from '../lib/intakeRecord';

// Deterministic UUIDs from src/integration/fixture_seed.py constants.
// All four fixture records must be seeded before presentation mode activates.
const PRESENTATION_INITIAL_QUEUE_IDS = [
  '00000000-0000-0000-0000-000000000042', // Yusuf (paused_for_crisis)
  '00000000-0000-0000-0000-000000000049', // Mariam (complete)
  '00000000-0000-0000-0000-000000000089', // Ambient A — Spanish (complete)
  '00000000-0000-0000-0000-000000000102', // Ambient B — Farsi (partial)
];

export type UsePresentationModeResult = {
  presentationActive: boolean;
  setPresentationActive: (active: boolean) => void;
  hudHidden: boolean;
  setHudHidden: (hidden: boolean) => void;
};

export function usePresentationMode(
  queueRecords: IntakeRecord[],
): UsePresentationModeResult {
  const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);
  const [presentationActive, setPresentationActive] = useState(
    () => new URLSearchParams(window.location.search).has('present'),
  );
  const [hudHidden, setHudHidden] = useState(false);

  // Verify seed contract + set coachmark-dismissed key on activation
  useEffect(() => {
    if (!presentationActive) return;
    localStorage.setItem('kin.coachmark.dismissed', 'true');
    const recordIds = queueRecords.map(r => {
      const n = parseInt(r.id, 10);
      return isNaN(n) ? r.id : n;
    });
    for (const expected of PRESENTATION_INITIAL_QUEUE_IDS) {
      if (!recordIds.includes(expected)) {
        console.warn(
          `[KIN] Presentation mode: expected record id=${expected} not found in queue. ` +
          `Bundle 2 fixture seeding is required for Beat 6 demo.`,
        );
      }
    }
  }, [presentationActive, queueRecords]);

  // ⌘⇧P toggle + H key for HUD
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = isMac ? e.metaKey : e.ctrlKey;
      if (mod && e.shiftKey && (e.key === 'p' || e.key === 'P')) {
        e.preventDefault();
        setPresentationActive(v => !v);
        return;
      }
      if (presentationActive && (e.key === 'h' || e.key === 'H')) {
        const tag = (document.activeElement as HTMLElement | null)?.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
          setHudHidden(v => !v);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isMac, presentationActive]);

  return { presentationActive, setPresentationActive, hudHidden, setHudHidden };
}
