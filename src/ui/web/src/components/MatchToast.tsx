/* MatchToast — surfaces match_proposed events as a deliberate
   user-driven navigation primitive (not auto-route).

   Visual structure adapted from design ref nav-app.jsx:178-202:
   bottom-right, green-accent, two buttons. Deliberately drops the
   design ref's 1.5s auto-open timer per S2-fix1 decision —
   auto-routing on match_proposed is fundamentally ambiguous in a
   multi-turn flow (every turn returns status=completed). User
   clicks "Open match" or "Dismiss"; or 30s silent auto-dismiss
   removes the toast without navigating. */
import { useEffect } from 'react';
import { IconLink } from './icons';
import { Button } from './primitives';

const SILENT_DISMISS_MS = 30_000;

export type MatchToastProps = {
  open: boolean;
  onOpen: () => void;
  onDismiss: () => void;
};

export function MatchToast({ open, onOpen, onDismiss }: MatchToastProps) {
  useEffect(() => {
    if (!open) return;
    const handle = setTimeout(onDismiss, SILENT_DISMISS_MS);
    return () => clearTimeout(handle);
  }, [open, onDismiss]);

  if (!open) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-30 w-[360px] bg-card border border-green/40 rounded-kin-lg overflow-hidden shadow-elevated"
    >
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-green">
          <IconLink size={12} /> Match candidate found
        </div>
        <div className="text-[13px] text-muted mt-1.5">
          Open match to review side-by-side.
        </div>
      </div>
      <div className="border-t border-hair bg-subtle/60 px-3 py-2 flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onDismiss}>
          Dismiss
        </Button>
        <Button variant="primary" size="sm" onClick={onOpen}>
          Open match
        </Button>
      </div>
    </div>
  );
}
