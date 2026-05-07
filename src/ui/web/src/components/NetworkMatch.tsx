/* B2-S25: Network match visualization — V3 inline SVG graph (Variant C).

   Replaces the S12 card-pair + SVG overlay with a single SVG canvas.
   Two columns of role-nodes connected by weighted bezier edges. Phase
   machine (split → linking → merged) drives edge entrance animation
   and primary-node fill cross-fade. Surrounding chrome (header, merged
   confirmation banner, MatchAuditPanel) unchanged from S12/S15.
*/
import React, { useEffect, useRef, useState } from 'react';
import { Button, Chip } from './primitives';
import { IconArrowRight, IconCheck, IconLink, IconMic } from './icons';
import type { Language, MatchPhase, NetworkMatchResult } from '../lib/types';
import { dirFor } from '../lib/i18n';
import { MatchAuditPanel } from './MatchAuditPanel';

// ─── Internal graph types ────────────────────────────────────────────

type GraphNode = {
  id: string;
  name: string;        // source script (Arabic / Farsi)
  nameLatin: string;
  age: number;
  relation: string;    // e.g. "Father (self)", "Wife", "Son" — render verbatim
  minor: boolean;
  kind: 'searcher' | 'missing' | 'roster';
  person_type: 'searcher' | 'missing_person' | 'roster_member';
};

type GraphEdge = {
  id: string;
  aId: string;
  bId: string;
  score: number;
  primary: boolean;
  label: string;       // e.g. "Son ↔ Son"
};

type GraphSide = {
  label: string;       // "INTAKE A · YUSUF REPORTING"
  nodes: GraphNode[];  // searcher first, then missing, then unmatched roster
};

type GraphData = {
  sideA: GraphSide;
  sideB: GraphSide;
  edges: GraphEdge[];
  threshold: number;
};

// ─── NetworkCardData (kept for prop compat with S12) ────────────────

type RosterMember = {
  name: string;
  nameLatin?: string;
  relationship: string;
  status: 'missing' | 'known' | 'present';
  age?: number;
};

type MissingPerson = {
  name: string;
  nameLatin?: string;
  relationship: string;   // display relation, e.g. "Nephew", "Son"
  age?: number;
};

export type NetworkCardData = {
  title: string;
  tone: 'warm' | 'cool';
  speakerLanguage: Language;
  searcherName?: string;
  searcherNameLatin?: string;
  searcherRelationship?: string;   // full label, e.g. "Father (self)"
  searcherAge?: number;
  // missingName/missingAge kept for backward-compat; missingPersons takes priority.
  missingName: string;
  missingNameLatin?: string;
  missingAge?: number;
  missingRelationship?: string;    // relation of the primary missing person
  age: string;
  lastSeen: string;
  lastSeenLatin?: string;
  missingPersons?: MissingPerson[];  // all missing persons, in NodeMatch index order
  rosterMembers?: RosterMember[];
};

export type NetworkMatchProps = {
  phase: MatchPhase;
  onBack: () => void;
  onNewIntake?: () => void;
  workerLanguage?: Language;
  networkResult: NetworkMatchResult;
  recordA?: NetworkCardData;
  recordB?: NetworkCardData;
  intakeIdA?: string;
  intakeIdB?: string;
};

// ─── DemoDock fixtures (dev-mode only) ──────────────────────────────

/* Yusuf-Mariam-Mohamad scenario. Three cross-role pairs.
   match_type drives edge label ("PRIMARY" / "SUPPORTING") and bold/dashed treatment. */
export const DEFAULT_NETWORK_RESULT: NetworkMatchResult = {
  matched: true,
  node_matches: [
    {
      role_a: 'missing_person', role_b: 'missing_person',
      name_a: 'محمد', name_b: 'محمد',
      roster_index_a: null, roster_index_b: 0,
      phonetic_score: 1.0, composite_score: 0.85,
      match_type: 'primary',
    },
    {
      role_a: 'roster_member', role_b: 'searcher',
      name_a: 'مريم', name_b: 'مريم',
      roster_index_a: 0, roster_index_b: null,
      phonetic_score: 1.0, composite_score: 0.85,
      match_type: 'supporting',
    },
    {
      role_a: 'searcher', role_b: 'missing_person',
      name_a: 'يوسف', name_b: 'يوسف',
      roster_index_a: null, roster_index_b: null,
      phonetic_score: 1.0, composite_score: 0.85,
      match_type: 'supporting',
      person_type_b: 'roster_member',  // cross-reference, not a primary missing person
    },
  ],
  primary_match: {
    role_a: 'missing_person', role_b: 'missing_person',
    name_a: 'محمد', name_b: 'محمد',
    roster_index_a: null, roster_index_b: 0,
    phonetic_score: 1.0, composite_score: 0.85,
    match_type: 'primary',
  },
};

/* Card A: Yusuf reporting.
   missingPersons[0] = Mohamad (son, matches NodeMatch missing_person on A).
   rosterMembers[0]  = Mariam  (wife, matches NodeMatch roster[0] on A).
   rosterMembers[1]  = Aisha   (daughter, unmatched → "ALSO IN ROSTER"). */
const DEFAULT_RECORD_A: NetworkCardData = {
  title: 'Intake A · Session #089',
  tone: 'warm',
  speakerLanguage: 'ar',
  searcherName: 'يوسف الحلبي',
  searcherNameLatin: 'Yusuf al-Halabi',
  searcherRelationship: 'Father (self)',
  searcherAge: 41,
  missingName: 'محمد الحلبي',
  missingNameLatin: 'Mohamad al-Halabi',
  missingAge: 9,
  missingRelationship: 'Nephew',
  age: '9',
  lastSeen: 'الجنوب · حدود المخيم',
  lastSeenLatin: 'South camp boundary',
  missingPersons: [
    { name: 'محمد الحلبي', nameLatin: 'Mohamad al-Halabi', relationship: 'Nephew', age: 9 },
  ],
  rosterMembers: [
    { name: 'مريم الحلبي',  nameLatin: 'Mariam al-Halabi',  relationship: 'Wife',     status: 'missing', age: 38 },
    { name: 'عائشة الحلبي', nameLatin: 'Aisha al-Halabi',   relationship: 'Daughter', status: 'missing', age: 6  },
  ],
};

/* Card B: Mariam reporting.
   missingPersons[0] = Mohamad (son — primary missing child on this case).
   missingPersons[1] = Yusuf   (husband — cross-reference to intake A searcher).
   rosterMembers[0]  = Mohamad (also filed here for matching; person_type resolves
                                to missing_person via role_b in NodeMatch). */
const DEFAULT_RECORD_B: NetworkCardData = {
  title: 'Intake B · Session #147',
  tone: 'cool',
  speakerLanguage: 'ar',
  searcherName: 'مريم الحلبي',
  searcherNameLatin: 'Mariam al-Halabi',
  searcherRelationship: 'Mother (self)',
  searcherAge: 38,
  missingName: 'محمد الحلبي',
  missingNameLatin: 'Mohamad al-Halabi',
  missingAge: 9,
  missingRelationship: 'Son',
  age: '9',
  lastSeen: 'البوابة الجنوبية',
  lastSeenLatin: 'Southern gate',
  missingPersons: [
    { name: 'محمد الحلبي', nameLatin: 'Mohamad al-Halabi', relationship: 'Son',     age: 9  },
    { name: 'يوسف الحلبي', nameLatin: 'Yusuf al-Halabi',   relationship: 'Husband', age: 41 },
  ],
  rosterMembers: [
    { name: 'محمد الحلبي', nameLatin: 'Mohamad al-Halabi', relationship: 'Son', status: 'missing', age: 9 },
  ],
};

// ─── Graph data builder ──────────────────────────────────────────────

/* Short label for edge display — strips "(self)" suffix used in
   display relations so edges read "Son ↔ Son" not "Son ↔ Son (self)". */
function buildGraphData(
  networkResult: NetworkMatchResult,
  cardA: NetworkCardData,
  cardB: NetworkCardData,
  intakeIdA: string,
  intakeIdB: string,
): GraphData {
  const nm = networkResult.node_matches;
  const primaryNm = networkResult.primary_match;

  // ── Node builders ─────────────────────────────────────────────────

  const searcherNode = (side: 'a' | 'b', card: NetworkCardData): GraphNode => ({
    id: `${side}:searcher`,
    name: card.searcherName ?? '',
    nameLatin: card.searcherNameLatin ?? '',
    age: card.searcherAge ?? 0,
    relation: card.searcherRelationship ?? 'Searcher',
    minor: (card.searcherAge ?? 99) < 18,
    kind: 'searcher',
    person_type: 'searcher',
  });

  const missingPersonNode = (side: 'a' | 'b', card: NetworkCardData, nameHint?: string): GraphNode => {
    // Look up by name when multiple missing persons exist; fall back to slot 0.
    const mp = nameHint
      ? (card.missingPersons?.find(p => p.name.includes(nameHint) || nameHint.includes(p.name)) ?? card.missingPersons?.[0])
      : card.missingPersons?.[0];
    const idx = mp && card.missingPersons ? card.missingPersons.indexOf(mp) : 0;
    return {
      id: `${side}:missing_${idx < 0 ? 0 : idx}`,
      name: mp?.name ?? card.missingName,
      nameLatin: mp?.nameLatin ?? card.missingNameLatin ?? '',
      age: mp?.age ?? card.missingAge ?? (parseInt(card.age) || 0),
      relation: mp?.relationship ?? card.missingRelationship ?? 'Missing',
      minor: (mp?.age ?? card.missingAge ?? (parseInt(card.age) || 99)) < 18,
      kind: 'missing',
      person_type: 'missing_person',
    };
  };

  const rosterNode = (side: 'a' | 'b', idx: number, card: NetworkCardData, fallbackName: string): GraphNode => {
    const m = card.rosterMembers?.[idx];
    return {
      id: `${side}:roster_${idx}`,
      name: m?.name ?? fallbackName,
      nameLatin: m?.nameLatin ?? '',
      age: m?.age ?? 0,
      relation: m?.relationship ?? 'Roster',
      minor: (m?.age ?? 99) < 18,
      kind: 'roster',
      person_type: 'roster_member',
    };
  };

  // ── Walk node_matches ──────────────────────────────────────────────

  const matchedAIds = new Set<string>();
  const matchedBIds = new Set<string>();
  const nodeMapA = new Map<string, GraphNode>();
  const nodeMapB = new Map<string, GraphNode>();
  const edges: GraphEdge[] = [];

  const resolveNode = (
    side: 'a' | 'b',
    role: string,
    rosterIdx: number | null,
    nameHint: string,
    card: NetworkCardData,
  ): GraphNode => {
    if (role === 'searcher') return searcherNode(side, card);
    if (role === 'missing_person') return missingPersonNode(side, card, nameHint);
    return rosterNode(side, rosterIdx ?? 0, card, nameHint);
  };

  for (let i = 0; i < nm.length; i++) {
    const m = nm[i];
    const aNode = resolveNode('a', m.role_a, m.roster_index_a, m.name_a, cardA);
    const bNode = resolveNode('b', m.role_b, m.roster_index_b, m.name_b, cardB);

    // Apply explicit person_type overrides when structural role ≠ display intent.
    if (m.person_type_a) aNode.person_type = m.person_type_a;
    if (m.person_type_b) bNode.person_type = m.person_type_b;

    nodeMapA.set(aNode.id, aNode);
    nodeMapB.set(bNode.id, bNode);
    matchedAIds.add(aNode.id);
    matchedBIds.add(bNode.id);

    // isPrimary: prefer match_type field; fall back to primary_match comparison.
    const isPrimary =
      m.match_type !== undefined
        ? m.match_type === 'primary'
        : primaryNm !== null
          ? m.role_a === primaryNm.role_a &&
            m.role_b === primaryNm.role_b &&
            m.name_a === primaryNm.name_a &&
            m.name_b === primaryNm.name_b
          : i === 0;

    // Edge label comes from match_type, not derived from role fields.
    const label = m.match_type === 'primary' ? 'PRIMARY'
                : m.match_type === 'supporting' ? 'SUPPORTING'
                : isPrimary ? 'PRIMARY' : 'SUPPORTING';

    edges.push({
      id: `edge_${i}`,
      aId: aNode.id,
      bId: bNode.id,
      score: m.composite_score,
      primary: isPrimary,
      label,
    });
  }

  // ── Always show searcher and primary missing person (identity context) ─

  const aSearcherId = 'a:searcher';
  const bSearcherId = 'b:searcher';
  const aMissingId  = 'a:missing_0';
  const bMissingId  = 'b:missing_0';

  if (!nodeMapA.has(aSearcherId) && cardA.searcherName) {
    nodeMapA.set(aSearcherId, searcherNode('a', cardA));
  }
  if (!nodeMapB.has(bSearcherId) && cardB.searcherName) {
    nodeMapB.set(bSearcherId, searcherNode('b', cardB));
  }
  if (!nodeMapA.has(aMissingId)) {
    nodeMapA.set(aMissingId, missingPersonNode('a', cardA));
  }
  if (!nodeMapB.has(bMissingId)) {
    nodeMapB.set(bMissingId, missingPersonNode('b', cardB));
  }

  // ── All roster members — flat list, no section separator ──────────

  const allRosterA: GraphNode[] = (cardA.rosterMembers ?? []).map((member, i) => {
    const id = `a:roster_${i}`;
    return nodeMapA.get(id) ?? {
      id, name: member.name, nameLatin: member.nameLatin ?? '',
      age: member.age ?? 0, relation: member.relationship,
      minor: (member.age ?? 99) < 18, kind: 'roster' as const,
      person_type: 'roster_member' as const,
    };
  });
  const allRosterB: GraphNode[] = (cardB.rosterMembers ?? []).map((member, i) => {
    const id = `b:roster_${i}`;
    return nodeMapB.get(id) ?? {
      id, name: member.name, nameLatin: member.nameLatin ?? '',
      age: member.age ?? 0, relation: member.relationship,
      minor: (member.age ?? 99) < 18, kind: 'roster' as const,
      person_type: 'roster_member' as const,
    };
  });

  // ── Flat node order: searcher → all missing → all roster ─────────

  // Deduplicate by name across all node kinds — same person can appear
  // as both a missing_person slot and a roster_member slot.
  const dedup = (nodes: GraphNode[], roster: GraphNode[]): GraphNode[] => {
    const seenNames = new Set(nodes.map(n => n.nameLatin || n.name));
    const filtered = roster.filter(r => !seenNames.has(r.nameLatin || r.name));
    return [...nodes, ...filtered];
  };

  const missingNodesA: GraphNode[] = [];
  const n = nodeMapA.get(aSearcherId);
  if (n) missingNodesA.push(n);
  const seenA = new Set<string>(n ? [n.id] : []);
  for (const node of nodeMapA.values()) {
    if (node.kind === 'missing' && !seenA.has(node.id)) {
      missingNodesA.push(node);
      seenA.add(node.id);
    }
  }
  const nodesA = dedup(missingNodesA, allRosterA);

  const missingNodesB: GraphNode[] = [];
  const nb = nodeMapB.get(bSearcherId);
  if (nb) missingNodesB.push(nb);
  const seenB = new Set<string>(nb ? [nb.id] : []);
  for (const node of nodeMapB.values()) {
    if (node.kind === 'missing' && !seenB.has(node.id)) {
      missingNodesB.push(node);
      seenB.add(node.id);
    }
  }
  const nodesB = dedup(missingNodesB, allRosterB);

  const sessionLabelA = intakeIdA
    ? `Intake A · ${cardA.searcherNameLatin ?? cardA.searcherName ?? 'reporting'}`
    : cardA.title;
  const sessionLabelB = intakeIdB
    ? `Intake B · ${cardB.searcherNameLatin ?? cardB.searcherName ?? 'reporting'}`
    : cardB.title;

  return {
    sideA: { label: sessionLabelA, nodes: nodesA },
    sideB: { label: sessionLabelB, nodes: nodesB },
    edges,
    threshold: 0.78,
  };
}

// ─── SVG layout constants (viewBox units = CSS px at native scale) ───

const W        = 1080;
const xL       = 130;
const xR       = 950;
const nodeW    = 220;
const nodeH    = 64;
const rowGap   = 96;
const headerY  = 42;
const firstRow = 130;

type NodePos = { x: number; y: number; kind: GraphNode['kind'] };

// Flat layout — no divider gaps, every node gets rowGap spacing.
function buildPositions(nodes: GraphNode[], x: number): { pos: Map<string, NodePos>; lastY: number; dividerY: null } {
  const pos = new Map<string, NodePos>();
  let y = firstRow;

  nodes.forEach(node => {
    pos.set(node.id, { x, y, kind: node.kind });
    y += rowGap;
  });

  return { pos, lastY: y, dividerY: null };
}

// ─── MatchGraphV3 ────────────────────────────────────────────────────

type GraphProps = {
  data: GraphData;
  phase: MatchPhase;
  reducedMotion: boolean;
  sideANodes: GraphNode[];
  sideBNodes: GraphNode[];
};

function MatchGraphV3({
  data,
  phase,
  reducedMotion,
  sideANodes,
  sideBNodes,
}: GraphProps) {
  const { sideA, sideB, edges } = data;

  const { pos: posA, lastY: lastYA } = buildPositions(sideANodes, xL);
  const { pos: posB, lastY: lastYB } = buildPositions(sideBNodes, xR);
  const H = Math.max(lastYA, lastYB) + 30;

  // Refs for measuring path lengths at mount (for dashoffset animation).
  const pathRefs = useRef<Map<string, SVGPathElement | null>>(new Map());
  const [pathLengths, setPathLengths] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    const lengths = new Map<string, number>();
    for (const [id, el] of pathRefs.current) {
      if (el && typeof el.getTotalLength === 'function') {
        lengths.set(id, el.getTotalLength());
      }
    }
    setPathLengths(lengths);
  }, [edges.length]);

  const showEdges = reducedMotion ? true : phase === 'linking' || phase === 'merged';

  const allPos = new Map([...posA, ...posB]);

  return (
    <div className="rounded-kin-lg border border-line bg-card">
      {/* Graph card header with legend */}
      <div className="px-4 py-2.5 border-b border-hair flex items-center justify-between">
        <div className="text-[11.5px] font-medium uppercase tracking-wider text-muted">
          Identity graph · {edges.length} linked pairs
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-muted flex items-center gap-1.5">
            <svg width="14" height="3" aria-hidden="true">
              <line x1="0" y1="1.5" x2="14" y2="1.5"
                stroke="oklch(0.55 0.11 155)" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            primary
          </span>
          <span className="text-[11px] text-muted flex items-center gap-1.5">
            <svg width="14" height="3" aria-hidden="true">
              <line x1="0" y1="1.5" x2="14" y2="1.5"
                stroke="oklch(0.55 0.11 155)" strokeWidth="1"
                strokeDasharray="3 3" opacity="0.55" />
            </svg>
            supporting
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height={H}
        style={{ display: 'block' }}
        aria-hidden="true"
      >
        {/* Column headers */}
        <text x={xL} y={headerY} textAnchor="middle" fontSize="11" fontWeight="600"
          fill="oklch(0.55 0.01 240)" letterSpacing="0.06em">
          {sideA.label.toUpperCase()}
        </text>
        <text x={xR} y={headerY} textAnchor="middle" fontSize="11" fontWeight="600"
          fill="oklch(0.55 0.01 240)" letterSpacing="0.06em">
          {sideB.label.toUpperCase()}
        </text>

        {/* Edges (drawn behind nodes) */}
        {showEdges && edges.map((edge, i) => {
          const a = allPos.get(edge.aId);
          const b = allPos.get(edge.bId);
          if (!a || !b) return null;

          const ax = a.x + nodeW / 2, ay = a.y;
          const bx = b.x - nodeW / 2, by = b.y;
          const cx = (ax + bx) / 2;
          const d = `M ${ax} ${ay} C ${cx} ${ay}, ${cx} ${by}, ${bx} ${by}`;
          const midX = (ax + bx) / 2;
          const midY = (ay + by) / 2;
          const labelX = ax + 96;
          const labelY = ay - 10;

          const pathLen = pathLengths.get(edge.id) ?? 1200;
          const animDelay = reducedMotion
            ? undefined
            : edge.primary ? '0ms' : `${120 * i}ms`;
          const pillDelay = reducedMotion ? undefined : '800ms';

          return (
            <g key={edge.id}>
              <path
                ref={el => { pathRefs.current.set(edge.id, el); }}
                d={d}
                fill="none"
                stroke="oklch(0.55 0.11 155)"
                strokeWidth={edge.primary ? 3 : 1}
                strokeDasharray={
                  reducedMotion
                    ? (edge.primary ? undefined : '3 4')
                    : `${pathLen} ${pathLen}`
                }
                strokeLinecap="round"
                opacity={edge.primary ? 1 : 0.55}
                className={reducedMotion ? undefined : 'kin-edge-draw'}
                style={
                  !reducedMotion
                    ? ({
                        '--path-len': pathLen,
                        animationDelay: animDelay,
                        // After animation completes, reset to non-animated dasharray.
                        ['--final-dasharray' as string]: edge.primary ? 'none' : '3 4',
                      } as React.CSSProperties)
                    : undefined
                }
                data-testid={`edge-path-${edge.id}`}
              />
              {/* Relationship label — above stroke, anchored to A-side row */}
              <text
                x={labelX} y={labelY}
                textAnchor="middle" fontSize="10" fontWeight="500"
                fill="oklch(0.55 0.01 240)" letterSpacing="0.08em"
                paintOrder="stroke"
                stroke="white" strokeWidth="3" strokeLinejoin="round"
              >
                {edge.label.toUpperCase()}
              </text>
              {/* Score pill — primary edge only */}
              {edge.primary && (
                <g
                  transform={`translate(${midX - 24},${midY - 11})`}
                  opacity={reducedMotion ? 1 : 0}
                  style={!reducedMotion ? { animation: `kin-fade-in 200ms ease-out ${pillDelay} forwards` } : undefined}
                  data-testid="score-pill"
                >
                  <rect width="48" height="22" rx="11"
                    fill="oklch(0.96 0.03 155)"
                    stroke="oklch(0.55 0.11 155)"
                    strokeWidth="1"
                  />
                  <text x="24" y="14.5" textAnchor="middle" fontSize="11" fontWeight="600"
                    fill="oklch(0.38 0.1 155)"
                    style={{ fontFeatureSettings: "'tnum'" }}>
                    {Math.round(edge.score * 100)}%
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {[
          ...sideANodes.map(n => ({ node: n, pos: posA.get(n.id)! })),
          ...sideBNodes.map(n => ({ node: n, pos: posB.get(n.id)! })),
        ].filter(({ pos }) => pos != null).map(({ node, pos: p }) => {
          const isMissing = node.person_type === 'missing_person';

          const fill   = isMissing ? 'oklch(0.96 0.03 155)' : '#fff';
          const stroke = isMissing ? 'oklch(0.55 0.11 155)' : 'oklch(0.88 0.008 85)';
          const sw     = isMissing ? 1.5 : 1;

          return (
            <g key={node.id} data-testid={`node-${node.id}`}>
              <rect
                x={p.x - nodeW / 2} y={p.y - nodeH / 2}
                width={nodeW} height={nodeH} rx="10"
                fill={fill} stroke={stroke} strokeWidth={sw}
                data-testid={isMissing ? 'missing-node-rect' : undefined}
              />
              {/* Latin name — primary typography */}
              <text x={p.x} y={p.y - 12} textAnchor="middle"
                fontSize="15" fontWeight="bold"
                fill="oklch(0.22 0.01 240)">
                {node.nameLatin || node.name}
              </text>
              {/* Arabic / source-script — secondary line */}
              <text x={p.x} y={p.y + 7} textAnchor="middle"
                fontSize="12" fontWeight="normal"
                fill="oklch(0.22 0.01 240)" opacity="0.75"
                direction="rtl">
                {node.name}
              </text>
              {/* Relation · age · minor */}
              <text x={p.x} y={p.y + 24} textAnchor="middle"
                fontSize="10.5" fill="oklch(0.55 0.01 240)" letterSpacing="0.02em">
                {node.relation} · {node.age}{node.minor ? '  ·  minor' : ''}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── NetworkMatch ────────────────────────────────────────────────────

export function NetworkMatch({
  phase,
  onBack,
  onNewIntake,
  workerLanguage,
  networkResult,
  recordA,
  recordB,
  intakeIdA,
  intakeIdB,
}: NetworkMatchProps) {
  if (!networkResult.matched) return null;

  const wl: Language = workerLanguage ?? 'en';
  const rA = recordA ?? DEFAULT_RECORD_A;
  const rB = recordB ?? DEFAULT_RECORD_B;
  const idA = intakeIdA ?? 'A';
  const idB = intakeIdB ?? 'B';

  const [auditPanelOpen, setAuditPanelOpen] = useState(false);

  const reducedMotion =
    typeof window !== 'undefined'
      ? (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)
      : false;

  const merged = phase === 'merged';

  const graphData = buildGraphData(networkResult, rA, rB, idA, idB);
  const panelSpeakerLang = rA.speakerLanguage;

  return (
    <div className="max-w-[1280px] mx-auto w-full">

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
        <div className="flex items-center gap-2">
          {merged && intakeIdA && intakeIdB && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAuditPanelOpen(v => !v)}
              aria-expanded={auditPanelOpen}
              aria-controls="match-audit-panel"
            >
              {auditPanelOpen ? 'Hide audit trail' : 'Show audit trail'}
            </Button>
          )}
          {onNewIntake && (
            <Button
              variant="primary"
              size="sm"
              icon={<IconMic size={14} />}
              onClick={onNewIntake}
            >
              Begin new intake
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            icon={<IconArrowRight className="rotate-180" size={16} />}
            onClick={onBack}
          >
            Back to intake
          </Button>
        </div>
      </div>

      {/* Main content — 60/40 split when audit panel is open */}
      <div className={`flex gap-4 ${auditPanelOpen ? 'items-start' : ''}`}>

        {/* Left: graph card + confirmation banner */}
        <div className={auditPanelOpen ? 'flex-[3] min-w-0' : 'flex-1'}>

          <div className={merged ? 'kin-merge-pulse rounded-kin-lg' : ''}>
            <MatchGraphV3
              data={graphData}
              phase={phase}
              reducedMotion={reducedMotion}
              sideANodes={graphData.sideA.nodes}
              sideBNodes={graphData.sideB.nodes}
            />
          </div>

          {/* Merged confirmation banner */}
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
                <div className="text-[12px] font-medium uppercase tracking-wider text-muted mb-1">
                  Matched name pairs
                </div>
                <p className="text-[11px] text-muted/70 mb-3" data-testid="threshold-label">
                  Threshold: {Math.round(graphData.threshold * 100)}% — below this, caseworker decides
                </p>
                <div className="space-y-2">
                  {networkResult.node_matches.map((nm, i) => {
                    const isPrimary =
                      networkResult.primary_match !== null
                        ? nm.role_a === networkResult.primary_match.role_a &&
                          nm.role_b === networkResult.primary_match.role_b &&
                          nm.name_a === networkResult.primary_match.name_a
                        : i === 0;
                    return (
                      <div key={i} className="flex items-center gap-3 text-[14px]">
                        <span
                          className={`w-1.5 h-1.5 rounded-full shrink-0 mt-0.5 ${isPrimary ? 'bg-green' : 'bg-line'}`}
                        />
                        <span className="text-ink font-medium">{nm.name_a}</span>
                        <span className="text-muted text-[12px]">
                          {nm.role_a} → {nm.role_b}
                        </span>
                        <span className="text-ink font-medium">{nm.name_b}</span>
                        <span className="ml-auto text-muted text-[12px] font-mono">
                          {Math.round(nm.composite_score * 100)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

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

        {/* Right: audit panel (40%) */}
        {auditPanelOpen && intakeIdA && intakeIdB && (
          <div
            id="match-audit-panel"
            className="flex-[2] min-w-0 min-h-[600px] rounded-kin-lg overflow-hidden border border-line"
          >
            <MatchAuditPanel
              intakeIdA={intakeIdA}
              intakeIdB={intakeIdB}
              networkResult={networkResult}
              speakerLanguage={panelSpeakerLang}
              onClose={() => setAuditPanelOpen(false)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
