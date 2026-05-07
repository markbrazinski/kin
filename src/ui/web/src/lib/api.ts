/* Tiny fetch wrappers for the two POST endpoints S5 added. */

export type AudioUploadResponse = {
  intake_id: string;
  status: string;
  is_crisis?: boolean;
  locale_aware_message?: string | null;
};

export async function uploadAudioBlob(opts: {
  blob: Blob;
  lang: string;
  sourceDeviceId: string;
  intakeId?: string | null;
  filename?: string;
}): Promise<AudioUploadResponse> {
  const form = new FormData();
  form.append(
    'audio',
    opts.blob,
    opts.filename ?? `turn.${opts.blob.type.split('/')[1] ?? 'webm'}`,
  );
  form.append('lang', opts.lang);
  form.append('source_device_id', opts.sourceDeviceId);
  if (opts.intakeId) form.append('intake_id', opts.intakeId);

  const res = await fetch('/intake/audio', {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`audio upload failed: ${res.status} ${text}`);
  }
  return (await res.json()) as AudioUploadResponse;
}

export async function postCrisisResolved(opts: {
  intakeId: string;
  resolution: 'referral_provided' | 'de_escalated';
  referralOrganization?: string;
}): Promise<void> {
  await fetch(`/intake/${encodeURIComponent(opts.intakeId)}/crisis-resolved`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      resolution: opts.resolution,
      referral_organization: opts.referralOrganization ?? null,
    }),
  });
}

export async function postTransliteration(opts: {
  intakeId: string;
  value: string;
}): Promise<{ intake_id: string; changed: boolean }> {
  const res = await fetch(
    `/intake/${encodeURIComponent(opts.intakeId)}/transliteration`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: opts.value }),
    },
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`transliteration update failed: ${res.status} ${text}`);
  }
  return (await res.json()) as { intake_id: string; changed: boolean };
}
