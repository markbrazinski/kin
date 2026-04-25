/* Chip — pill badge with optional icon and tone color (icon + text + color, never color alone). */
import type { ReactNode } from 'react';

export type ChipTone = 'neutral' | 'primary' | 'amber' | 'red' | 'green';

export type ChipProps = {
  icon?: ReactNode;
  children?: ReactNode;
  tone?: ChipTone;
  className?: string;
};

const Chip = ({ icon, children, tone = "neutral", className = "" }: ChipProps) => {
  const tones: Record<ChipTone, string> = {
    neutral: "bg-subtle border-line text-ink",
    primary: "bg-primary-soft border-primary/20 text-primary",
    amber:   "bg-amber-soft border-amber/40 text-[oklch(0.42_0.12_75)]",
    red:     "bg-red-soft border-red/30 text-red",
    green:   "bg-green-soft border-green/30 text-[oklch(0.38_0.1_155)]",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 h-7 px-2.5 text-[13px] font-medium border rounded-kin ${tones[tone]} ${className}`}>
      {icon}
      {children}
    </span>
  );
};

export { Chip };
