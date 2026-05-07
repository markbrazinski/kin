/* VoicePanel callback-wiring tests for ADR-004 REV 3.

   Two contracts:
     #6  Crisis POST response invokes onCrisisResponse with the
         locale_aware_message.
     #7  Subsequent stop POSTs with intakeId=null when the previous
         turn was a crisis (Gap 3 — exercised by passing the cleared
         prop through; component reads the latest prop via ref).

   Both tests mock useMicCapture to capture the onStop callback and
   uploadAudioBlob to control the response body — keeps the test off
   real MediaRecorder + fetch.
*/
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, screen } from '@testing-library/react';

type CapturedOpts = {
  onStop?: (blob: Blob) => Promise<void> | void;
};

const captured: CapturedOpts = {};

vi.mock('./hooks/useMicCapture', () => ({
  useMicCapture: (opts: CapturedOpts) => {
    captured.onStop = opts.onStop;
    return { state: 'idle' as const, start: vi.fn(), stop: vi.fn(), error: null };
  },
}));

/* Mockable phase value for the parameterized phase-render test below.
   The 3 ADR-004 REV 3 crisis-wiring tests don't read this — they only
   exercise the onStop callback path. */
const mockPhase = { current: 'ready' as 'ready' | 'awaiting' | 'recording' | 'transcribing' | 'extracting' | 'done' };
vi.mock('./hooks/useVoicePhase', () => ({
  useVoicePhase: () => ({
    phase: mockPhase.current,
    isCrisis: false,
    onBegin: vi.fn(),
    onStop: vi.fn(),
    reset: vi.fn(),
  }),
}));

const uploadAudioBlobMock = vi.fn();
vi.mock('./lib/api', () => ({
  uploadAudioBlob: (...args: unknown[]) => uploadAudioBlobMock(...args),
}));

import { VoicePanel } from './App';
import { voiceCopy } from './lib/voiceCopy';

beforeEach(() => {
  captured.onStop = undefined;
  uploadAudioBlobMock.mockReset();
});

describe('VoicePanel — crisis wiring (ADR-004 REV 3)', () => {
  it('test #6 — crisis POST response invokes onCrisisResponse with the message', async () => {
    uploadAudioBlobMock.mockResolvedValueOnce({
      intake_id: 'rec-1',
      status: 'partial',
      is_crisis: true,
      locale_aware_message: 'يرجى الاتصال بالرقم',
    });

    const onCrisisResponse = vi.fn();
    render(
      <VoicePanel
        workerLanguage="en"
        speakerLanguage="ar"
        elapsedSec={0}
        sourceDeviceId="tent_b"
        intakeId={null}
        auditEvents={[]}
        structlogEvents={[]}
        onCrisisResponse={onCrisisResponse}
      />,
    );

    expect(captured.onStop).toBeTypeOf('function');
    await act(async () => {
      await captured.onStop!(new Blob(['x'], { type: 'audio/webm' }));
    });

    expect(onCrisisResponse).toHaveBeenCalledTimes(1);
    expect(onCrisisResponse).toHaveBeenCalledWith('يرجى الاتصال بالرقم');
  });

  it('test #6b — passes null when the response omits locale_aware_message (Gemma fallback)', async () => {
    uploadAudioBlobMock.mockResolvedValueOnce({
      intake_id: 'rec-1',
      status: 'partial',
      is_crisis: true,
      // locale_aware_message intentionally absent (undefined)
    });

    const onCrisisResponse = vi.fn();
    render(
      <VoicePanel
        workerLanguage="en"
        speakerLanguage="ar"
        elapsedSec={0}
        sourceDeviceId="tent_b"
        intakeId={null}
        auditEvents={[]}
        structlogEvents={[]}
        onCrisisResponse={onCrisisResponse}
      />,
    );

    await act(async () => {
      await captured.onStop!(new Blob(['x'], { type: 'audio/webm' }));
    });

    expect(onCrisisResponse).toHaveBeenCalledWith(null);
  });

  it('test #7 — Gap 3: after a crisis turn, a re-rendered VoicePanel with intakeId=null POSTs intakeId=null', async () => {
    /* Simulate the App-level chain: crisis response fires
       clearIntakeId(), App re-renders VoicePanel with intakeId={null}.
       VoicePanel's intakeIdRef must reflect the latest prop on the
       NEXT mic stop. */
    uploadAudioBlobMock
      .mockResolvedValueOnce({
        intake_id: 'rec-1',
        status: 'partial',
        is_crisis: true,
        locale_aware_message: 'msg',
      })
      .mockResolvedValueOnce({
        intake_id: 'rec-2',
        status: 'partial',
        locale_aware_message: null,
      });

    const onCrisisResponse = vi.fn();
    const { rerender } = render(
      <VoicePanel
        workerLanguage="en"
        speakerLanguage="ar"
        elapsedSec={0}
        sourceDeviceId="tent_b"
        intakeId="rec-1"
        auditEvents={[]}
        structlogEvents={[]}
        onCrisisResponse={onCrisisResponse}
      />,
    );

    // First mic stop — crisis response.
    await act(async () => {
      await captured.onStop!(new Blob(['x'], { type: 'audio/webm' }));
    });
    expect(uploadAudioBlobMock).toHaveBeenNthCalledWith(1, expect.objectContaining({ intakeId: 'rec-1' }));
    expect(onCrisisResponse).toHaveBeenCalledTimes(1);

    // App-level handler calls clearIntakeId(); parent re-renders with null.
    rerender(
      <VoicePanel
        workerLanguage="en"
        speakerLanguage="ar"
        elapsedSec={0}
        sourceDeviceId="tent_b"
        intakeId={null}
        auditEvents={[]}
        structlogEvents={[]}
        onCrisisResponse={onCrisisResponse}
      />,
    );

    // Second mic stop — must POST with intakeId=null (create-path).
    await act(async () => {
      await captured.onStop!(new Blob(['y'], { type: 'audio/webm' }));
    });
    expect(uploadAudioBlobMock).toHaveBeenNthCalledWith(2, expect.objectContaining({ intakeId: null }));
  });
});

describe('VoicePanel — parameterized phase render', () => {
  type Phase = 'ready' | 'awaiting' | 'recording' | 'transcribing' | 'extracting' | 'done';
  const ALL_PHASES: Phase[] = ['ready', 'awaiting', 'recording', 'transcribing', 'extracting', 'done'];
  const SHOW_BEGIN: Phase[] = ['ready', 'done'];
  const SHOW_STOP: Phase[] = ['recording', 'transcribing', 'extracting'];

  function renderAt(phase: Phase) {
    mockPhase.current = phase;
    return render(
      <VoicePanel
        workerLanguage="en"
        speakerLanguage="en"
        elapsedSec={0}
        sourceDeviceId="laptop"
        intakeId={null}
        auditEvents={[]}
        structlogEvents={[]}
        onCrisisResponse={vi.fn()}
      />,
    );
  }

  for (const phase of ALL_PHASES) {
    it(`renders correct UI for phase=${phase}`, () => {
      const { unmount } = renderAt(phase);

      // Caption matches voiceCopy[phase].en, with aria-live polite.
      const caption = screen.getByText(voiceCopy[phase].en);
      const liveRegion = caption.closest('[aria-live="polite"]');
      expect(liveRegion).not.toBeNull();

      // Begin visible only in {ready, done}.
      const beginBtn = screen.queryByRole('button', { name: 'Begin' });
      if (SHOW_BEGIN.includes(phase)) {
        expect(beginBtn).not.toBeNull();
      } else {
        expect(beginBtn).toBeNull();
      }

      // Stop visible only in {recording, transcribing, extracting}.
      const stopBtn = screen.queryByRole('button', { name: 'Stop' });
      if (SHOW_STOP.includes(phase)) {
        expect(stopBtn).not.toBeNull();
        // Stop must be red text + red border + WHITE bg (never bg-red filled).
        const cls = stopBtn!.className;
        expect(cls).toMatch(/\btext-red\b/);
        expect(cls).toMatch(/\bborder-red\b/);
        // Design ref lock: bg-white background, NOT bg-red filled.
        // bg-red-soft (hover state) is fine; bg-red as the standalone
        // class is the violation. Use negative-lookahead to exclude
        // any bg-red- variants from the match.
        expect(cls).toMatch(/\bbg-white\b/);
        expect(cls).not.toMatch(/\bbg-red(?!-)/);
      } else {
        expect(stopBtn).toBeNull();
      }

      unmount();
    });
  }
});
