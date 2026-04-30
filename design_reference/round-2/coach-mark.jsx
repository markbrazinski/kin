/* ============================================================================
 * KIN — coach-mark.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • Storage key: 'kin.coachmark.dismissed'. Don't change without
 *     migration — returning users see it again if you do.
 *   • Auto-cleared when presentation mode activates (?present=1 or
 *     ⌘⇧P). This is intentional — judges should never see the coach
 *     mark. presentation-mode.jsx handles the clear; do not also clear
 *     here, you'll race.
 *   • Copy is plain-language, max 2 short sentences per panel. Resist
 *     the urge to add more — this is first-load friction and every
 *     extra sentence costs trust.
 *   • Position: anchored to nav-rail (left side). If you move the rail
 *     to the right (RTL UI direction for full-Arabic deployments —
 *     future scope), mirror this anchor.
 * ============================================================================
 * Coach-mark — first-load orientation, dismissible. localStorage-persisted.
 * Cleared automatically when presentation mode activates. */

const COACH_KEY = "kin.coachmark.v1.dismissed";

function useCoachMark(presentationActive) {
  const [show, setShow] = React.useState(false);
  React.useEffect(() => {
    try {
      const dismissed = localStorage.getItem(COACH_KEY);
      if (!dismissed) setShow(true);
    } catch (_) {}
  }, []);
  React.useEffect(() => {
    if (presentationActive && show) {
      setShow(false);
      try { localStorage.setItem(COACH_KEY, "1"); } catch(_) {}
    }
  }, [presentationActive, show]);

  const dismiss = () => {
    setShow(false);
    try { localStorage.setItem(COACH_KEY, "1"); } catch(_) {}
  };
  return { show, dismiss };
}

function CoachMark({ show, onDismiss }) {
  if (!show) return null;
  return (
    <div
      role="dialog"
      aria-label="Quick orientation"
      className="kin-rise mx-6 mt-4 mb-1 bg-card border border-line rounded-kin-lg overflow-hidden"
    >
      <div className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-kin border border-primary/30 bg-primary-soft text-primary flex items-center justify-center shrink-0">
            <IconInfo size={16} />
          </div>
          <div className="min-w-0">
            <div className="text-[14px] font-semibold text-ink">Welcome — quick orientation</div>
            <div className="text-[13px] text-muted mt-0.5">
              Use the rail on the left to switch between <span className="text-ink font-medium">Intake</span> and the <span className="text-ink font-medium">Queue</span>. Press <span className="font-mono text-ink">Begin</span> to start an intake; the system speaks the language detected from the audio. Pipeline events stream in the right sidebars as proof of work.
            </div>
          </div>
        </div>
        <div className="sm:ml-auto flex items-center gap-2 shrink-0">
          <Button size="sm" variant="secondary" onClick={onDismiss}>Got it</Button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { useCoachMark, CoachMark });
