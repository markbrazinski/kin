/* Read-only detail view for a persisted intake record.
   Wraps RecordCard with a read-only banner. Does NOT mount live-state hooks.
   Prototype: design_reference/round-2/record-readonly.jsx */
import React from 'react';
import { Chip, Button } from './primitives';
import { RecordCard } from './RecordCard';
import { IconLock, IconArrowRight } from './icons';
import type { IntakeRecord } from '../lib/intakeRecord';
import type { RecordData } from '../lib/types';
import type { Language } from '../lib/types';

// ---- IntakeRecord → RecordData mapping -------------------------------------

function toRecordData(r: IntakeRecord): RecordData {
  return {
    name: r.full_name_transliteration || r.full_name_source_script,
    nameVariants: null,
    nameNative: r.full_name_source_script || null,
    nameNativeRtl: /[؀-ۿݐ-ݿ]/.test(r.full_name_source_script),
    age: r.age !== null ? String(r.age) : '',
    relationship: r.relationship_to_seeker,
    language: r.language,
    lastSeenLocation: r.last_seen_location ?? '',
    lastSeenLocationSource: 'speaker',
    lastSeenLocationRtl: false,
    lastSeenDate: r.last_seen_date ?? '',
    circumstance: '',
    physicalDesc: r.distinguishing_marks ?? '',
    features: '',
    guardian: {
      guardianPresent: '',
      cpConsent: '',
      cmKnown: '',
      referralStatus: '',
    },
    searcherName: '',
    searcherNameLatin: '',
    missingPersons: [],
    familyRoster: [],
  };
}

// ---- Status banner ----------------------------------------------------------

function StatusBanner({ status, isCrisis }: { status: IntakeRecord['status']; isCrisis: boolean }) {
  if (isCrisis || status === 'paused_for_crisis') {
    return (
      <div className="mb-3 bg-red-soft border border-red/30 rounded-kin px-4 py-3 text-[13px] text-ink">
        Crisis referral issued — intake locked. Caseworker review required.
      </div>
    );
  }
  if (status === 'partial') {
    return (
      <div className="mb-3 bg-[oklch(0.98_0.02_75)] border border-amber/30 rounded-kin px-4 py-3 text-[13px] text-ink">
        Awaiting next turn — record extended when capture resumes.
      </div>
    );
  }
  return null;
}

// ---- RecordReadonly ---------------------------------------------------------

export type RecordReadonlyProps = {
  record: IntakeRecord;
  workerLanguage: Language;
  onBack: () => void;
  onNew: () => void;
};

export function RecordReadonly({ record, onBack, onNew }: RecordReadonlyProps) {
  const recordData = toRecordData(record);

  return (
    <div className="max-w-[1100px] mx-auto w-full">
      {/* Back affordance */}
      <div className="mb-4">
        <Button
          variant="ghost"
          size="sm"
          icon={<IconArrowRight className="rotate-180" size={16} />}
          onClick={onBack}
        >
          Back to queue
        </Button>
      </div>

      {/* Read-only banner */}
      <div className="mb-3 bg-card border border-line rounded-kin px-4 py-3 flex items-center gap-3">
        <div className="w-8 h-8 rounded-kin border border-line bg-subtle/60 text-muted flex items-center justify-center">
          <IconLock size={14} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-semibold text-ink">Viewing previous record</div>
          <div className="text-[13px] text-muted mt-0.5">Read-only · open from the queue. Editing not enabled in this build.</div>
        </div>
        <Button size="sm" variant="secondary" onClick={onNew}>New intake</Button>
      </div>

      {/* Status-specific banner */}
      <StatusBanner status={record.status} isCrisis={record.is_crisis} />

      {/* Record card (read-only — no live-state hooks) */}
      <RecordCard
        record={recordData}
        minor={record.is_minor}
        justPopulatedKey={null}
        disabled={false}
      />
    </div>
  );
}
