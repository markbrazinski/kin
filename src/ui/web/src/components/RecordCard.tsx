/* Record card: V3 Contextual layout — metadata strip, chiclet ribbon (via IntakePanel),
   family network with per-person attribute nesting, MinorStrip, Guardian section. */
import React from 'react';
import type { Dispatch, ReactNode, SetStateAction } from 'react';
import {
  IconShield, IconAlert, IconInfo, IconUser,
  IconMapPin, IconSparkle, IconLock, IconPause, IconLanguages, IconCheck,
} from './icons';
import { SectionHeader, Chip, Field } from './primitives';
import { MinorStrip } from './MinorStrip';
import type { FamilyMember, GuardianData, RecordData } from '../lib/types';

export type RecordCardProps = {
  record: RecordData;
  minor: boolean | undefined;
  justPopulatedKey: string | null;
  disabled?: boolean;
  highlightKey?: string | null;
};

type ExpandedMap = Record<string, boolean>;

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

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatRecordId(uuid: string | undefined): string {
  if (!uuid) return '—';
  const tail = uuid.slice(-4);
  return `KIN-2026-${tail.padStart(4, '0').toUpperCase()}`;
}

function formatCapturedAt(iso: string | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    return `${date} · ${time}`;
  } catch {
    return '—';
  }
}

function isRtlText(text: string): boolean {
  return /[؀-ۿݐ-ݿ؀-ۿ]/.test(text);
}

// ─── Sub-section shell ────────────────────────────────────────────────────────

function SubSection({ id, title, icon, meta, children, expandedMap, setExpandedMap, highlight }: SubSectionProps) {
  const expanded = expandedMap[id] !== false;
  const toggle = () => setExpandedMap(m => ({ ...m, [id]: !expanded }));
  return (
    <section className={`border-t border-hair ${highlight ? 'bg-amber-soft/50' : ''}`}>
      <SectionHeader title={title} icon={icon} meta={meta} expanded={expanded} onToggle={toggle} />
      {expanded && <div className="pb-4">{children}</div>}
    </section>
  );
}

// ─── Metadata strip ───────────────────────────────────────────────────────────

function MetadataStrip({ record }: { record: RecordData }) {
  // Before intake begins, recordId and capturedAt are both absent.
  // Show a minimal "ready" placeholder rather than four dashes.
  if (!record.recordId && !record.capturedAt) {
    return (
      <div className="px-6 pt-5 pb-3 border-b border-hair">
        <span className="text-[13px] text-muted italic">Ready to begin</span>
      </div>
    );
  }

  const syncDotColor =
    record.syncStatus === 'synced' ? 'bg-green' :
    record.syncStatus === 'queued' ? 'bg-amber' :
    'bg-line';
  const syncLabel =
    record.syncStatus === 'synced' ? 'Synced' :
    record.syncStatus === 'queued' ? 'Queued for sync' :
    'Local only';

  return (
    <div className="px-6 pt-5 pb-3 flex items-stretch justify-between gap-6 border-b border-hair">
      {/* RECORD */}
      <div className="flex-1 min-w-0">
        <div className="text-[12px] uppercase tracking-wider text-muted">Record</div>
        <div className="font-mono text-[15px] text-ink mt-0.5 truncate">
          {formatRecordId(record.recordId)}
        </div>
      </div>
      {/* CAPTURED */}
      <div className="flex-1 min-w-0">
        <div className="text-[12px] uppercase tracking-wider text-muted">Captured</div>
        <div className="text-[14px] text-ink mt-0.5 truncate">
          {formatCapturedAt(record.capturedAt)}
        </div>
      </div>
      {/* SPOKEN LANGUAGE */}
      <div className="flex-1 min-w-0">
        <div className="text-[12px] uppercase tracking-wider text-muted">Spoken language</div>
        <div className="flex items-center gap-1.5 text-[14px] text-ink mt-0.5">
          <IconLanguages size={13} className="text-muted shrink-0" />
          <span className="truncate">{record.language || '—'}</span>
        </div>
      </div>
      {/* STATUS */}
      <div className="flex-1 min-w-0">
        <div className="text-[12px] uppercase tracking-wider text-muted">Status</div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${syncDotColor}`} />
          <span className="text-[14px] text-ink truncate">{syncLabel}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Person row + nested attrs ────────────────────────────────────────────────

type PersonRowProps = {
  member: FamilyMember;
  role: 'searcher' | 'missing' | 'roster';
  isMinor?: boolean;
  lastSeenFallback?: string;
  lastSeenFallbackLatin?: string;
};

function PersonRow({ member, role, isMinor, lastSeenFallback, lastSeenFallbackLatin }: PersonRowProps) {
  const rtl = isRtlText(member.name);
  const showNested = role === 'missing';

  let pill: ReactNode = null;
  if (role === 'searcher') {
    pill = <Chip tone="primary">{member.relationship || 'Searcher'}</Chip>;
  } else if (role === 'missing' && isMinor) {
    pill = <Chip tone="amber" icon={<IconShield size={12} />}>Minor · Missing</Chip>;
  } else if (role === 'missing') {
    pill = <Chip tone="amber" icon={<IconAlert size={12} />}>Missing</Chip>;
  } else if (role === 'roster') {
    pill = <Chip tone="green" icon={<IconCheck size={12} />}>With searcher</Chip>;
  }

  return (
    <div>
      {/* Header row */}
      <div className="flex items-center justify-between gap-4 py-2.5">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-full bg-subtle border border-hair flex items-center justify-center text-muted shrink-0">
            <IconUser size={16} />
          </div>
          <div className="min-w-0">
            <div className="flex items-baseline gap-2 leading-tight flex-wrap">
              <span
                dir={rtl ? 'rtl' : undefined}
                className={`text-[17px] text-ink truncate${rtl ? ' rtl' : ''}`}
              >
                {member.name}
              </span>
              {member.nameLatin && (
                <span className="text-[13px] text-muted truncate">{member.nameLatin}</span>
              )}
            </div>
            <div className="text-[12.5px] text-muted mt-0.5">
              {[member.relationship, member.age !== undefined ? `${member.age}` : null]
                .filter(Boolean)
                .join(' · ')}
            </div>
          </div>
        </div>
        {pill && <div className="shrink-0">{pill}</div>}
      </div>

      {/* Per-person nested attrs — missing persons only, always rendered */}
      {showNested && (
        <div className="ml-12 mt-1 mb-3 border-l-2 border-hair pl-3 space-y-2">
          {/* LAST SEEN — show source + transliteration (if both exist) */}
          <div>
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted mb-0.5">
              <IconMapPin size={11} />
              Last seen
            </div>
            {(() => {
              const source = member.lastSeen ?? lastSeenFallback;
              const latin = member.lastSeen ? undefined : lastSeenFallbackLatin;
              if (!source) return <span className="text-[13px] text-muted">—</span>;
              return (
                <div className="flex flex-col gap-0.5">
                  <span className="text-[13px] text-ink">{source}</span>
                  {latin && latin !== source && (
                    <span className="text-[12.5px] text-muted">{latin}</span>
                  )}
                </div>
              );
            })()}
          </div>
          {/* MARKS — hidden when empty */}
          {(member.marks && member.marks.length > 0) && (
            <div>
              <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted mb-0.5">
                <IconSparkle size={11} />
                {`Marks · ${member.marks.length}`}
              </div>
              <ul className="space-y-1">
                {member.marks.map((m, i) => (
                  <li key={i} className="text-[14px] text-ink">{m}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Family network section ───────────────────────────────────────────────────

type FamilyNetworkProps = {
  searcherName: string;
  searcherNameLatin: string;
  missingPersons: FamilyMember[];
  familyRoster: FamilyMember[];
  expandedMap: ExpandedMap;
  setExpandedMap: Dispatch<SetStateAction<ExpandedMap>>;
  highlightKey: string | null;
  lastSeenFallback?: string;
  lastSeenFallbackLatin?: string;
};

function FamilyNetworkSection({
  searcherName,
  searcherNameLatin,
  missingPersons,
  familyRoster,
  expandedMap,
  setExpandedMap,
  highlightKey,
  lastSeenFallback,
  lastSeenFallbackLatin,
}: FamilyNetworkProps) {
  const hasAny = searcherName || missingPersons.length > 0 || familyRoster.length > 0;
  if (!hasAny) return null;

  const totalCount = (searcherName ? 1 : 0) + missingPersons.length + familyRoster.length;
  const minorCount = missingPersons.filter(
    m => typeof m.age === 'number' && m.age > 0 && m.age < 18
  ).length;

  const isHighlighted =
    highlightKey === 'searcher_name' ||
    highlightKey === 'searcher_name_transliteration' ||
    highlightKey === 'missing_persons' ||
    highlightKey === 'family_roster';

  const meta = (
    <div className="flex items-center gap-0">
      <Chip tone="neutral">{totalCount}</Chip>
      {minorCount > 0 && (
        <span className="text-[12.5px] text-muted ml-1.5">
          · {minorCount} minor{minorCount > 1 ? 's' : ''}
        </span>
      )}
    </div>
  );

  return (
    <SubSection
      id="family_network"
      title="Family network"
      icon={<IconUser size={18} />}
      meta={meta}
      expandedMap={expandedMap}
      setExpandedMap={setExpandedMap}
      highlight={isHighlighted}
    >
      <div className="px-6 pt-1">
        {searcherName && (
          <div>
            <div className="text-[11.5px] uppercase tracking-wider text-muted mt-3 mb-0.5">
              Searcher
            </div>
            <PersonRow
              member={{
                name: searcherName,
                nameLatin: searcherNameLatin || undefined,
                relationship: '',
              }}
              role="searcher"
            />
          </div>
        )}

        {missingPersons.length > 0 && (
          <div>
            <div className="text-[11.5px] uppercase tracking-wider text-muted mt-3 mb-0.5">
              Missing · {missingPersons.length}
            </div>
            <div>
              {missingPersons.map((m, i) => (
                <PersonRow
                  key={i}
                  member={m}
                  role="missing"
                  isMinor={typeof m.age === 'number' && m.age > 0 && m.age < 18}
                  lastSeenFallback={lastSeenFallback}
                  lastSeenFallbackLatin={lastSeenFallbackLatin}
                />
              ))}
            </div>
          </div>
        )}

        {familyRoster.length > 0 && (
          <div>
            <div className="text-[11.5px] uppercase tracking-wider text-muted mt-3 mb-0.5">
              With searcher · {familyRoster.length}
            </div>
            <div>
              {familyRoster.map((m, i) => (
                <PersonRow key={i} member={m} role="roster" />
              ))}
            </div>
          </div>
        )}
      </div>
    </SubSection>
  );
}

// ─── Guardian & Protection ────────────────────────────────────────────────────

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
        <span>
          Record will remain flagged{' '}
          <span className="font-medium text-ink">Incomplete — Minor Protection Required</span>{' '}
          until all four fields complete.
        </span>
      </div>
    </SubSection>
  );
}

// ─── RecordCard ───────────────────────────────────────────────────────────────

function RecordCard({ record, minor, justPopulatedKey: _justPopulatedKey, disabled, highlightKey }: RecordCardProps) {
  const [expandedMap, setExpandedMap] = React.useState<ExpandedMap>({});

  // Real pipeline populates familyRoster (from SSE family_roster event);
  // missingPersons is only set on the synthetic path. Check both so the
  // MinorStrip fires on both paths.
  const allMissing = record.familyRoster.filter(m => m.status !== 'WITH_SEARCHER').length > 0
    ? record.familyRoster.filter(m => m.status !== 'WITH_SEARCHER')
    : record.missingPersons;
  const hasMinor = allMissing.some(
    m => typeof m.age === 'number' && m.age > 0 && m.age < 18
  );
  const firstMinor = allMissing.find(
    m => typeof m.age === 'number' && m.age > 0 && m.age < 18
  );
  const minorDisplayName = firstMinor?.nameLatin || firstMinor?.name;

  return (
    <div
      className={`relative bg-card rounded-kin-lg border transition-colors duration-200 ${disabled ? 'border-hair' : 'border-line'}`}
      aria-disabled={disabled || undefined}
    >
      {/* MinorStrip — first child, inside card, derived from family-network state */}
      <MinorStrip visible={hasMinor} minorName={minorDisplayName} />

      {disabled && (
        <div
          className="flex items-center gap-2 px-5 py-2 border-b border-hair bg-amber-soft/50 text-muted"
          role="status"
        >
          <IconPause size={14} />
          <span className="text-[13px] font-medium">Paused — respond to crisis referral</span>
        </div>
      )}

      <div className={disabled ? 'pointer-events-none select-none' : ''}>
        {/* 4-cell metadata strip */}
        <MetadataStrip record={record} />

        <div className="px-6 pb-2">
          <FamilyNetworkSection
            searcherName={record.searcherName}
            searcherNameLatin={record.searcherNameLatin}
            missingPersons={record.familyRoster.filter(m => m.status !== 'WITH_SEARCHER')}
            familyRoster={record.familyRoster.filter(m => m.status === 'WITH_SEARCHER')}
            expandedMap={expandedMap}
            setExpandedMap={setExpandedMap}
            highlightKey={highlightKey ?? null}
            lastSeenFallback={record.lastSeenLocationSource || record.lastSeenLocation || undefined}
            lastSeenFallbackLatin={record.lastSeenLocation || undefined}
          />

          {record.physicalDesc && (
            <SubSection
              id="identifying_marks"
              title="Identifying marks"
              icon={<IconSparkle size={18} />}
              expandedMap={expandedMap}
              setExpandedMap={setExpandedMap}
              highlight={highlightKey === 'distinguishing_marks'}
            >
              <div className="px-6 pb-3">
                <p className="text-[14px] text-ink leading-snug" dir="auto">
                  {record.physicalDesc}
                </p>
              </div>
            </SubSection>
          )}

          <GuardianProtection
            data={record.guardian || {}}
            minor={minor}
            expandedMap={expandedMap}
            setExpandedMap={setExpandedMap}
          />
        </div>
      </div>

      {/* Local-only lock indicator */}
      <div className="px-6 pb-4 flex items-center gap-1.5 text-[11px] text-muted">
        <IconLock size={11} />
        <span>Local only — no data leaves this device</span>
      </div>
    </div>
  );
}

export { RecordCard };
