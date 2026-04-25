/* CompletenessMeter — segmented progress indicator (no percentages); shows structure instead. */
import type { CompletenessSegment } from '../../lib/types';

// Principle 10 adjacent: avoid numeric progress. Show structure instead.
export type CompletenessMeterProps = {
  segments: CompletenessSegment[];
};

const CompletenessMeter = ({ segments }: CompletenessMeterProps) => {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-[12px] font-medium uppercase tracking-wider text-muted">Record completeness</div>
        <div className="text-[12px] text-muted">{segments.filter(s => s.filled).length} of {segments.length} sections</div>
      </div>
      <div className="flex gap-1.5">
        {segments.map(s => (
          <div key={s.key} className="flex-1">
            <div className={`h-2 rounded-full border ${s.filled ? "bg-primary border-primary" : "bg-white border-line"}`} />
            <div className="mt-1.5 text-[11px] text-muted truncate">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export { CompletenessMeter };
