"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type BorderBeamSize = "sm" | "md" | "lg" | "xl" | number;
export type BorderBeamTheme = "default" | "neon" | "sunset" | "ocean" | "matrix" | "cyberpunk" | "sanctum" | "antigravity" | "iridescent";
export type BorderBeamColorVariant = "default" | "primary" | "secondary" | "accent" | "rainbow" | "sanctum" | "antigravity" | "iridescent";

export interface BorderBeamProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
  size?: BorderBeamSize;
  duration?: number;
  borderWidth?: number;
  anchor?: number;
  colorFrom?: string;
  colorTo?: string;
  delay?: number;
  theme?: BorderBeamTheme;
  colorVariant?: BorderBeamColorVariant;
  reverse?: boolean;
}

const THEME_COLORS: Record<BorderBeamTheme, { from: string; to: string }> = {
  default: { from: "#ffaa40", to: "#9c40ff" },
  neon: { from: "#00f0ff", to: "#ff0077" },
  sunset: { from: "#ff4b4b", to: "#ffb800" },
  ocean: { from: "#00c6ff", to: "#0072ff" },
  matrix: { from: "#00ff87", to: "#60efff" },
  cyberpunk: { from: "#f72585", to: "#7209b7" },
  sanctum: { from: "#76B900", to: "#86e810" },
  antigravity: { from: "#00f0ff", to: "#ff2e83" },
  iridescent: { from: "#00f0ff", to: "#ff2e83" },
};

const VARIANT_COLORS: Record<BorderBeamColorVariant, { from: string; to: string }> = {
  default: { from: "var(--color-primary, #6366f1)", to: "var(--color-accent, #a855f7)" },
  primary: { from: "#3b82f6", to: "#8b5cf6" },
  secondary: { from: "#10b981", to: "#06b6d4" },
  accent: { from: "#f59e0b", to: "#ef4444" },
  rainbow: { from: "#ff0080", to: "#7928ca" },
  sanctum: { from: "#76B900", to: "#86e810" },
  antigravity: { from: "#00f0ff", to: "#ff2e83" },
  iridescent: { from: "#00f0ff", to: "#ff2e83" },
};

export const BorderBeam = React.forwardRef<HTMLDivElement, BorderBeamProps>(
  (
    {
      className,
      size = "md",
      duration = 15,
      borderWidth = 1.5,
      anchor = 90,
      colorFrom,
      colorTo,
      delay = 0,
      theme,
      colorVariant,
      reverse = false,
      style,
      ...props
    },
    ref
  ) => {
    let resolvedSize: number;
    if (typeof size === "number") {
      resolvedSize = size;
    } else {
      switch (size) {
        case "sm":
          resolvedSize = 100;
          break;
        case "lg":
          resolvedSize = 300;
          break;
        case "xl":
          resolvedSize = 400;
          break;
        case "md":
        default:
          resolvedSize = 200;
          break;
      }
    }

    let activeFrom = colorFrom;
    let activeTo = colorTo;

    if (!activeFrom && !activeTo) {
      if (theme && THEME_COLORS[theme]) {
        activeFrom = THEME_COLORS[theme].from;
        activeTo = THEME_COLORS[theme].to;
      } else if (colorVariant && VARIANT_COLORS[colorVariant]) {
        activeFrom = VARIANT_COLORS[colorVariant].from;
        activeTo = VARIANT_COLORS[colorVariant].to;
      } else {
        activeFrom = "#ffaa40";
        activeTo = "#9c40ff";
      }
    }

    return (
      <div
        ref={ref}
        style={
          {
            "--size": `${resolvedSize}`,
            "--duration": `${duration}`,
            "--anchor": `${anchor}`,
            "--border-width": `${borderWidth}`,
            "--color-from": activeFrom || "#ffaa40",
            "--color-to": activeTo || "#9c40ff",
            "--delay": `-${delay}s`,
            "--direction": reverse ? "reverse" : "normal",
            ...style,
          } as React.CSSProperties
        }
        className={cn(
          "pointer-events-none absolute inset-0 rounded-[inherit] [border:calc(var(--border-width)*1px)_solid_transparent]",
          "![mask-clip:padding-box,border-box] ![mask-composite:intersect] [mask:linear-gradient(transparent,transparent),linear-gradient(white,white)]",
          "after:absolute after:aspect-square after:w-[calc(var(--size)*1px)] after:animate-border-beam after:[animation-delay:var(--delay)] after:[animation-direction:var(--direction)] after:[animation-duration:calc(var(--duration)*1s)] after:[background:linear-gradient(to_left,var(--color-from),var(--color-to),transparent)] after:[offset-anchor:calc(var(--anchor)*1%)_50%] after:[offset-path:rect(0_auto_auto_0_round_inherit)]",
          className
        )}
        {...props}
      >
        <style>{`
          @keyframes border-beam {
            to {
              offset-distance: 100%;
            }
          }
          .animate-border-beam {
            animation: border-beam calc(var(--duration) * 1s) infinite linear;
          }
        `}</style>
      </div>
    );
  }
);

BorderBeam.displayName = "BorderBeam";
export default BorderBeam;
