"use client";

import { ThinkingOrb } from "@/components/ui/thinking-orbs";

// Solving — a single status pill, exactly as on the original site.
export default function ThinkingOrbSolvingDemo() {
  return (
    <div className="flex min-h-[360px] w-full items-center justify-center bg-[#070707] p-8">
      <div
        className="inline-flex h-[74px] items-center gap-3 rounded-full pl-[9px] pr-8"
        style={{
          background: "rgba(29,29,29,0.42)",
          boxShadow:
            "inset 0 0 0 1px rgba(44,47,54,0.31), inset 0 0 50px 0 rgba(255,255,255,0.012)",
        }}
      >
        <span className="[&_canvas]:!size-14">
          <ThinkingOrb state="solving" size={64} theme="dark" />
        </span>
        <span
          className="whitespace-nowrap text-lg leading-6"
          style={{ color: "rgba(251,251,251,0.5)" }}
        >
          Solving….
        </span>
      </div>
    </div>
  );
}

export function MathThinkingPill({
  text = "Solving….",
  size = "md",
}: {
  text?: string;
  size?: "sm" | "md" | "lg";
}) {
  const isSm = size === "sm";
  return (
    <div
      className={`inline-flex items-center rounded-full select-none transition-all ${
        isSm
          ? "h-[42px] gap-2 pl-[6px] pr-4"
          : "h-[56px] gap-3 pl-[8px] pr-6"
      }`}
      style={{
        background: "rgba(24, 24, 27, 0.72)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        boxShadow:
          "inset 0 0 0 1px rgba(255, 255, 255, 0.1), 0 4px 20px -2px rgba(0, 0, 0, 0.5)",
      }}
    >
      <span className={isSm ? "[&_canvas]:!size-8" : "[&_canvas]:!size-11"}>
        <ThinkingOrb state="solving" size={64} theme="dark" />
      </span>
      <span
        className={`whitespace-nowrap font-medium tracking-wide ${
          isSm ? "text-xs" : "text-sm"
        }`}
        style={{ color: "rgba(251, 251, 251, 0.85)" }}
      >
        {text}
      </span>
    </div>
  );
}
