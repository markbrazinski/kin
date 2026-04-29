/* useMicCapture hook tests — drive the state machine via mock
   MediaRecorder + mock MediaDevices, no real browser APIs. */
import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import {
  MockMediaDevices,
  MockMediaRecorder,
  MockMediaStream,
  MockMediaStreamTrack,
} from '../test-utils/MockMediaRecorder';
import { useMicCapture } from './useMicCapture';

type Ctor = ConstructorParameters<typeof MockMediaRecorder>;

const recorderCtor = MockMediaRecorder as unknown as new (
  stream: MediaStream,
  options?: { mimeType?: string },
) => InstanceType<typeof MockMediaRecorder>;

beforeEach(() => {
  MockMediaRecorder.reset();
});

function makeFactory(devices: MockMediaDevices) {
  return () => devices as unknown as MediaDevices;
}

describe('useMicCapture', () => {
  it('transitions idle → recording → processing → idle across a capture cycle', async () => {
    const devices = new MockMediaDevices();
    const { result } = renderHook(() =>
      useMicCapture({
        mediaDevicesFactory: makeFactory(devices),
        mediaRecorderCtor: recorderCtor,
      }),
    );

    expect(result.current.state).toBe('idle');

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.state).toBe('recording');
    const recorder = MockMediaRecorder.last()!;
    expect(recorder.state).toBe('recording');

    act(() => {
      result.current.stop();
    });
    expect(result.current.state).toBe('processing');

    /* Real MediaRecorder fires dataavailable + stop asynchronously
       after stop(). Drive them manually to complete the lifecycle. */
    act(() => {
      recorder.emitData(new Blob(['chunk'], { type: 'audio/webm' }));
      recorder.emitStop();
    });

    await waitFor(() => expect(result.current.state).toBe('idle'));
    expect(result.current.audioBlob).not.toBeNull();
    expect(result.current.audioBlob!.size).toBeGreaterThan(0);
  });

  it('cleans up media stream tracks on unmount', async () => {
    const stoppableTrack = new MockMediaStreamTrack();
    /* Pre-bake the stream so we can capture the track reference. */
    const stream = new MockMediaStream([stoppableTrack]);
    const devices = new MockMediaDevices();
    devices.getUserMedia = async () => stream as unknown as MediaStream;

    const { result, unmount } = renderHook(() =>
      useMicCapture({
        mediaDevicesFactory: makeFactory(devices),
        mediaRecorderCtor: recorderCtor,
      }),
    );

    await act(async () => {
      await result.current.start();
    });
    expect(stoppableTrack.stopped).toBe(false);

    unmount();
    expect(stoppableTrack.stopped).toBe(true);
  });

  it('surfaces an error state when getUserMedia rejects', async () => {
    const devices = new MockMediaDevices({
      rejectWith: new Error('Permission denied'),
    });
    const { result } = renderHook(() =>
      useMicCapture({
        mediaDevicesFactory: makeFactory(devices),
        mediaRecorderCtor: recorderCtor,
      }),
    );

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.state).toBe('error');
    expect(result.current.error).toContain('Permission denied');
  });

  it('delivers the captured Blob via the onStop callback', async () => {
    const devices = new MockMediaDevices();
    const captured: Blob[] = [];
    const { result } = renderHook(() =>
      useMicCapture({
        mediaDevicesFactory: makeFactory(devices),
        mediaRecorderCtor: recorderCtor,
        onStop: (blob) => captured.push(blob),
      }),
    );

    await act(async () => {
      await result.current.start();
    });
    const recorder = MockMediaRecorder.last()!;

    act(() => {
      result.current.stop();
      recorder.emitData(new Blob(['turn1'], { type: 'audio/webm' }));
      recorder.emitStop();
    });

    await waitFor(() => expect(captured).toHaveLength(1));
    expect(captured[0].size).toBeGreaterThan(0);
    expect(captured[0].type).toBe('audio/webm');
  });
});

/* Type guard satisfied so the cast in `recorderCtor` doesn't compile-fail.
   The Ctor tuple is unused at runtime; this referenced type prevents
   the unused-import warning. */
void (null as unknown as Ctor);
