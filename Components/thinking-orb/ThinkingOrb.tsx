"use client";

import * as React from "react";
import type { ThinkingOrbProps, ThinkingOrbState } from "./types";

/* ─────────────────────────────────────────────────────────
 * STATE PALETTES & THEMES
 * ───────────────────────────────────────────────────────── */
interface StateVisual {
  primary: string;
  secondary: string;
  glow: string;
  accent: string;
  animationClass: string;
}

const PALETTES_DARK: Record<ThinkingOrbState, StateVisual> = {
  working: {
    primary: "#6366f1",
    secondary: "#8b5cf6",
    glow: "rgba(99, 102, 241, 0.45)",
    accent: "#c084fc",
    animationClass: "orb-anim-working",
  },
  searching: {
    primary: "#0ea5e9",
    secondary: "#06b6d4",
    glow: "rgba(14, 165, 233, 0.5)",
    accent: "#38bdf8",
    animationClass: "orb-anim-searching",
  },
  solving: {
    primary: "#10b981",
    secondary: "#059669",
    glow: "rgba(16, 185, 129, 0.45)",
    accent: "#34d399",
    animationClass: "orb-anim-solving",
  },
  listening: {
    primary: "#ec4899",
    secondary: "#f43f5e",
    glow: "rgba(236, 72, 153, 0.5)",
    accent: "#fb7185",
    animationClass: "orb-anim-listening",
  },
  connecting: {
    primary: "#8b5cf6",
    secondary: "#3b82f6",
    glow: "rgba(139, 92, 246, 0.5)",
    accent: "#60a5fa",
    animationClass: "orb-anim-connecting",
  },
  weaving: {
    primary: "#f59e0b",
    secondary: "#d97706",
    glow: "rgba(245, 158, 11, 0.45)",
    accent: "#fbbf24",
    animationClass: "orb-anim-weaving",
  },
  composing: {
    primary: "#a855f7",
    secondary: "#ec4899",
    glow: "rgba(168, 85, 247, 0.5)",
    accent: "#f472b6",
    animationClass: "orb-anim-composing",
  },
  breathing: {
    primary: "#14b8a6",
    secondary: "#0d9488",
    glow: "rgba(20, 184, 166, 0.45)",
    accent: "#2dd4bf",
    animationClass: "orb-anim-breathing",
  },
  shaping: {
    primary: "#f43f5e",
    secondary: "#e11d48",
    glow: "rgba(244, 63, 94, 0.5)",
    accent: "#fda4af",
    animationClass: "orb-anim-shaping",
  },
};

const PALETTES_LIGHT: Record<ThinkingOrbState, StateVisual> = {
  working: {
    primary: "#4f46e5",
    secondary: "#7c3aed",
    glow: "rgba(79, 70, 229, 0.25)",
    accent: "#9333ea",
    animationClass: "orb-anim-working",
  },
  searching: {
    primary: "#0284c7",
    secondary: "#0891b2",
    glow: "rgba(2, 132, 199, 0.25)",
    accent: "#0ea5e9",
    animationClass: "orb-anim-searching",
  },
  solving: {
    primary: "#059669",
    secondary: "#047857",
    glow: "rgba(5, 150, 105, 0.25)",
    accent: "#10b981",
    animationClass: "orb-anim-solving",
  },
  listening: {
    primary: "#db2777",
    secondary: "#e11d48",
    glow: "rgba(219, 39, 119, 0.25)",
    accent: "#f43f5e",
    animationClass: "orb-anim-listening",
  },
  connecting: {
    primary: "#7c3aed",
    secondary: "#2563eb",
    glow: "rgba(124, 58, 237, 0.25)",
    accent: "#3b82f6",
    animationClass: "orb-anim-connecting",
  },
  weaving: {
    primary: "#d97706",
    secondary: "#b45309",
    glow: "rgba(217, 119, 6, 0.25)",
    accent: "#f59e0b",
    animationClass: "orb-anim-weaving",
  },
  composing: {
    primary: "#9333ea",
    secondary: "#db2777",
    glow: "rgba(147, 51, 234, 0.25)",
    accent: "#ec4899",
    animationClass: "orb-anim-composing",
  },
  breathing: {
    primary: "#0d9488",
    secondary: "#0f766e",
    glow: "rgba(13, 148, 136, 0.25)",
    accent: "#14b8a6",
    animationClass: "orb-anim-breathing",
  },
  shaping: {
    primary: "#e11d48",
    secondary: "#be123c",
    glow: "rgba(225, 29, 72, 0.25)",
    accent: "#f43f5e",
    animationClass: "orb-anim-shaping",
  },
};

export const ThinkingOrb = React.forwardRef<HTMLDivElement, ThinkingOrbProps>(
  (
    {
      state = "working",
      size = 64,
      speed = 1,
      dark = true,
      paused = false,
      className,
      style,
      ...props
    },
    ref
  ) => {
    const palette = (dark ? PALETTES_DARK : PALETTES_LIGHT)[state] || PALETTES_DARK.working;
    const isInline = size <= 28;
    const duration = Math.max(0.1, 4 / (speed || 1));

    return (
      <div
        ref={ref}
        role="status"
        aria-label={`Thinking orb: ${state}`}
        style={
          {
            width: `${size}px`,
            height: `${size}px`,
            minWidth: `${size}px`,
            minHeight: `${size}px`,
            "--orb-primary": palette.primary,
            "--orb-secondary": palette.secondary,
            "--orb-accent": palette.accent,
            "--orb-glow": palette.glow,
            "--orb-duration": `${duration}s`,
            "--orb-play-state": paused ? "paused" : "running",
            ...style,
          } as React.CSSProperties
        }
        className={`relative inline-flex items-center justify-center shrink-0 select-none overflow-visible ${className || ""}`}
        {...props}
      >
        <style>{`
          @keyframes orb-pulse {
            0%, 100% { transform: scale(0.92); opacity: 0.8; }
            50% { transform: scale(1.08); opacity: 1; }
          }
          @keyframes orb-spin-slow {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          @keyframes orb-spin-reverse {
            0% { transform: rotate(360deg); }
            100% { transform: rotate(0deg); }
          }
          @keyframes orb-ripple {
            0% { transform: scale(0.7); opacity: 0.9; }
            50% { transform: scale(1.15); opacity: 0.4; }
            100% { transform: scale(1.3); opacity: 0; }
          }
          @keyframes orb-wave {
            0%, 100% { border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%; transform: rotate(0deg) scale(0.95); }
            33% { border-radius: 70% 30% 46% 54% / 30% 29% 71% 70%; transform: rotate(120deg) scale(1.05); }
            66% { border-radius: 100% 60% 60% 100% / 100% 100% 60% 60%; transform: rotate(240deg) scale(0.98); }
          }
          @keyframes orb-breathe {
            0%, 100% { transform: scale(0.88); filter: blur(2px); }
            50% { transform: scale(1.12); filter: blur(0.5px); }
          }
          @keyframes orb-connect {
            0%, 100% { transform: scale(1) rotate(0deg); }
            25% { transform: scale(1.06, 0.94) rotate(45deg); }
            50% { transform: scale(0.95, 1.05) rotate(90deg); }
            75% { transform: scale(1.04, 0.96) rotate(135deg); }
          }

          .orb-core-anim {
            animation-duration: var(--orb-duration);
            animation-play-state: var(--orb-play-state);
            animation-iteration-count: infinite;
            animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
          }
        `}</style>

        {/* Ambient Outer Glow */}
        <div
          className="absolute inset-[-20%] rounded-full pointer-events-none transition-all duration-500 blur-md"
          style={{
            background: `radial-gradient(circle, var(--orb-glow) 0%, transparent 70%)`,
            animation: paused ? "none" : "orb-pulse calc(var(--orb-duration) * 1.5) infinite ease-in-out",
            animationPlayState: paused ? "paused" : "running",
            opacity: isInline ? 0.7 : 0.9,
          }}
          aria-hidden="true"
        />

        {/* Outer Orbital / Ripple Rings (Active in searching/solving/connecting) */}
        {(state === "searching" || state === "connecting" || state === "weaving") && !isInline && (
          <div
            className="absolute inset-[-10%] rounded-full border border-current pointer-events-none opacity-40"
            style={{
              borderColor: "var(--orb-accent)",
              animation: paused ? "none" : "orb-ripple calc(var(--orb-duration) * 1.2) infinite linear",
              animationPlayState: paused ? "paused" : "running",
            }}
            aria-hidden="true"
          />
        )}

        {/* Morphing Fluid Shell for organic states */}
        {(state === "shaping" || state === "weaving" || state === "composing") ? (
          <div
            className="absolute inset-0 rounded-full orb-core-anim transition-all duration-300"
            style={{
              background: `linear-gradient(135deg, var(--orb-primary), var(--orb-secondary), var(--orb-accent))`,
              animationName: "orb-wave",
              animationDuration: "calc(var(--orb-duration) * 2)",
              boxShadow: `0 0 ${size / 4}px var(--orb-glow)`,
            }}
            aria-hidden="true"
          />
        ) : (
          /* High-Fidelity Layered Spherical Orb */
          <div
            className="relative w-full h-full rounded-full overflow-hidden transition-all duration-300 orb-core-anim"
            style={{
              background: `radial-gradient(circle at 35% 30%, var(--orb-accent) 0%, var(--orb-primary) 50%, var(--orb-secondary) 100%)`,
              boxShadow: `inset 0 -${size / 8}px ${size / 4}px rgba(0,0,0,0.35), 0 0 ${size / 3}px var(--orb-glow)`,
              animationName:
                state === "breathing"
                  ? "orb-breathe"
                  : state === "listening"
                  ? "orb-pulse"
                  : state === "connecting"
                  ? "orb-connect"
                  : "orb-pulse",
            }}
            aria-hidden="true"
          >
            {/* Dynamic Swirling Chromatic Filament */}
            <div
              className="absolute inset-0 rounded-full opacity-60 mix-blend-overlay pointer-events-none"
              style={{
                background: `conic-gradient(from 0deg, var(--orb-accent), transparent 60%, var(--orb-secondary), transparent)`,
                animation: paused ? "none" : "orb-spin-slow var(--orb-duration) infinite linear",
                animationPlayState: paused ? "paused" : "running",
              }}
            />

            {/* Specular Highlight */}
            <div
              className="absolute top-[12%] left-[18%] rounded-full bg-white/75 blur-[0.6px] pointer-events-none"
              style={{
                width: `${Math.max(3, size * 0.22)}px`,
                height: `${Math.max(2, size * 0.14)}px`,
                transform: "rotate(-30deg)",
              }}
            />
          </div>
        )}
      </div>
    );
  }
);

ThinkingOrb.displayName = "ThinkingOrb";
export default ThinkingOrb;
