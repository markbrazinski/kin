/* Persistent 44px icon rail. Two routes: intake (capture) + queue (review).
   Active state = bg-primary-soft + 2px primary left accent. Settings/Help
   intentionally omitted — rail is bimodal capture-vs-review per design ref
   nav-rail.jsx. */
import React, { useRef, useCallback } from 'react';
import { IconMic, IconList } from './icons';

export type RailRoute = 'intake' | 'queue';

export type RailNavProps = {
  route: RailRoute;
  setRoute: (route: RailRoute) => void;
  queuedCount?: number;
  syncOk?: boolean;
};

type RailItem = {
  key: RailRoute;
  label: string;
  icon: React.ReactNode;
  hot: string;
  badge?: number;
};

export function RailNav({ route, setRoute, queuedCount, syncOk = true }: RailNavProps) {
  const items: RailItem[] = [
    { key: 'intake', label: 'Intake', icon: <IconMic size={18} />, hot: '⌘1' },
    { key: 'queue',  label: 'Queue',  icon: <IconList size={18} />, hot: '⌘2', badge: queuedCount },
  ];

  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);

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
                  <span className="absolute top-1.5 right-1.5 min-w-[14px] h-[14px] px-1 rounded-full bg-primary text-white text-[9px] font-semibold flex items-center justify-center leading-none">
                    {it.badge > 9 ? '9+' : it.badge}
                  </span>
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
