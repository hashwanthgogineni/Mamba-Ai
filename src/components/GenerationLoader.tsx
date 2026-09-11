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
          width="320"
          height="320"
          viewBox="0 0 220 220"
          className="gl-svg"
          role="img"
          aria-label={`Generating your game, ${formatClock(elapsed)} elapsed`}
        >
          <defs>
            <linearGradient id="glArc" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#25D366" />
              <stop offset="100%" stopColor="#0E8C56" />
            </linearGradient>
          </defs>

          {/* Track for the progress ring */}
          <circle
            cx="110"
            cy="110"
            r={R_PROGRESS}
            fill="none"
            stroke="#1C2620"
            strokeWidth="2"
          />

          {/* Elapsed-time progress ring */}
          <circle
            cx="110"
            cy="110"
            r={R_PROGRESS}
            fill="none"
            stroke="url(#glArc)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={C_PROGRESS}
            strokeDashoffset={dashOffset}
            transform="rotate(-90 110 110)"
            style={{ transition: "stroke-dashoffset 1s linear" }}
          />

          {/* Outer sweep — long dashes, slow clockwise */}
          <g className="gl-spin-cw-slow">
            <circle
              cx="110"
              cy="110"
              r="86"
              fill="none"
              stroke="#25D366"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeDasharray="60 400"
              opacity="0.75"
            />
            <circle
              cx="110"
              cy="110"
              r="86"
              fill="none"
              stroke="#25D366"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeDasharray="18 122"
              strokeDashoffset="140"
              opacity="0.3"
            />
          </g>

          {/* Mid ring — counter-clockwise, faster */}
          <g className="gl-spin-ccw">
            <circle
              cx="110"
              cy="110"
              r="66"
              fill="none"
              stroke="#25D366"
              strokeWidth="1"
              strokeDasharray="4 14"
              opacity="0.45"
            />
          </g>

          {/* Inner ring — draws itself, erases, repeats */}
          <circle
            className="gl-draw"
            cx="110"
            cy="110"
            r="46"
            fill="none"
            stroke="#25D366"
            strokeWidth="2"
            strokeLinecap="round"
            transform="rotate(-90 110 110)"
          />

          {/* Orbiting node riding the progress arc */}
          <g
            style={{
              transformBox: "view-box",
              transformOrigin: "110px 110px",
              transform: `rotate(${progress * 360 - 90}deg)`,
              transition: "transform 1s linear",
            }}
          >
            <circle cx={110 + R_PROGRESS} cy="110" r="4" fill="#25D366" />
            <circle cx={110 + R_PROGRESS} cy="110" r="9" fill="#25D366" opacity="0.18" />
          </g>

          {/* Crosshair ticks — quiet structure, not decoration */}
          <g stroke="#25D366" strokeWidth="1" opacity="0.35">
            <line x1="110" y1="4" x2="110" y2="14" />
            <line x1="110" y1="206" x2="110" y2="216" />
            <line x1="4" y1="110" x2="14" y2="110" />
            <line x1="206" y1="110" x2="216" y2="110" />
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
        @keyframes gl-spin-cw  { to { transform: rotate(360deg); } }
        @keyframes gl-spin-ccw { to { transform: rotate(-360deg); } }
        @keyframes gl-draw {
          0%   { stroke-dasharray: 0 289;   stroke-dashoffset: 0; }
          45%  { stroke-dasharray: 289 289; stroke-dashoffset: 0; }
          55%  { stroke-dasharray: 289 289; stroke-dashoffset: 0; }
          100% { stroke-dasharray: 289 289; stroke-dashoffset: -289; }
        }
        .gl-spin-cw-slow,
        .gl-spin-ccw {
          transform-box: view-box;
          transform-origin: 110px 110px;
        }
        .gl-spin-cw-slow { animation: gl-spin-cw 14s linear infinite; }
        .gl-spin-ccw     { animation: gl-spin-ccw 8s linear infinite; }
        .gl-draw         { animation: gl-draw 4s ease-in-out infinite; }
        .gl-svg          { overflow: visible; }

        @media (prefers-reduced-motion: reduce) {
          .gl-spin-cw-slow,
          .gl-spin-ccw,
          .gl-draw { animation: none; }
          .gl-draw { stroke-dasharray: 289 289; stroke-dashoffset: 72; }
        }
      `}</style>
    </div>
  );
}
