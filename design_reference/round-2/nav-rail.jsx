/* ============================================================================
 * KIN — nav-rail.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: 44px width. This is min hit-target on touch + matches
 *     the iOS/macOS sidebar rail convention. Wider feels desktop-app
 *     bloated; narrower fails accessibility.
 *   • DO NOT CHANGE: active-state pattern = bg-card + 2px primary left
 *     accent + ink text. The 2px accent is what makes it readable from
 *     across the room during a demo. No filled-color tabs.
 *   • Two routes only: 'intake' (mic icon) and 'queue' (list icon). Do
 *     NOT add settings/profile/etc. icons here — Settings lives elsewhere
 *     (overflow on top bar). Adding rail items dilutes the bimodal
 *     (capture vs. review) story.
 *   • Bottom: KIN wordmark + sync-status dot. Dot color follows the same
 *     idle/busy/down vocabulary as the structlog heartbeat — keep them
 *     visually synced; they refer to the same underlying state.
 *   • Accessibility: each rail button gets aria-label (icons-only). The
 *     active route also sets aria-current="page". Preserve both.
 * ============================================================================
 * Navigation Rail — 44px wide, full height, hairline border, no shadow.
 * Two icons: Intake (mic), Queue (list). Active state: bg + 2px left accent. */

function NavRail({ route, setRoute, queuedCount, syncOk = true }) {
  const items = [
    { key: "intake", label: "Intake", icon: <IconMic size={18} />, hot: "⌘1" },
    { key: "queue",  label: "Queue",  icon: <IconList size={18} />, hot: "⌘2", badge: queuedCount },
  ];
  return (
    <nav
      aria-label="Primary"
      className="shrink-0 w-[44px] bg-card border-r border-line flex flex-col"
    >
      {/* Wordmark anchor — matches top bar dot pattern */}
      <div className="h-14 flex items-center justify-center border-b border-hair">
        <div className="w-6 h-6 rounded-kin border border-ink/70 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-primary" />
        </div>
      </div>

      <ul className="flex-1 py-2 flex flex-col gap-0.5">
        {items.map((it) => {
          const active = route === it.key;
          return (
            <li key={it.key} className="relative">
              {active && (
                <span aria-hidden="true" className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-primary rounded-r" />
              )}
              <button
                type="button"
                onClick={() => setRoute(it.key)}
                title={`${it.label} (${it.hot})`}
                aria-current={active ? "page" : undefined}
                className={`group w-full h-10 flex items-center justify-center relative transition-colors
                  ${active ? "text-primary bg-primary-soft" : "text-muted hover:text-ink hover:bg-subtle"}`}
              >
                {it.icon}
                {it.badge ? (
                  <span className="absolute top-1.5 right-1.5 min-w-[14px] h-[14px] px-1 rounded-full bg-primary text-white text-[9px] font-semibold flex items-center justify-center leading-none">
                    {it.badge > 9 ? "9+" : it.badge}
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>

      {/* Sync dot */}
      <div className="h-12 flex flex-col items-center justify-center gap-1 border-t border-hair">
        <div title={syncOk ? "Local hub reachable" : "Local-only"}
             className={`w-1.5 h-1.5 rounded-full ${syncOk ? "bg-green" : "bg-amber"}`} />
        <div className="text-[9px] font-mono uppercase tracking-wider text-muted">v0.4</div>
      </div>
    </nav>
  );
}

const IconList = (p) => (
  <Icon {...p}>
    <path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/>
    <circle cx="4" cy="6" r="1" fill="currentColor" stroke="none"/>
    <circle cx="4" cy="12" r="1" fill="currentColor" stroke="none"/>
    <circle cx="4" cy="18" r="1" fill="currentColor" stroke="none"/>
  </Icon>
);

Object.assign(window, { NavRail, IconList });
