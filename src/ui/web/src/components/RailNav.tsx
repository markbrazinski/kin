/* Persistent 44px icon rail. Two routes: intake (capture) + queue (review).
   Active state = bg-primary-soft + 2px primary left accent. Settings/Help
   intentionally omitted — rail is bimodal capture-vs-review per design ref
   nav-rail.jsx. */
import React, { useRef, useCallback, useState, useEffect } from 'react';
import { IconMic, IconList } from './icons';

const BADGE_BASE_CLS =
  'absolute top-1.5 right-1.5 min-w-[14px] h-[14px] px-1 rounded-full bg-primary text-white text-[9px] font-semibold flex items-center justify-center leading-none';
const BADGE_TICK_DURATION_MS = 200;  // animation is 150ms; small buffer

/* Bundle 1.5 S5: badge with kin-badge-tick animation on count
   INCREASE. animateKey is incremented by the parent when
   queuedCount goes up; this component watches the key, applies the
   kin-badge-tick class transiently, and clears it after the
   animation finishes so a later decrease (which keeps animateKey
   constant) renders the bare badge. */
function BadgeSpan({ badge, animateKey }: { badge: number; animateKey: number }) {
  const [animating, setAnimating] = useState(false);
  const prevKeyRef = useRef(animateKey);
  useEffect(() => {
    if (animateKey !== prevKeyRef.current) {
      prevKeyRef.current = animateKey;
      setAnimating(true);
      const handle = setTimeout(() => setAnimating(false), BADGE_TICK_DURATION_MS);
      return () => clearTimeout(handle);
    }
    return undefined;
  }, [animateKey]);

  return (
    <span className={`${BADGE_BASE_CLS}${animating ? ' kin-badge-tick' : ''}`}>
      {badge > 9 ? '9+' : badge}
    </span>
  );
}

export type RailRoute = 'intake' | 'queue';

export type RailNavProps = {
  route: RailRoute;
  setRoute: (route: RailRoute) => void;
  queuedCount?: number;
  pendingMatchCount?: number;
  syncOk?: boolean;
};

type RailItem = {
  key: RailRoute;
  label: string;
  icon: React.ReactNode;
  hot: string;
  badge?: number;
};

export function RailNav({ route, setRoute, queuedCount, pendingMatchCount, syncOk = true }: RailNavProps) {
  const items: RailItem[] = [
    { key: 'intake', label: 'Intake', icon: <IconMic size={18} />, hot: '⌘1', badge: pendingMatchCount || undefined },
    { key: 'queue',  label: 'Queue',  icon: <IconList size={18} />, hot: '⌘2', badge: queuedCount },
  ];

  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);

  /* Bundle 1.5 S5: kin-badge-tick on count INCREASE only. Decrease
     (confirm/reject decrement) does NOT animate — count going down
     should not pull worker attention. tickKey increments on each
     detected increase; React's key prop forces a fresh mount of the
     badge span so the CSS animation replays. */
  const prevCountRef = useRef<number | undefined>(queuedCount);
  const [tickKey, setTickKey] = useState(0);
  useEffect(() => {
    const prev = prevCountRef.current ?? 0;
    const curr = queuedCount ?? 0;
    if (curr > prev) setTickKey((k) => k + 1);
    prevCountRef.current = queuedCount;
  }, [queuedCount]);

  const prevMatchRef = useRef<number | undefined>(pendingMatchCount);
  const [matchTickKey, setMatchTickKey] = useState(0);
  useEffect(() => {
    const prev = prevMatchRef.current ?? 0;
    const curr = pendingMatchCount ?? 0;
    if (curr > prev) setMatchTickKey((k) => k + 1);
    prevMatchRef.current = pendingMatchCount;
  }, [pendingMatchCount]);

  const onKeyDown = useCallback(
    (idx: number) => (e: React.KeyboardEvent<HTMLButtonElement>) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = (idx + 1) % items.length;
        buttonsRef.current[next]?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = (idx - 1 + items.length) % items.length;
        buttonsRef.current[prev]?.focus();
      }
    },
    [items.length],
  );

  return (
    <nav
      aria-label="Primary"
      className="shrink-0 w-[44px] bg-card border-r border-line flex flex-col"
    >
      {/* Wordmark anchor */}
      <div className="h-14 flex items-center justify-center border-b border-hair">
        <div className="w-6 h-6 rounded-kin border border-ink/70 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-primary" />
        </div>
      </div>

      <ul className="flex-1 py-2 flex flex-col gap-0.5">
        {items.map((it, idx) => {
          const active = route === it.key;
          return (
            <li key={it.key} className="relative">
              {active && (
                <span
                  aria-hidden="true"
                  className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-primary rounded-r"
                />
              )}
              <button
                ref={(el) => { buttonsRef.current[idx] = el; }}
                type="button"
                onClick={() => setRoute(it.key)}
                onKeyDown={onKeyDown(idx)}
                title={`${it.label} (${it.hot})`}
                aria-label={it.label}
                aria-current={active ? 'page' : undefined}
                className={`group w-full h-10 flex items-center justify-center relative transition-colors
                  ${active ? 'text-primary bg-primary-soft' : 'text-muted hover:text-ink hover:bg-subtle'}`}
              >
                {it.icon}
                {it.badge ? (
                  <BadgeSpan
                    badge={it.badge}
                    animateKey={it.key === 'queue' ? tickKey : matchTickKey}
                  />
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>

      {/* Sync dot */}
      <div className="h-12 flex flex-col items-center justify-center gap-1 border-t border-hair">
        <div
          title={syncOk ? 'Local hub reachable' : 'Local-only'}
          className={`w-1.5 h-1.5 rounded-full ${syncOk ? 'bg-green' : 'bg-amber'}`}
        />
        <div className="text-[9px] font-mono uppercase tracking-wider text-muted">v0.4</div>
      </div>
    </nav>
  );
}
