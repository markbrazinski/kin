/* ============================================================================
 * KIN — presentation-mode.jsx
 * ----------------------------------------------------------------------------
 * ADAPTATION NOTES FOR CC:
 *   • DO NOT CHANGE: scope. This file is INTENTIONALLY thin. It is NOT a
 *     UI scripter, NOT a step-runner, NOT an animation controller. It does
 *     three things only — keep it that way:
 *       1. Hide dev surfaces (DemoDock and any data-dev="true" elements)
 *       2. Seed required demo data (Mohammed snapshot pre-loaded so the
 *          Beat 6 transliteration match has something to match against)
 *       3. Optional presenter HUD below the 1080p safe-area
 *   • Activated by ⌘⇧P or ?present=1 query param. Both should produce
 *     identical state — the URL param exists so a presenter can deep-link
 *     into a clean state from a fresh tab.
 *   • Coach-mark is auto-dismissed when presentation activates (the
 *     coach-mark file reads the same localStorage key — set it).
 *   • DO NOT add demo-step automation here. The whole point of this build
 *     is that the demo runs from REAL state transitions driven by REAL
 *     (or simulated) audio + LLM responses, not a scripted UI tour. If you
 *     find yourself adding setTimeouts to advance the UI, stop — that work
 *     belongs in your audio/LLM mock layer, not here.
 *   • Presenter HUD is OPTIONAL and lives below y=1080. Safe to omit
 *     entirely if your demo monitor crops to 1920×1080.
 *   • Exit: Esc or ⌘⇧P toggle. Restore DemoDock visibility on exit.
 * ============================================================================
 * Presentation-mode driver — ⌘⇧P only. NOT a UI scripter.
   Responsibilities (only):
     1. Hide dev surfaces (DemoDock, debug affordances)
     2. Seed required data (Mohammed snapshot pre-loaded into queue for Beat 6 match-fire)
     3. Optional presenter HUD (below the 1080p safe-area crop)
   Does NOT advance UI, does NOT script events. Real audio drives real pipeline. */

const PRESENTATION_INITIAL_QUEUE_IDS = [89]; // Mohammed pre-seed for Beat 6

function usePresentationMode() {
  const [active, setActive] = React.useState(false);
  const [hudHidden, setHudHidden] = React.useState(false);

  React.useEffect(() => {
    const onKey = (e) => {
      const isMac = /Mac/.test(navigator.platform);
      const mod = isMac ? e.metaKey : e.ctrlKey;
      if (mod && e.shiftKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault();
        setActive(v => !v);
      }
      if (active && (e.key === "h" || e.key === "H")) {
        // Only intercept H if no input is focused
        const tag = document.activeElement?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") setHudHidden(v => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  return { active, setActive, hudHidden, setHudHidden };
}

function PresenterHUD({ active, hidden, setHidden, pipelineState, onReset }) {
  if (!active || hidden) return null;
  return (
    <div className="fixed bottom-0 inset-x-0 z-40 h-6 bg-ink text-white/85 flex items-center px-3 text-[11px] font-mono gap-3 select-none">
      <span className="text-white font-semibold tracking-wide">PRESENTATION</span>
      <span className="text-white/60">dev surfaces hidden · queue seeded</span>
      <span className="ml-3 inline-flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${
          pipelineState === "busy" ? "bg-primary" :
          pipelineState === "down" ? "bg-amber" : "bg-green"
        } ${pipelineState !== "down" ? "animate-pulse" : ""}`} />
        pipeline {pipelineState}
      </span>
      <div className="flex-1" />
      <button onClick={onReset} className="px-2 py-0.5 rounded border border-white/20 hover:bg-white/10">reset</button>
      <button onClick={() => setHidden(true)} className="px-2 py-0.5 rounded border border-white/20 hover:bg-white/10" title="Hide HUD (H)">hide</button>
    </div>
  );
}

Object.assign(window, { usePresentationMode, PresenterHUD, PRESENTATION_INITIAL_QUEUE_IDS });
