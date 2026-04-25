/* Field — labeled value row with optional verify chip, sub-value, and populate-flash animation. */
import type { ReactNode } from 'react';
import { IconInfo } from '../icons';
import { Chip } from './Chip';

// Principle 10: no confidence %. If a value is awaiting verification, show a "verify" chip.
export type FieldProps = {
  label: ReactNode;
  value?: ReactNode;
  extra?: ReactNode;
  verify?: boolean;
  justPopulated?: boolean;
  subValue?: ReactNode;
};

const Field = ({ label, value, extra, verify, justPopulated, subValue }: FieldProps) => {
  return (
    <div className={`py-2.5 px-0 -mx-0 rounded-kin ${justPopulated ? "kin-populate" : ""}`}>
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-medium uppercase tracking-wider text-muted">{label}</div>
        {verify && (
          <Chip icon={<IconInfo size={12} />} tone="amber">Verify</Chip>
        )}
      </div>
      <div className="mt-1 text-[18px] text-ink leading-snug">
        {value === null || value === undefined || value === ""
          ? <span className="text-muted">—</span>
          : value}
      </div>
      {subValue && (
        <div className="mt-1 text-[15px] text-muted leading-snug">{subValue}</div>
      )}
      {extra}
    </div>
  );
};

export { Field };
