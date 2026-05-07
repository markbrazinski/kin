/* Queue view — list of persisted intake records with filters.
   Fetches from GET /intake/records on mount and on view activation.
   Prototype: design_reference/round-2/queue-view.jsx */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Chip, Button } from './primitives';
import { IconMic, IconShield, IconAlert, IconCheck, IconArrowRight } from './icons';
import type { IntakeRecord, IntakeStatus } from '../lib/intakeRecord';
import { containsNonLatinScript } from '../lib/script';
import { dirFor } from '../lib/i18n';

// ---- Status chip derivation -------------------------------------------------

type StatusShape = { label: string; tone: 'green' | 'amber' | 'red'; icon: React.ReactElement };

function statusShape(record: IntakeRecord): StatusShape {
  if (record.is_crisis) {
    return { label: 'Crisis', tone: 'red', icon: <IconAlert size={12} /> };
  }
  if (record.is_minor && record.status === 'partial') {
    return { label: 'Minor · Incomplete', tone: 'amber', icon: <IconShield size={12} /> };
  }
  if (record.status === 'partial') {
    return { label: 'Incomplete', tone: 'amber', icon: <IconArrowRight size={12} /> };
  }
  return { label: 'Complete', tone: 'green', icon: <IconCheck size={12} /> };
}

// ---- Timestamp formatting ---------------------------------------------------

function formatUpdated(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  return isToday ? `Today · ${time}` : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ` · ${time}`;
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
}

// ---- QueueRow ---------------------------------------------------------------

type QueueRowProps = {
  record: IntakeRecord;
  onOpen: (record: IntakeRecord) => void;
};

export function QueueRow({ record, onOpen }: QueueRowProps) {
  const latinName = record.full_name_transliteration || record.full_name_source_script;
  const hasNative =
    record.full_name_source_script &&
    record.full_name_transliteration &&
    containsNonLatinScript(record.full_name_source_script);
  const nativeDir = dirFor(record.language as import('../lib/types').Language);

  const shape = statusShape(record);

  const summary = [
    record.relationship_to_seeker,
    record.last_seen_location ? `last seen ${record.last_seen_location}` : null,
  ].filter(Boolean).join(' · ') || 'No summary available';

  return (
    <button
      type="button"
      onClick={() => onOpen(record)}
      className="w-full text-left grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-5 py-3 border-t border-hair hover:bg-subtle transition-colors"
    >
      <div className="min-w-0">
        <div className="flex items-baseline gap-3 flex-wrap">
          <span className="text-[16px] text-ink font-medium truncate">{latinName || '—'}</span>
          {hasNative && (
            <span dir={nativeDir} className={`text-[15px] text-ink/80 ${nativeDir === 'rtl' ? 'rtl' : ''}`}>
              {record.full_name_source_script}
            </span>
          )}
          <span className="font-mono text-[11px] text-muted">#{record.id.slice(0, 8)}</span>
        </div>
        <div className="text-[13px] text-muted truncate mt-0.5">{summary}</div>
      </div>
      <Chip icon={shape.icon} tone={shape.tone}>{shape.label}</Chip>
      <div className="text-[12px] text-muted font-mono tabular-nums w-[110px] text-right">
        {formatUpdated(record.updated_at)}
      </div>
      <span className="inline-flex items-center gap-1.5 text-[12px] text-muted">
        <span className="w-1.5 h-1.5 rounded-full bg-muted" />
        Local-only
      </span>
    </button>
  );
}

// ---- QueueView --------------------------------------------------------------

type FilterId = 'all' | 'incomplete' | 'today';

export type QueueViewProps = {
  records: IntakeRecord[];
  onOpen: (record: IntakeRecord) => void;
  onNew: () => void;
};

export function QueueView({ records, onOpen, onNew }: QueueViewProps) {
  const [filter, setFilter] = useState<FilterId>('all');

  const filtered = useMemo(() => {
    if (filter === 'incomplete') {
      return records.filter(r => r.status === 'partial');
    }
    if (filter === 'today') {
      return records.filter(r => isToday(r.updated_at));
    }
    return records;
  }, [records, filter]);

  const filters: { id: FilterId; label: string; count: number }[] = [
    { id: 'all',        label: 'All',        count: records.length },
    { id: 'incomplete', label: 'Incomplete', count: records.filter(r => r.status === 'partial').length },
    { id: 'today',      label: 'Today',      count: records.filter(r => isToday(r.updated_at)).length },
  ];

  return (
    <div className="max-w-[1100px] mx-auto w-full">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Queue</div>
          <h1 className="text-[24px] font-semibold text-ink mt-0.5 tracking-[-0.01em]">
            Records on this device
          </h1>
          <div className="text-[14px] text-muted mt-1">
            Click any record to reopen. Local-only records will sync when the hub is reachable.
          </div>
        </div>
        <Button variant="primary" icon={<IconMic size={16} />} onClick={onNew}>New intake</Button>
      </div>

      <div className="flex items-center gap-1.5 mb-4 flex-wrap">
        {filters.map(f => {
          const active = filter === f.id;
          return (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`h-8 px-3 text-[13px] font-medium rounded-kin border transition-colors ${
                active ? 'bg-primary text-white border-primary' : 'bg-white text-ink border-line hover:bg-subtle'
              }`}
            >
              {f.label}
              <span className={`ml-1.5 text-[11px] font-mono ${active ? 'text-white/80' : 'text-muted'}`}>
                {f.count}
              </span>
            </button>
          );
        })}
      </div>

      <div className="bg-card border border-line rounded-kin-lg overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-muted">
          <div>Record</div>
          <div>Status</div>
          <div className="w-[110px] text-right">Updated</div>
          <div>Sync</div>
        </div>
        {filtered.length === 0 ? (
          <div className="px-5 py-12 text-center text-[14px] text-muted border-t border-hair">
            No records match this filter.
          </div>
        ) : (
          filtered.map(r => <QueueRow key={r.id} record={r} onOpen={onOpen} />)
        )}
      </div>
    </div>
  );
}

// ---- useQueueRecords --------------------------------------------------------

export function useQueueRecords(active: boolean) {
  const [records, setRecords] = useState<IntakeRecord[]>([]);

  const fetch_ = useCallback(() => {
    fetch('/intake/records')
      .then(r => r.json())
      .then((data: { records?: IntakeRecord[] }) => setRecords(data.records ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (active) fetch_();
  }, [active, fetch_]);

  return { records, refetch: fetch_ };
}
