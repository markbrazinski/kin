/* ChicletRibbon — 2-chiclet family-network completeness indicator.
   Replaces CompletenessMeter; tracks Searcher + Missing-persons fill state. */
import React from 'react';

export type ChicletRibbonProps = {
  searcherName: string;
  missingPersonsCount: number;
  detailedCount?: number;
};

type ChicletProps = {
  title: string;
  subCount: string;
  filled: boolean;
  partial?: boolean;
  stagger?: boolean;
};

function Chiclet({ title, subCount, filled, partial, stagger }: ChicletProps) {
  const dotColor = filled
    ? 'bg-primary'
    : partial
      ? 'bg-amber'
      : 'bg-line';

  return (
    <div className="border border-hair rounded-kin px-3 py-2 bg-white flex flex-col gap-0.5">
      <div className="flex items-center gap-1.5">
        <div
          className={`w-1.5 h-1.5 rounded-full transition-colors duration-300 ${dotColor}`}
          style={stagger ? { transitionDelay: '120ms' } : undefined}
        />
        <span className="text-[12.5px] font-medium text-ink truncate">{title}</span>
      </div>
      <span
        key={subCount}
        className="text-[11.5px] text-muted transition-opacity duration-200"
      >
        {subCount}
      </span>
    </div>
  );
}

export function ChicletRibbon({ searcherName, missingPersonsCount, detailedCount = 0 }: ChicletRibbonProps) {
  const searcherFilled = !!searcherName;
  const searcherSubCount = searcherFilled ? '1 · identified' : '—';

  const missingFilled = missingPersonsCount > 0 && detailedCount === missingPersonsCount;
  const missingPartial = missingPersonsCount > 0 && detailedCount < missingPersonsCount;
  const missingSubCount =
    missingPersonsCount === 0
      ? '— · none yet'
      : `${detailedCount} of ${missingPersonsCount} detailed`;

  return (
    <div className="grid grid-cols-2 gap-2">
      <Chiclet
        title="Searcher"
        subCount={searcherSubCount}
        filled={searcherFilled}
      />
      <Chiclet
        title="Missing persons"
        subCount={missingSubCount}
        filled={missingFilled}
        partial={missingPartial}
        stagger
      />
    </div>
  );
}
