/* B2-S12: Cross-role family-network match visualization.

   Consumes NetworkMatchResult (N NodeMatch pairs from S11) and renders
   two intake cards side-by-side with an SVG overlay of N connection
   lines. Primary match line is bold; supporting lines are dashed and
   de-emphasized. Phase machine: split → linking → merged, identical
   shape to TransliterationMatch (S8) but merged state keeps both cards
   visible — the network IS the discovery, not a record merge.

   DEFAULT_NETWORK_RESULT / DEFAULT_RECORD_A / DEFAULT_RECORD_B are
   DemoDock-button fixtures only — not the recording-day fixture data.
   The Bundle 2 fixture seed spec produces the live-pipeline records.
*/
import React, { useEffect, useRef, useState } from 'react';
import { Button, Chip } from './primitives';
import { IconArrowRight, IconCheck, IconLink } from './icons';
import type { Language, MatchPhase, NetworkMatchResult, NodeMatch } from '../lib/types';
import { dirFor } from '../lib/i18n';

// ─── Internal types ─────────────────────────────────────────────────

type RosterMember = {
  name: string;
  nameLatin?: string;
  relationship: string;
  status: 'missing' | 'known' | 'present';
};

type NetworkCardData = {
  title: string;
  tone: 'warm' | 'cool';
  speakerLanguage: Language;
  searcherName?: string;
  searcherNameLatin?: string;
  searcherRelationship?: string;
  missingName: string;
  missingNameLatin?: string;
  age: string;
  lastSeen: string;
  lastSeenLatin?: string;
  rosterMembers?: RosterMember[];
};

export type NetworkMatchProps = {
  phase: MatchPhase;
  onBack: () => void;
  workerLanguage?: Language;
  networkResult: NetworkMatchResult;
  recordA?: NetworkCardData;
  recordB?: NetworkCardData;
};

type LineCoords = { x1: number; y1: number; x2: number; y2: number };

// ─── DemoDock fixtures (dev-mode only) ──────────────────────────────

/* Hand-curated Arabic Yusuf-Mariam-Mohamad scenario. Three cross-role
   pairs matching S11's test_network_match_full_yusuf_mariam_mohamad. */
export const DEFAULT_NETWORK_RESULT: NetworkMatchResult = {
  matched: true,
  node_matches: [
    {
      role_a: 'searcher', role_b: 'missing_person',
      name_a: 'يوسف', name_b: 'يوسف',
      roster_index_a: null, roster_index_b: null,
      phonetic_score: 1.0, composite_score: 0.85,
    },
    {
      role_a: 'missing_person', role_b: 'roster_member',
      name_a: 'محمد', name_b: 'محمد',
      roster_index_a: null, roster_index_b: 0,
      phonetic_score: 1.0, composite_score: 0.85,
    },
    {
      role_a: 'roster_member', role_b: 'searcher',
      name_a: 'مريم', name_b: 'مريم',
      roster_index_a: 0, roster_index_b: null,
      phonetic_score: 1.0, composite_score: 0.85,
    },
  ],
  primary_match: {
    role_a: 'searcher', role_b: 'missing_person',
    name_a: 'يوسف', name_b: 'يوسف',
    roster_index_a: null, roster_index_b: null,
    phonetic_score: 1.0, composite_score: 0.85,
  },
};

const DEFAULT_RECORD_A: NetworkCardData = {
  title: 'Intake A · Session #089',
  tone: 'warm',
  speakerLanguage: 'ar',
  searcherName: 'يوسف',
  searcherNameLatin: 'Yusuf',
  searcherRelationship: 'يبحث عن ابن أخته',
  missingName: 'محمد',
  missingNameLatin: 'Mohamad',
  age: '8',
  lastSeen: 'الجنوب · حدود المخيم',
  lastSeenLatin: 'South camp boundary',
  rosterMembers: [
    { name: 'مريم', nameLatin: 'Mariam', relationship: 'أخت', status: 'missing' },
  ],
};

const DEFAULT_RECORD_B: NetworkCardData = {
  title: 'Intake B · Session #147',
  tone: 'cool',
  speakerLanguage: 'ar',
  searcherName: 'مريم',
  searcherNameLatin: 'Mariam',
  searcherRelationship: 'تبحث عن أخيها',
  missingName: 'يوسف',
  missingNameLatin: 'Yusuf',
  age: '35',
  lastSeen: 'البوابة الجنوبية',
  lastSeenLatin: 'Southern gate',
  rosterMembers: [
    { name: 'محمد', nameLatin: 'Mohamad', relationship: 'ابن أخت', status: 'missing' },
  ],
};

// ─── Ref map helpers ────────────────────────────────────────────────

function makeRoleKey(
  side: 'a' | 'b',
  role: string,
  index: number | null,
): string {
  if (role === 'roster_member' && index !== null) {
    return `${side}:roster_${index}`;
  }
  return `${side}:${role}`;
}

function computeLines(
  containerRef: React.RefObject<HTMLDivElement>,
  refMap: Map<string, React.RefObject<HTMLDivElement>>,
  nodeMatches: NodeMatch[],
): LineCoords[] {
  if (!containerRef.current) return [];
  const containerRect = containerRef.current.getBoundingClientRect();
  const lines: LineCoords[] = [];
  for (const nm of nodeMatches) {
    const refA = refMap.get(makeRoleKey('a', nm.role_a, nm.roster_index_a));
    const refB = refMap.get(makeRoleKey('b', nm.role_b, nm.roster_index_b));
    if (!refA?.current || !refB?.current) continue;
    const rA = refA.current.getBoundingClientRect();
    const rB = refB.current.getBoundingClientRect();
    lines.push({
      x1: rA.left + rA.width / 2 - containerRect.left,
      y1: rA.top + rA.height / 2 - containerRect.top,
      x2: rB.left + rB.width / 2 - containerRect.left,
      y2: rB.top + rB.height / 2 - containerRect.top,
    });
  }
  return lines;
}

// ─── NetworkCard ─────────────────────────────────────────────────────

function needsSecondary(lang: Language): boolean {
  return lang === 'ar' || lang === 'fa';
}

function NetworkCard({
  data,
  side,
  ensureRef,
}: {
  data: NetworkCardData;
  side: 'a' | 'b';
  ensureRef: (key: string) => React.RefObject<HTMLDivElement>;
}) {
  const toneBg =
    data.tone === 'warm'
      ? 'bg-[oklch(0.985_0.012_75)]'
      : 'bg-[oklch(0.985_0.006_220)]';
  const valueDir = dirFor(data.speakerLanguage);
  const rtlClass = valueDir === 'rtl' ? 'rtl' : '';
  const secondary = needsSecondary(data.speakerLanguage);

  return (
    <div className={`flex-1 border border-line rounded-kin-lg ${toneBg}`}>
      <div className="px-5 py-3 border-b border-hair">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">
          {data.title}
        </div>
      </div>
      <div className="px-5 py-4 space-y-4">

        {/* Searcher slot */}
        {data.searcherName && (
          <div>
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted">
              Searcher
            </div>
            <div
              ref={ensureRef(makeRoleKey(side, 'searcher', null))}
              dir={valueDir}
              className={`text-[15px] text-ink mt-0.5 ${rtlClass}`}
            >
              {data.searcherName}
            </div>
            {secondary && data.searcherNameLatin && (
              <div dir="ltr" className="text-[12px] text-muted mt-0.5">
                {data.searcherNameLatin}
              </div>
            )}
            {data.searcherRelationship && (
              <div dir={valueDir} className={`text-[13px] text-muted/80 ${rtlClass}`}>
                {data.searcherRelationship}
              </div>
            )}
          </div>
        )}

        {/* Missing person slot */}
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">
            Missing person
          </div>
          <div
            ref={ensureRef(makeRoleKey(side, 'missing_person', null))}
            dir={valueDir}
            className={`text-[20px] font-semibold text-ink mt-0.5 ${rtlClass}`}
          >
            {data.missingName}
          </div>
          {secondary && data.missingNameLatin && (
            <div dir="ltr" className="text-[13px] text-muted mt-0.5">
              {data.missingNameLatin}
            </div>
          )}
        </div>

        {/* Age + last seen */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">
              Age
            </div>
            <div className="text-[16px] text-ink">{data.age}</div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted">
              Last seen
            </div>
            <div dir={valueDir} className={`text-[16px] text-ink ${rtlClass}`}>
              {data.lastSeen}
            </div>
            {secondary && data.lastSeenLatin && (
              <div dir="ltr" className="text-[12px] text-muted mt-0.5">
                {data.lastSeenLatin}
              </div>
            )}
          </div>
        </div>

        {/* Roster members */}
        {data.rosterMembers && data.rosterMembers.length > 0 && (
          <div>
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted">
              Roster
            </div>
            {data.rosterMembers.map((member, idx) => (
              <div key={idx} className="mt-1">
                <div
                  ref={ensureRef(makeRoleKey(side, 'roster_member', idx))}
                  dir={valueDir}
                  className={`text-[15px] text-ink ${rtlClass}`}
                >
                  {member.name}
                  {secondary && member.nameLatin && (
                    <span dir="ltr" className="text-[12px] text-muted ml-2">
                      {member.nameLatin}
                    </span>
                  )}
                </div>
                <div dir="ltr" className="text-[12px] text-muted">{member.relationship}</div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}

// ─── NetworkMatch ────────────────────────────────────────────────────

export function NetworkMatch({
  phase,
  onBack,
  workerLanguage,
  networkResult,
  recordA,
  recordB,
}: NetworkMatchProps) {
  // Parent (App.tsx) applies the richness-based priority rule before
  // rendering this component. Guard here is minimal: only gates on
  // matched so component stays pure about its own invariant.
  if (!networkResult.matched) return null;

  const wl: Language = workerLanguage ?? 'en';
  const rA = recordA ?? DEFAULT_RECORD_A;
  const rB = recordB ?? DEFAULT_RECORD_B;

  const containerRef = useRef<HTMLDivElement>(null);
  // Stable ref map across renders; keys grow monotonically, never shrink.
  const refMapRef = useRef<Map<string, React.RefObject<HTMLDivElement>>>(
    new Map(),
  );
  const [lines, setLines] = useState<LineCoords[]>([]);

  const reducedMotion =
    typeof window !== 'undefined'
      ? (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)
      : false;

  const showLines = reducedMotion
    ? networkResult.node_matches.length > 0
    : phase === 'linking' || phase === 'merged';

  const merged = phase === 'merged';

  function ensureRef(key: string): React.RefObject<HTMLDivElement> {
    if (!refMapRef.current.has(key)) {
      refMapRef.current.set(key, React.createRef<HTMLDivElement>());
    }
    return refMapRef.current.get(key)!;
  }

  // Cards never translate/scale across phase transitions (only opacity
  // changes in S8's pattern), so phase is not in the dep array.
  // If card positions ever animate, add `phase` here.
  useEffect(() => {
    if (!showLines) {
      setLines([]);
      return;
    }
    const id = requestAnimationFrame(() => {
      setLines(
        computeLines(containerRef, refMapRef.current, networkResult.node_matches),
      );
    });
    const handler = () =>
      setLines(
        computeLines(containerRef, refMapRef.current, networkResult.node_matches),
      );
    window.addEventListener('resize', handler);
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener('resize', handler);
    };
  }, [showLines, networkResult.node_matches]);

  return (
    <div className="max-w-[960px] mx-auto w-full">

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">
            Reunification candidate
          </div>
          <div className="text-[22px] font-semibold text-ink mt-0.5">
            Network match — {networkResult.node_matches.length} linked identities
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={<IconArrowRight className="rotate-180" size={16} />}
          onClick={onBack}
        >
          Back to intake
        </Button>
      </div>

      {/* Card pair + SVG overlay */}
      <div ref={containerRef} className={`relative ${merged ? 'kin-merge-pulse' : ''}`}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <NetworkCard data={rA} side="a" ensureRef={ensureRef} />
          <NetworkCard data={rB} side="b" ensureRef={ensureRef} />
        </div>

        {showLines && lines.length > 0 && (
          <svg
            aria-hidden="true"
            className="absolute inset-0 w-full h-full pointer-events-none overflow-visible"
          >
            {lines.map((coords, i) => {
              const isPrimary = i === 0;
              const animDelay = reducedMotion
                ? undefined
                : `${i === 0 ? 0 : 400 + (i - 1) * 300}ms`;
              return (
                <line
                  key={i}
                  x1={coords.x1}
                  y1={coords.y1}
                  x2={coords.x2}
                  y2={coords.y2}
                  stroke={
                    isPrimary
                      ? 'oklch(0.55 0.11 155)'
                      : 'oklch(0.55 0.11 155 / 0.45)'
                  }
                  strokeWidth={isPrimary ? 2 : 1}
                  strokeDasharray={isPrimary ? undefined : '4 3'}
                  className={reducedMotion ? undefined : 'kin-link-draw'}
                  style={
                    animDelay !== undefined ? { animationDelay: animDelay } : undefined
                  }
                />
              );
            })}
          </svg>
        )}
      </div>

      {/* Merged confirmation banner — cards stay visible above */}
      {merged && (
        <div className="mt-5 bg-card border border-green/40 rounded-kin-lg">
          <div className="px-6 py-4 border-b border-hair bg-green-soft/60 flex items-center gap-3">
            <div className="w-8 h-8 rounded-kin bg-white border border-green/40 text-green flex items-center justify-center">
              <IconLink size={16} />
            </div>
            <div>
              <div className="text-[12px] font-medium uppercase tracking-wider text-[oklch(0.38_0.1_155)]">
                Network match confirmed
              </div>
              <div className="text-[15px] text-ink mt-0.5">
                {networkResult.node_matches.length} identity links across both records.
              </div>
            </div>
            <div className="ml-auto">
              <Chip icon={<IconCheck size={12} />} tone="green">
                Pending caseworker review
              </Chip>
            </div>
          </div>

          <div className="px-6 py-5">
            <div className="text-[12px] font-medium uppercase tracking-wider text-muted mb-3">
              Matched name pairs
            </div>
            <div className="space-y-2">
              {networkResult.node_matches.map((nm, i) => (
                <div key={i} className="flex items-center gap-3 text-[14px]">
                  <span className="text-ink font-medium">{nm.name_a}</span>
                  <span className="text-muted text-[12px]">
                    {nm.role_a} → {nm.role_b}
                  </span>
                  <span className="text-ink font-medium">{nm.name_b}</span>
                  <span className="ml-auto text-muted text-[12px] font-mono">
                    {Math.round(nm.composite_score * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Cosmetic CTA buttons — onClick absent per S8 Item 11 pattern.
              Parent match view owns confirm/reject; this component is
              visualization only. */}
          <div
            dir={dirFor(wl)}
            className="border-t border-hair bg-subtle/40 px-6 py-3 flex flex-col sm:flex-row gap-2 sm:justify-end"
          >
            <Button variant="ghost">Escalate to supervisor</Button>
            <Button variant="secondary">Reject</Button>
            <Button variant="confirm" icon={<IconCheck size={16} />}>
              Confirm match
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
