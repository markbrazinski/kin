/* SectionHeader — collapsible section title row with icon, optional meta, and chevron toggle. */
import type { ReactNode } from 'react';
import { IconChevron } from '../icons';

export type SectionHeaderProps = {
  title: ReactNode;
  icon?: ReactNode;
  meta?: ReactNode;
  expanded?: boolean;
  onToggle?: () => void;
};

const SectionHeader = ({ title, icon, meta, expanded = true, onToggle }: SectionHeaderProps) => (
  <div className="flex items-center justify-between py-3">
    <button
      type="button"
      onClick={onToggle}
      className="flex items-center gap-2.5 text-ink"
    >
      <span className="text-muted">{icon}</span>
      <span className="text-[21px] font-semibold tracking-[-0.005em]">{title}</span>
      {meta}
    </button>
    {onToggle && (
      <span className={`text-muted transition-transform duration-150 ${expanded ? "" : "-rotate-90"}`}>
        <IconChevron size={18} />
      </span>
    )}
  </div>
);

export { SectionHeader };
