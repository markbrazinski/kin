/* MinorStrip — persistent amber banner inside the record card when a minor is detected.
   Slides in on first appearance; never dismissable. */
import { useState, useEffect } from 'react';
import { IconShield } from './icons';

export type MinorStripProps = {
  visible: boolean;
  minorName?: string;
};

export function MinorStrip({ visible, minorName }: MinorStripProps) {
  // Track whether the strip has previously been mounted so we only animate on
  // the first appearance, not on every re-render or prop change.
  const [hasAnimated, setHasAnimated] = useState(false);

  useEffect(() => {
    if (visible && !hasAnimated) {
      setHasAnimated(true);
    }
  }, [visible, hasAnimated]);

  if (!visible) return null;

  // Apply slide-in class only on first mount (when hasAnimated just became true).
  // After that, the flag is set and we skip the animation class.
  const animClass = hasAnimated ? '' : ' kin-strip-in';

  return (
    <div
      className={`flex items-center gap-2.5 px-4 py-3 bg-amber-soft border-b border-amber/30 rounded-t-kin-lg${animClass}`}
    >
      <IconShield size={18} className="text-[oklch(0.42_0.12_75)] shrink-0" />
      <div>
        <div className="text-[14px] font-medium text-[oklch(0.32_0.12_75)] leading-tight">
          Child protection routing required — minor detected
        </div>
        {minorName && (
          <div className="text-[12.5px] text-[oklch(0.42_0.12_75)] mt-0.5">{minorName}</div>
        )}
      </div>
    </div>
  );
}
