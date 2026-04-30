/* ============================================================================
 * KIN — queue-view.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • SEEDED_RECORDS is demo data. Replace with your records query
 *     (probably react-query against /api/records or similar). Schema:
 *       { id, name, age, sex, lastSeen, status, minor, language, ts }
 *     status enum: 'open' | 'matched' | 'closed' | 'crisis'
 *   • Filters: All / Open / Matched / Crisis. The Crisis filter shows
 *     records where the crisis flag was raised even if since-resolved —
 *     this is the operations-review surface. Don't filter to "active
 *     crisis only."
 *   • Row click → opens record in Intake panel as READ-ONLY
 *     (record-readonly.jsx). Editing from queue is a separate flow
 *     (out of scope for hackathon). The read-only banner is load-bearing
 *     here — it tells the worker they're reviewing, not capturing.
 *   • Visual: hairline rows, no zebra striping. Status is a Chip on the
 *     right, language is muted text. Density is intentional — this is a
 *     scan-many-quickly surface.
 *   • The minor flag in row badges uses Shield icon + amber tone,
 *     matching record-card. Stay consistent with the triple-redundancy
 *     pattern — same vocabulary across surfaces.
 * ============================================================================
 * Queue View — list of records with filters. Click row → read-only Intake. */

const SEEDED_RECORDS = [
  {
    id: 89,  name: "Mohammed Al-Saleh", native: "محمد الصالح", rtl: true,
    age: "34", status: "complete", statusLabel: "Complete",
    updated: "Today · 09:14", sync: "synced",
    summary: "Self-registered · separated from spouse and son · last seen Jordan border",
  },
  {
    id: 102, name: "Ana Beltrán Ruiz", age: "29", status: "complete", statusLabel: "Complete",
    updated: "Today · 10:42", sync: "syncing",
    summary: "Reuniting with brother · last seen Tuxtla Gutiérrez",
  },
  {
    id: 138, name: "Yusuf Karimi", native: "یوسف کریمی", rtl: true,
    age: "16", status: "minor", statusLabel: "Incomplete · Minor protection",
    updated: "Today · 11:08", sync: "local",
    summary: "Unaccompanied minor · Guardian/CP fields pending",
  },
  {
    id: 141, name: "Daniela Ortiz", age: "41", status: "complete", statusLabel: "Complete",
    updated: "Today · 11:55", sync: "local",
    summary: "Searching for daughter · last seen Tapachula bus terminal",
  },
];

const STATUS_TONE = {
  complete: "green",
  minor:    "amber",
  crisis:   "red",
  active:   "primary",
};

function QueueRow({ r, onOpen }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(r)}
      className="w-full text-left grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-5 py-3 border-t border-hair hover:bg-subtle transition-colors"
    >
      <div className="min-w-0">
        <div className="flex items-baseline gap-3 flex-wrap">
          <span className="text-[16px] text-ink font-medium truncate">{r.name}</span>
          {r.native && <span className={`text-[15px] text-ink/80 ${r.rtl ? "rtl" : ""}`}>{r.native}</span>}
          <span className="font-mono text-[11px] text-muted">#{r.id}</span>
        </div>
        <div className="text-[13px] text-muted truncate mt-0.5">{r.summary}</div>
      </div>
      <Chip
        icon={r.status === "minor" ? <IconShield size={12} /> :
              r.status === "crisis" ? <IconAlert size={12} /> : <IconCheck size={12} />}
        tone={STATUS_TONE[r.status] || "neutral"}
      >{r.statusLabel}</Chip>
      <div className="text-[12px] text-muted font-mono tabular-nums w-[110px] text-right">{r.updated}</div>
      <span className={`inline-flex items-center gap-1.5 text-[12px] ${
        r.sync === "synced" ? "text-green" : r.sync === "syncing" ? "text-primary" : "text-muted"
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${
          r.sync === "synced" ? "bg-green" : r.sync === "syncing" ? "bg-primary animate-pulse" : "bg-muted"
        }`} />
        {r.sync === "synced" ? "Synced" : r.sync === "syncing" ? "Syncing" : "Local-only"}
      </span>
    </button>
  );
}

function QueueView({ records, onOpen, onNew }) {
  const [filter, setFilter] = React.useState("all");
  const filtered = React.useMemo(() => {
    if (filter === "all") return records;
    if (filter === "incomplete") return records.filter(r => r.status === "minor");
    if (filter === "today") return records;
    return records;
  }, [records, filter]);

  const filters = [
    { id: "all",        label: "All",        count: records.length },
    { id: "incomplete", label: "Incomplete", count: records.filter(r => r.status === "minor").length },
    { id: "today",      label: "Today",      count: records.length },
  ];

  return (
    <div className="max-w-[1100px] mx-auto px-6 py-6">
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
                active ? "bg-primary text-white border-primary" : "bg-white text-ink border-line hover:bg-subtle"
              }`}
            >
              {f.label}
              <span className={`ml-1.5 text-[11px] font-mono ${active ? "text-white/80" : "text-muted"}`}>{f.count}</span>
            </button>
          );
        })}
      </div>

      <div className="bg-card border border-line rounded-kin-lg overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-muted">
          <div>Record</div><div>Status</div><div className="w-[110px] text-right">Updated</div><div>Sync</div>
        </div>
        {filtered.length === 0 ? (
          <div className="px-5 py-12 text-center text-[14px] text-muted border-t border-hair">
            No records match this filter.
          </div>
        ) : filtered.map(r => <QueueRow key={r.id} r={r} onOpen={onOpen} />)}
      </div>
    </div>
  );
}

Object.assign(window, { QueueView, SEEDED_RECORDS });
