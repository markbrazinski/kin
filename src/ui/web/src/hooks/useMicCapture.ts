/* Browser microphone capture via MediaRecorder.

   Per-turn Begin/Stop semantics: caller calls start() to begin
   recording, stop() to end. On stop, the captured chunks are
   concatenated into a Blob and the onStop callback (if provided) is
   invoked with it. The caller is responsible for POSTing the Blob
   wherever it needs to go.

   No audio level visualization in S5 (deferred to S7 polish). The
   hook owns just the MediaRecorder lifecycle + getUserMedia
   permission flow + cleanup.

   Test injection: the optional `mediaDevicesFactory` and
   `mediaRecorderCtor` props let tests substitute mocks. Production
   reads navigator.mediaDevices and window.MediaRecorder directly.
*/
import { useCallback, useEffect, useRef, useState } from 'react';

export type MicState = 'idle' | 'recording' | 'processing' | 'error';

type MediaRecorderLike = {
  state: string;
  mimeType: string;
  start(): void;
  stop(): void;
  addEventListener(
    name: string,
    listener: (event: { data?: Blob }) => void,
  ): void;
  removeEventListener?(
    name: string,
    listener: (event: { data?: Blob }) => void,
  ): void;
};

type MediaRecorderCtor = new (
  stream: MediaStream,
  options?: { mimeType?: string },
) => MediaRecorderLike;

export interface UseMicCaptureOpts {
  mimeType?: string;
  onStop?: (blob: Blob) => void;
  mediaDevicesFactory?: () => MediaDevices;
  mediaRecorderCtor?: MediaRecorderCtor;
}

export interface UseMicCaptureResult {
  state: MicState;
  start: () => Promise<void>;
  stop: () => void;
  audioBlob: Blob | null;
  error: string | null;
}

const DEFAULT_MIME_TYPE = 'audio/webm';

function defaultMediaDevices(): MediaDevices {
  if (
    typeof navigator === 'undefined' ||
    !navigator.mediaDevices
  ) {
    throw new Error(
      'navigator.mediaDevices not available in this environment',
    );
  }
  return navigator.mediaDevices;
}

function defaultRecorderCtor(): MediaRecorderCtor {
  if (
    typeof window === 'undefined' ||
    typeof (window as unknown as { MediaRecorder?: MediaRecorderCtor })
      .MediaRecorder === 'undefined'
  ) {
    throw new Error('MediaRecorder is not available in this environment');
  }
  return (window as unknown as { MediaRecorder: MediaRecorderCtor })
    .MediaRecorder;
}

export function useMicCapture(
  opts: UseMicCaptureOpts = {},
): UseMicCaptureResult {
  const {
    mimeType = DEFAULT_MIME_TYPE,
    onStop,
    mediaDevicesFactory = defaultMediaDevices,
    mediaRecorderCtor,
  } = opts;

  const [state, setState] = useState<MicState>('idle');
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorderLike | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const onStopRef = useRef(onStop);
  onStopRef.current = onStop;

  const cleanup = useCallback(() => {
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) {
        try {
          track.stop();
        } catch {
          /* noop */
        }
      }
      streamRef.current = null;
    }
    recorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const start = useCallback(async () => {
    if (state === 'recording' || state === 'processing') return;
    setError(null);
    setAudioBlob(null);

    let stream: MediaStream;
    try {
      const devices = mediaDevicesFactory();
      stream = await devices.getUserMedia({ audio: true });
    } catch (err) {
      const msg =
        err instanceof Error
          ? `microphone access failed: ${err.message}`
          : 'microphone access failed';
      setError(msg);
      setState('error');
      return;
    }

    let Ctor: MediaRecorderCtor;
    try {
      Ctor = mediaRecorderCtor ?? defaultRecorderCtor();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : 'MediaRecorder unavailable';
      setError(msg);
      setState('error');
      for (const track of stream.getTracks()) track.stop();
      return;
    }

    const recorder = new Ctor(stream, { mimeType });
    chunksRef.current = [];

    recorder.addEventListener('dataavailable', (e) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
    });
    recorder.addEventListener('stop', () => {
      const blob = new Blob(chunksRef.current, { type: mimeType });
      setAudioBlob(blob);
      setState('idle');
      cleanup();
      onStopRef.current?.(blob);
    });

    streamRef.current = stream;
    recorderRef.current = recorder;
    recorder.start();
    setState('recording');
  }, [state, mediaDevicesFactory, mediaRecorderCtor, mimeType, cleanup]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state !== 'recording') return;
    setState('processing');
    recorder.stop();
  }, []);

  /* Cleanup tracks on unmount even if recording is still active. */
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return { state, start, stop, audioBlob, error };
}
