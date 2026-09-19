"use client";

import React, { useState, useEffect } from "react";
import { ThinkingOrb, type OrbState } from "@/components/ui/thinking-orbs";

export interface AgentOrbConfig {
  state: OrbState;
  label: string;
  detail: string;
}

/**
 * Dynamically resolves the agent's OrbState, label, and detail based on
 * the current prompt query, active tool, or execution phase.
 */
export function resolveAgentOrbConfig(
  prompt?: string,
  activeTool?: string,
  phase?: string
): AgentOrbConfig {
  const p = (prompt || "").toLowerCase();
  const tool = (activeTool || "").toLowerCase();
  const ph = (phase || "").toLowerCase();

  // Explicit phase overrides
  if (ph.includes("solve") || ph.includes("math") || ph.includes("calc")) {
    return {
      state: "solving",
      label: "Solving….",
      detail: "Evaluating mathematical operations & AST invariants",
    };
  }
  if (ph.includes("search") || ph.includes("grep") || ph.includes("find")) {
    return {
      state: "searching",
      label: "Searching….",
      detail: "Scanning workspace files and AST symbols",
    };
  }
  if (ph.includes("run") || ph.includes("test") || ph.includes("exec")) {
    return {
      state: "working",
      label: "Working….",
      detail: "Running sandbox execution & test suite",
    };
  }
  if (ph.includes("compose") || ph.includes("generate") || ph.includes("write")) {
    return {
      state: "composing",
      label: "Composing….",
      detail: "Synthesizing code architecture and logic",
    };
  }
  if (ph.includes("shape") || ph.includes("diff") || ph.includes("patch") || ph.includes("refactor")) {
    return {
      state: "shaping",
      label: "Shaping….",
      detail: "Structuring patch diffs and refactoring logic",
    };
  }
  if (ph.includes("connect") || ph.includes("socket") || ph.includes("network") || ph.includes("mcp")) {
    return {
      state: "connecting",
      label: "Connecting….",
      detail: "Validating loopback sockets and MCP boundary",
    };
  }

  // Active Tool Execution overrides
  if (tool.includes("python") || tool.includes("terminal") || tool.includes("bash") || tool.includes("unittest")) {
    return {
      state: "working",
      label: "Working….",
      detail: `Executing ${activeTool} in sandbox`,
    };
  }
  if (tool.includes("search") || tool.includes("grep") || tool.includes("ripgrep") || tool.includes("glob")) {
    return {
      state: "searching",
      label: "Searching….",
      detail: "Searching codebase patterns",
    };
  }
  if (tool.includes("diff") || tool.includes("patch") || tool.includes("edit") || tool.includes("replace")) {
    return {
      state: "shaping",
      label: "Shaping….",
      detail: "Applying patch diffs to workspace",
    };
  }
  if (tool.includes("mcp") || tool.includes("network") || tool.includes("daemon")) {
    return {
      state: "connecting",
      label: "Connecting….",
      detail: "Communicating over loopback interface",
    };
  }

  // Prompt semantic analysis
  // 1. Math / Calculation / Arithmetic
  if (
    p.includes("calc") ||
    p.includes("math") ||
    p.includes("reciprocal") ||
    p.includes("divide") ||
    p.includes("multiply") ||
    p.includes("subtract") ||
    p.includes("add") ||
    p.includes("formula") ||
    p.includes("equation") ||
    p.includes("arithmetic") ||
    p.includes("calculator.py") ||
    /(\d+\s*[\+\-\*\/\%]\s*\d+)/.test(p)
  ) {
    return {
      state: "solving",
      label: "Solving….",
      detail: "Evaluating mathematical operations & AST invariants",
    };
  }

  // 2. Search / Grep / Codebase discovery
  if (
    p.includes("search") ||
    p.includes("find") ||
    p.includes("grep") ||
    p.includes("locate") ||
    p.includes("where") ||
    p.includes("lookup") ||
    p.includes("explore") ||
    p.includes("list files")
  ) {
    return {
      state: "searching",
      label: "Searching….",
      detail: "Scanning workspace files and AST symbols",
    };
  }

  // 3. Testing / Running / Sandbox execution
  if (
    p.includes("test") ||
    p.includes("run") ||
    p.includes("execute") ||
    p.includes("eval") ||
    p.includes("sandbox") ||
    p.includes("benchmark") ||
    p.includes("ci")
  ) {
    return {
      state: "working",
      label: "Working….",
      detail: "Running sandbox execution & test suite",
    };
  }

  // 4. Code Generation / Creation / Scaffolding
  if (
    p.includes("create") ||
    p.includes("generate") ||
    p.includes("write") ||
    p.includes("build") ||
    p.includes("scaffold") ||
    p.includes("implement") ||
    p.includes("make a")
  ) {
    return {
      state: "composing",
      label: "Composing….",
      detail: "Synthesizing code architecture and logic",
    };
  }

  // 5. Code Patching / Refactoring / Editing
  if (
    p.includes("patch") ||
    p.includes("edit") ||
    p.includes("fix") ||
    p.includes("refactor") ||
    p.includes("guard") ||
    p.includes("audit") ||
    p.includes("clean") ||
    p.includes("modify")
  ) {
    return {
      state: "shaping",
      label: "Shaping….",
      detail: "Structuring patch diffs and refactoring logic",
    };
  }

  // 6. Network / MCP / Boundary / Socket
  if (
    p.includes("mcp") ||
    p.includes("socket") ||
    p.includes("network") ||
    p.includes("egress") ||
    p.includes("packet") ||
    p.includes("boundary") ||
    p.includes("port")
  ) {
    return {
      state: "connecting",
      label: "Connecting….",
      detail: "Validating loopback sockets and MCP boundary",
    };
  }

  // 7. Merging / Synthesizing complex multi-faceted logic
  if (
    p.includes("integrate") ||
    p.includes("combine") ||
    p.includes("merge") ||
    p.includes("weave") ||
    p.includes("reconcile")
  ) {
    return {
      state: "weaving",
      label: "Weaving….",
      detail: "Reconciling dependencies and AST branches",
    };
  }

  // 8. Default: General thinking / reasoning
  return {
    state: "breathing",
    label: "Thinking….",
    detail: "Reasoning over workspace context",
  };
}

interface DynamicThinkingPillProps {
  prompt?: string;
  activeTool?: string;
  phase?: string;
  forcedState?: OrbState;
  forcedLabel?: string;
  forcedDetail?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

/**
 * Dynamic Thinking Pill that adapts its state and animation
 * depending on what the agent is currently doing.
 */
export const DynamicThinkingPill: React.FC<DynamicThinkingPillProps> = ({
  prompt,
  activeTool,
  phase,
  forcedState,
  forcedLabel,
  forcedDetail,
  size = "lg",
  className = "",
}) => {
  const [currentConfig, setCurrentConfig] = useState<AgentOrbConfig>(() =>
    resolveAgentOrbConfig(prompt, activeTool, phase)
  );

  // Dynamically update as prompt, activeTool, or phase changes
  useEffect(() => {
    if (forcedState || forcedLabel || forcedDetail) {
      setCurrentConfig((prev) => ({
        state: forcedState || prev.state || "breathing",
        label: forcedLabel || prev.label || "Thinking….",
        detail: forcedDetail !== undefined ? forcedDetail : prev.detail,
      }));
      return;
    }
    const resolved = resolveAgentOrbConfig(prompt, activeTool, phase);
    setCurrentConfig(resolved);
  }, [prompt, activeTool, phase, forcedState, forcedLabel, forcedDetail]);

  // Optional dynamic progression during live execution:
  // If an operation takes a few seconds, simulate the agent's cognitive pipeline
  // (e.g. initial thinking -> specific action -> verifying)
  useEffect(() => {
    if (forcedState || !prompt) return;

    const initial = resolveAgentOrbConfig(prompt, activeTool, phase);
    setCurrentConfig(initial);

    // If starting in solving or searching or composing, keep it
    if (initial.state === "solving") {
      // stays solving for math
      return;
    }

    // For general prompts, after 1.8s if tools are being examined, move to shaping/working
    const timer = setTimeout(() => {
      const p = prompt.toLowerCase();
      if (p.includes("audit") || p.includes("fix")) {
        setCurrentConfig({
          state: "shaping",
          label: "Shaping….",
          detail: "Refactoring AST logic",
        });
      } else if (p.includes("test") || p.includes("run")) {
        setCurrentConfig({
          state: "working",
          label: "Working….",
          detail: "Executing test runner",
        });
      }
    }, 2200);

    return () => clearTimeout(timer);
  }, [prompt, activeTool, phase, forcedState]);

  const isSmall = size === "sm";
  const isMedium = size === "md";

  return (
    <div
      className={`inline-flex items-center rounded-full select-none shadow-2xl transition-all duration-300 animate-in fade-in zoom-in-95 ${
        isSmall
          ? "h-[46px] gap-2.5 pl-[7px] pr-5"
          : isMedium
          ? "h-[58px] gap-3 pl-[8px] pr-6"
          : "h-[74px] gap-3.5 pl-[9px] pr-8"
      } ${className}`}
      style={{
        background: "rgba(29, 29, 29, 0.55)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        boxShadow:
          "inset 0 0 0 1px rgba(44, 47, 54, 0.45), inset 0 0 50px 0 rgba(255, 255, 255, 0.012), 0 8px 32px rgba(0, 0, 0, 0.6)",
      }}
    >
      <span
        className={`flex items-center justify-center shrink-0 ${
          isSmall
            ? "[&_canvas]:!size-9"
            : isMedium
            ? "[&_canvas]:!size-11"
            : "[&_canvas]:!size-14"
        }`}
      >
        <ThinkingOrb
          key={currentConfig.state}
          state={currentConfig.state}
          size={64}
          theme="dark"
        />
      </span>

      <div className="flex flex-col justify-center">
        <div className="flex items-center gap-2">
          <span
            className={`whitespace-nowrap font-normal select-none transition-colors duration-200 ${
              isSmall
                ? "text-sm"
                : isMedium
                ? "text-base"
                : "text-lg leading-6"
            }`}
            style={{ color: "rgba(251, 251, 251, 0.72)" }}
          >
            {currentConfig.label}
          </span>
          {currentConfig.state === "solving" && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#76B900]/20 text-[#76B900] uppercase tracking-wider font-semibold">
              Math
            </span>
          )}
          {currentConfig.state === "searching" && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 uppercase tracking-wider font-semibold">
              Scan
            </span>
          )}
          {currentConfig.state === "working" && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 uppercase tracking-wider font-semibold">
              Exec
            </span>
          )}
          {currentConfig.state === "shaping" && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 uppercase tracking-wider font-semibold">
              Patch
            </span>
          )}
          {currentConfig.state === "composing" && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 uppercase tracking-wider font-semibold">
              Draft
            </span>
          )}
          {currentConfig.state === "connecting" && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 uppercase tracking-wider font-semibold">
              Socket
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
