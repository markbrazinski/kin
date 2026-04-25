/* Waveform — animated bar visualizer with 4 states (idle/recording/processing/playback). */
import { useMemo } from 'react';

export type WaveformState = 'idle' | 'recording' | 'processing' | 'playback';

export type WaveformProps = {
  state?: WaveformState;
  bars?: number;
};

const Waveform = ({ state = "idle", bars = 32 }: WaveformProps) => {
  // deterministic heights so SSR-friendly
  const heights = useMemo<number[]>(() => {
    const out: number[] = [];
    for (let i = 0; i < bars; i++) {
      // quasi-random but stable
      const v = 0.3 + 0.7 * Math.abs(Math.sin(i * 1.37 + 2.1));
      out.push(v);
    }
    return out;
  }, [bars]);

  const active = state === "recording" || state === "playback";
  const color =
    state === "recording" ? "bg-red"
    : state === "playback" ? "bg-primary"
    : state === "processing" ? "bg-muted"
    : "bg-line";

  return (
    <div className="flex items-center gap-[3px] h-10">
      {heights.map((h, i) => (
        <div
          key={i}
          className={`w-[3px] rounded-sm ${color} ${active ? "kin-wave-bar" : ""}`}
          style={{
            height: `${Math.round(h * 32) + 6}px`,
            animationDelay: active ? `${(i % 8) * 70}ms` : undefined,
            opacity: state === "idle" ? 0.55 : 1,
          }}
        />
      ))}
    </div>
  );
};

export { Waveform };
