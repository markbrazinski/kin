/* Presenter HUD — fixed strip at bottom-0, below the 1080p safe-area crop.
   Visible only when presentation mode is active and not hidden by H key.
   Prototype: design_reference/round-2/presentation-mode.jsx */

type PipelineState = 'busy' | 'ready' | 'down';

export type PresenterHUDProps = {
  active: boolean;
  hidden: boolean;
  setHidden: (hidden: boolean) => void;
  pipelineState: PipelineState;
  onReset: () => void;
};

export function PresenterHUD({ active, hidden, setHidden, pipelineState, onReset }: PresenterHUDProps) {
  if (!active || hidden) return null;

  const dotColor =
    pipelineState === 'busy' ? 'bg-primary' :
    pipelineState === 'down' ? 'bg-amber' : 'bg-green';

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 h-6 bg-ink text-white/85 flex items-center px-3 text-[11px] font-mono gap-3 select-none">
      <span className="text-white font-semibold tracking-wide">PRESENTATION</span>
      <span className="text-white/60">dev surfaces hidden · queue seeded</span>
      <span className="ml-3 inline-flex items-center gap-1.5">
        {/* motion-safe: animate-pulse respects prefers-reduced-motion */}
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor} motion-safe:animate-pulse`} />
        pipeline {pipelineState}
      </span>
      <div className="flex-1" />
      <button
        onClick={onReset}
        className="px-2 py-0.5 rounded border border-white/20 hover:bg-white/10"
      >
        reset
      </button>
      <button
        onClick={() => setHidden(true)}
        className="px-2 py-0.5 rounded border border-white/20 hover:bg-white/10"
        title="Hide HUD (H)"
      >
        hide
      </button>
    </div>
  );
}
