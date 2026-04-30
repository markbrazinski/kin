/* ============================================================================
 * KIN — record-readonly.jsx (read-only RecordCard wrapper)
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • Wraps RecordCard with a banner. Do NOT fork the RecordCard component
 *     for read-only — pass `disabled` and render the banner above it. This
 *     keeps the layout identical so the worker recognizes the form on
 *     reopen.
 *   • Banner copy: "Read-only — reopen for editing." with a primary
 *     "Reopen" button. The Reopen action in production triggers an audit
 *     log entry (out of scope this build, button is a placeholder).
 *   • Banner uses amber-soft tone (advisory, not error). Don't escalate to
 *     red — read-only is normal queue behavior, not a failure state.
 * ============================================================================
 * RecordCard read-only mode + reuse. Imports the Round 1 RecordCard as-is.
 * Adds: read-only banner when reopening from queue. */

function RecordCardReadOnlyBanner({ onResume }) {
  return (
    <div className="mb-3 bg-card border border-line rounded-kin px-4 py-3 flex items-center gap-3">
      <div className="w-8 h-8 rounded-kin border border-line bg-subtle/60 text-muted flex items-center justify-center">
        <IconLock size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[14px] font-semibold text-ink">Viewing previous record</div>
        <div className="text-[13px] text-muted mt-0.5">Read-only · open from the queue. Editing not enabled in this build.</div>
      </div>
      <Button size="sm" variant="secondary" onClick={onResume}>New intake</Button>
    </div>
  );
}

Object.assign(window, { RecordCardReadOnlyBanner });
