/* api.ts wire test — uploadAudioBlob surfaces locale_aware_message
   on crisis responses and returns the typed AudioUploadResponse
   shape end-to-end. ADR-004 REV 3. */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { uploadAudioBlob } from './api';

describe('uploadAudioBlob', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns locale_aware_message on a paused_for_crisis response', async () => {
    const fakeResponse = {
      intake_id: 'rec-1',
      status: 'paused_for_crisis',
      locale_aware_message: 'يرجى الاتصال بالرقم',
    };
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify(fakeResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const resp = await uploadAudioBlob({
      blob: new Blob(['x'], { type: 'audio/webm' }),
      lang: 'ar',
      sourceDeviceId: 'tent_b',
    });

    expect(resp.status).toBe('paused_for_crisis');
    expect(resp.locale_aware_message).toBe('يرجى الاتصال بالرقم');
  });

  it('returns locale_aware_message=null on a non-crisis response', async () => {
    const fakeResponse = {
      intake_id: 'rec-2',
      status: 'complete',
      locale_aware_message: null,
    };
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify(fakeResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const resp = await uploadAudioBlob({
      blob: new Blob(['x'], { type: 'audio/webm' }),
      lang: 'es',
      sourceDeviceId: 'tent_a',
    });

    expect(resp.status).toBe('complete');
    expect(resp.locale_aware_message).toBeNull();
  });
});
