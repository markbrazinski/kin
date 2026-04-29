/* Minimal MediaRecorder + getUserMedia test double.

   jsdom 25 does not ship MediaRecorder or getUserMedia. The
   useMicCapture hook accepts a `mediaDevicesFactory` injection seam
   so tests can hand it a synthetic environment.

   Surface implemented matches what the hook actually uses:
     - constructor(stream, options?)
     - start()
     - stop()
     - state ('inactive' | 'recording' | 'paused')
     - addEventListener('dataavailable' | 'stop', cb)
*/

export type MockListener = (event: { data?: Blob }) => void;

export class MockMediaRecorder {
  static instances: MockMediaRecorder[] = [];
  static reset(): void {
    MockMediaRecorder.instances = [];
  }
  static last(): MockMediaRecorder | undefined {
    return MockMediaRecorder.instances[MockMediaRecorder.instances.length - 1];
  }

  state: 'inactive' | 'recording' | 'paused' = 'inactive';
  mimeType: string;

  private listeners: Map<string, MockListener[]> = new Map();
  private chunks: Blob[] = [];

  constructor(_stream: MediaStream, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType ?? 'audio/webm';
    MockMediaRecorder.instances.push(this);
  }

  addEventListener(name: string, listener: MockListener): void {
    const arr = this.listeners.get(name) ?? [];
    arr.push(listener);
    this.listeners.set(name, arr);
  }

  removeEventListener(name: string, listener: MockListener): void {
    const arr = this.listeners.get(name);
    if (!arr) return;
    const idx = arr.indexOf(listener);
    if (idx >= 0) arr.splice(idx, 1);
  }

  start(): void {
    this.state = 'recording';
    this.chunks = [];
  }

  stop(): void {
    this.state = 'inactive';
    /* Caller drives the dataavailable + stop fires via the test
       helpers below. Real browsers fire these asynchronously after
       stop() completes; we keep that order under test control. */
  }

  /* Test helpers — real MediaRecorder fires these on the platform. */
  emitData(data: Blob): void {
    this.chunks.push(data);
    const arr = this.listeners.get('dataavailable');
    if (!arr) return;
    for (const fn of arr) fn({ data });
  }

  emitStop(): void {
    const arr = this.listeners.get('stop');
    if (!arr) return;
    for (const fn of arr) fn({});
  }
}


/* Minimal MediaStreamTrack stand-in used so the hook can call
   `track.stop()` during cleanup. */
export class MockMediaStreamTrack {
  stop = (): void => {
    this.stopped = true;
  };
  stopped = false;
  kind: string = 'audio';
}


/* Minimal MediaStream stand-in. */
export class MockMediaStream {
  private tracks: MockMediaStreamTrack[];

  constructor(tracks?: MockMediaStreamTrack[]) {
    this.tracks = tracks ?? [new MockMediaStreamTrack()];
  }

  getTracks(): MockMediaStreamTrack[] {
    return this.tracks;
  }
}


/* Minimal mediaDevices stand-in. Tests configure success or rejection
   per-instance. */
export type MockMediaDevicesOpts = {
  /* If provided, getUserMedia rejects with this error. */
  rejectWith?: Error;
};

export class MockMediaDevices {
  rejectWith: Error | null;
  lastConstraints: MediaStreamConstraints | null = null;
  lastStream: MockMediaStream | null = null;

  constructor(opts: MockMediaDevicesOpts = {}) {
    this.rejectWith = opts.rejectWith ?? null;
  }

  async getUserMedia(
    constraints: MediaStreamConstraints,
  ): Promise<MediaStream> {
    this.lastConstraints = constraints;
    if (this.rejectWith) throw this.rejectWith;
    const stream = new MockMediaStream();
    this.lastStream = stream;
    return stream as unknown as MediaStream;
  }
}
