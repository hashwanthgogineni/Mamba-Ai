// src/components/GenerationLoader.tsx
import { useEffect, useRef, useState } from "react";

const ESTIMATED_SECONDS = 3 * 60; // Godot builds land at roughly 2-4 minutes

const R_PROGRESS = 100;
const C_PROGRESS = 2 * Math.PI * R_PROGRESS;

interface GenerationLoaderProps {
  /** Live status text from the backend, e.g. "AI is building your complete HTML5 game..." */
  status?: string;
}

function formatClock(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function GenerationLoader({ status }: GenerationLoaderProps) {
  const [elapsed, setElapsed] = useState(0);

  const startedAt = useRef<number>(Date.now());

  // Elapsed clock, driven from a timestamp so a throttled background tab
  // doesn't drift behind real time.
  useEffect(() => {
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.current) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, []);


  // Cap the ring short of full so it never reads as "done" while still running.
  const progress = Math.min(elapsed / ESTIMATED_SECONDS, 0.97);
  const dashOffset = C_PROGRESS * (1 - progress);

  const overrun = elapsed > ESTIMATED_SECONDS;
  const remaining = Math.max(ESTIMATED_SECONDS - elapsed, 0);

  return (
    <div className="flex flex-col items-center justify-center h-full w-full px-8 py-10 gap-10">
      {/* ---------- Circular drawing animation ---------- */}
      <div className="relative flex items-center justify-center">
        <svg
          width="240"
          height="240"
          viewBox="0 0 220 220"
          className="gl-svg"
          role="img"
          aria-label={`Generating your game, ${formatClock(elapsed)} elapsed`}
        >
          {/* One quiet track. */}
          <circle cx="110" cy="110" r="92" fill="none" stroke="#1A1A1A" strokeWidth="1" />

          {/* Elapsed progress — a single thin arc, nothing else. */}
          <circle
            cx="110"
            cy="110"
            r="92"
            fill="none"
            stroke="#25D366"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray={C_PROGRESS}
            strokeDashoffset={dashOffset}
            transform="rotate(-90 110 110)"
            style={{ transition: "stroke-dashoffset 1s linear" }}
          />

          {/* The moving object: one dot orbiting continuously, with a short
              comet tail so motion reads even when progress barely changes. */}
          <g className="gl-orbit">
            <circle cx="110" cy="18" r="14" fill="#25D366" opacity="0.10" />
            <circle cx="110" cy="18" r="3.5" fill="#25D366" />
          </g>
        </svg>
        {/* Centre readout */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span
            className="text-[#25D366] text-4xl font-semibold tabular-nums tracking-tight"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatClock(elapsed)}
          </span>
          <span className="text-gray-200 text-[12px] font-semibold uppercase tracking-[0.18em] mt-1">
            {overrun ? "almost there" : `of ~${formatClock(ESTIMATED_SECONDS)}`}
          </span>
        </div>
      </div>

      {/* ---------- Status ---------- */}
      <div className="flex flex-col items-center text-center gap-1.5">
        <p className="text-white text-xl font-bold">
          {status || "Cooking your Game..."}
        </p>
        <p className="text-gray-200 text-sm font-medium">
          {overrun
            ? "Taking a little longer than usual — hang tight."
            : `Usually takes 2-4 minutes · ~${formatClock(remaining)} left`}
        </p>
      </div>

      <style>{`
        @keyframes gl-orbit { to { transform: rotate(360deg); } }
        .gl-orbit {
          transform-box: view-box;
          transform-origin: 110px 110px;
          animation: gl-orbit 3.2s linear infinite;
        }
        .gl-svg { overflow: visible; }

        @media (prefers-reduced-motion: reduce) {
          .gl-orbit { animation: none; }
        }
      `}</style>
    </div>
  );
}
