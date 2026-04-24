/* Record card: biographic, last-seen, distinguishing marks, plus optional Guardian & Protection
   sub-section that auto-expands when a minor is detected. */
import React from 'react';
import type { Dispatch, ReactNode, SetStateAction } from 'react';
import { IconCamera, IconShield, IconAlert, IconInfo, IconUser, IconMapPin, IconSparkle, IconLock, IconPause } from './icons';
import { SectionHeader, Chip, Field } from './primitives';

export type NameVariant = {
  latin: string;
  script?: string;
  rtl?: boolean;
};

export type GuardianData = {
  guardianPresent?: string;
  cpConsent?: string;
  cmKnown?: string;
  referralStatus?: string;
};

export type RecordData = {
  name: string;
  nameVariants: NameVariant[] | null;
  nameNative: string | null;
  nameNativeRtl: boolean;
  age: string;
  relationship: string;
  language: string;
  lastSeenLocation: string;
  lastSeenLocationSource: string;
  lastSeenLocationRtl: boolean;
  lastSeenDate: string;
  circumstance: string;
  physicalDesc: string;
  features: string;
  guardian: GuardianData;
};

export type RecordCardProps = {
  record: RecordData;
  minor: boolean | undefined;
  justPopulatedKey: string | null;
  disabled?: boolean;
};

type ExpandedMap = Record<string, boolean>;

type TransliterationVariantsProps = {
  variants: NameVariant[] | null | undefined;
};

type SubSectionProps = {
  id: string;
  title: ReactNode;
  icon?: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
  expandedMap: ExpandedMap;
  setExpandedMap: Dispatch<SetStateAction<ExpandedMap>>;
  highlight?: boolean;
};

type GuardianProtectionProps = {
  data: GuardianData;
  minor: boolean | undefined;
  expandedMap: ExpandedMap;
  setExpandedMap: Dispatch<SetStateAction<ExpandedMap>>;
};

function TransliterationVariants({ variants }: TransliterationVariantsProps) {
  if (!variants || !variants.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="text-[12px] font-medium uppercase tracking-wider text-muted">Variants</span>
      {variants.map((v, i) => (
        <span key={i} className="inline-flex items-center gap-2 text-[15px]">
          <span className="text-ink">{v.latin}</span>
          {v.script && (
            <span className={`text-ink/90 ${v.rtl ? "rtl" : ""}`} style={{ fontSize: 17 }}>
              {v.script}
            </span>
          )}
        </span>
      ))}
    </div>
  );
}

function PhotoPlaceholder() {
  // Stub per brief: "Photo intake not yet implemented". Neutral, structural.
  return (
    <div className="mt-2 flex items-center gap-3 border border-dashed border-line rounded-kin p-3 bg-subtle/60">
      <div className="w-14 h-14 rounded-kin bg-white border border-line flex items-center justify-center text-muted">
        <IconCamera size={22} />
      </div>
      <div className="flex-1">
        <div className="text-[14px] font-medium text-ink">Photos</div>
        <div className="text-[13px] text-muted">Photo intake not yet implemented in this build.</div>
      </div>
    </div>
  );
}

function SubSection({ id, title, icon, meta, children, expandedMap, setExpandedMap, highlight }: SubSectionProps) {
  const expanded = expandedMap[id] !== false;
  const toggle = () => setExpandedMap(m => ({ ...m, [id]: !expanded }));
  return (
    <section
      className={`border-t border-hair ${highlight ? "bg-amber-soft/50" : ""}`}
    >
      <SectionHeader title={title} icon={icon} meta={meta} expanded={expanded} onToggle={toggle} />
      {expanded && <div className="pb-4">{children}</div>}
    </section>
  );
}

function GuardianProtection({ data, minor, expandedMap, setExpandedMap }: GuardianProtectionProps) {
  if (!minor) return null;
  return (
    <SubSection
      id="guardian"
      title="Guardian & Protection Status"
      icon={<IconShield size={18} />}
      meta={<Chip icon={<IconAlert size={12} />} tone="amber" className="ml-2">Required</Chip>}
      expandedMap={expandedMap}
      setExpandedMap={setExpandedMap}
      highlight
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
        <Field label="Guardian present at intake" value={data.guardianPresent} />
        <Field label="Consent to share with UNHCR CP" value={data.cpConsent} />
        <Field label="Known to case-management system" value={data.cmKnown} />
        <Field label="Referral status" value={data.referralStatus} />
      </div>
      <div className="mt-2 text-[13px] text-muted flex items-start gap-2">
        <IconInfo size={14} className="mt-0.5 shrink-0" />
        <span>Record will remain flagged <span className="font-medium text-ink">Incomplete — Minor Protection Required</span> until all four fields complete.</span>
      </div>
    </SubSection>
  );
}

function RecordCard({ record, minor, justPopulatedKey, disabled }: RecordCardProps) {
  const [expandedMap, setExpandedMap] = React.useState<ExpandedMap>({});

  return (
    <div
      className={`relative bg-card rounded-kin-lg border transition-colors duration-200 ${disabled ? "border-hair" : "border-line"}`}
      aria-disabled={disabled || undefined}
    >
      {disabled && (
        <div
          className="flex items-center gap-2 px-5 py-2 border-b border-hair bg-amber-soft/50 rounded-t-kin-lg text-muted"
          role="status"
        >
          <IconPause size={14} />
          <span className="text-[13px] font-medium">Paused — respond to crisis referral</span>
        </div>
      )}
      <div className={disabled ? "pointer-events-none select-none" : ""}>
      <div className="px-6 pt-5 pb-1 flex items-center justify-between">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Record</div>
          <div className="text-[15px] text-ink mt-0.5">
            {record.name || <span className="text-muted">Unnamed — intake in progress</span>}
          </div>
        </div>
        <Chip
          icon={<IconLock size={12} />}
          tone="neutral"
          className="!bg-white"
        >
          Local only
        </Chip>
      </div>

      <div className="px-6 pb-2">
        <SubSection
          id="bio"
          title="Biographic"
          icon={<IconUser size={18} />}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
            <Field
              label="Name"
              value={record.name}
              subValue={record.nameNative && <span className={record.nameNativeRtl ? "rtl" : ""}>{record.nameNative}</span>}
              extra={<TransliterationVariants variants={record.nameVariants} />}
              justPopulated={justPopulatedKey === "name"}
            />
            <Field label="Age" value={record.age} justPopulated={justPopulatedKey === "age"} />
            <Field label="Relationship to speaker" value={record.relationship} justPopulated={justPopulatedKey === "relationship"} />
            <Field label="Spoken language" value={record.language} />
          </div>
        </SubSection>

        <GuardianProtection
          data={record.guardian || {}}
          minor={minor}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        />

        <SubSection
          id="lastseen"
          title="Last seen"
          icon={<IconMapPin size={18} />}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
            <Field
              label="Location"
              value={record.lastSeenLocation}
              subValue={record.lastSeenLocationSource &&
                <span className={record.lastSeenLocationRtl ? "rtl" : ""}>
                  {record.lastSeenLocationSource}
                </span>}
              justPopulated={justPopulatedKey === "lastSeenLocation"}
            />
            <Field label="Date" value={record.lastSeenDate} justPopulated={justPopulatedKey === "lastSeenDate"} />
            <Field label="Circumstance" value={record.circumstance} justPopulated={justPopulatedKey === "circumstance"} />
          </div>
        </SubSection>

        <SubSection
          id="marks"
          title="Distinguishing marks"
          icon={<IconSparkle size={18} />}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        >
          <div className="grid grid-cols-1 gap-x-8">
            <Field label="Physical description" value={record.physicalDesc} justPopulated={justPopulatedKey === "physicalDesc"} />
            <Field label="Identifying features" value={record.features} justPopulated={justPopulatedKey === "features"} />
          </div>
          <PhotoPlaceholder />
        </SubSection>
      </div>
      </div>
    </div>
  );
}

export { RecordCard, TransliterationVariants };
