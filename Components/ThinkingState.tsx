"use client";

import * as React from "react";
import { cn } from "../lib/utils";
import {
  ChevronDown,
  Search,
  Terminal,
  Check,
  Globe,
  ExternalLink,
  FileCode2,
  FileText,
  Command,
  Database,
  AlertCircle,
  Cpu,
} from "lucide-react";
import { PixelDotsLoader } from "./PixelDotsLoader";
import { NestedReasoningBlock } from "./NestedReasoningBlock";
import { TerminalCommand } from "./TerminalCommand";
import { FileDiff } from "./FileDiff";
import type {
  TraceNode,
  ToolDefinition,
  ThinkingStateProps,
} from "./types";

/* ─────────────────────────────────────────────────────────
 * SAFE DYNAMIC ICON RENDERER
 * ───────────────────────────────────────────────────────── */
function renderDynamicIcon(icon: any, className?: string): React.ReactNode {
  if (!icon) return null;
  if (React.isValidElement(icon)) return icon;
  if (typeof icon === "function" || typeof icon === "object") {
    return React.createElement(icon, {
      className: cn("size-3.5 shrink-0", className),
      "aria-hidden": "true",
    });
  }
  return null;
}

/* ─────────────────────────────────────────────────────────
 * DEFAULT TOOL REGISTRY
 * ───────────────────────────────────────────────────────── */
export const DEFAULT_TOOL_REGISTRY: Record<string, ToolDefinition> = {
  read_file: {
    name: "read_file",
    label: "Read",
    icon: FileText,
    iconClassName: "text-muted-foreground/80",
    monoChip: true,
  },
  edit_file: {
    name: "edit_file",
    label: "Edit",
    icon: FileCode2,
    iconClassName: "text-amber-500",
    monoChip: true,
  },
  execute_command: {
    name: "execute_command",
    label: "Run",
    icon: Terminal,
    iconClassName: "text-violet-500",
    monoChip: true,
  },
  search_web: {
    name: "search_web",
    label: "Search",
    icon: Search,
    iconClassName: "text-blue-500",
  },
  query_database: {
    name: "query_database",
    label: "SQL Query",
    icon: Database,
    iconClassName: "text-emerald-500",
    monoChip: true,
  },
};

/* ─────────────────────────────────────────────────────────
 * UNIVERSAL EXTENSIBLE PILL ROW ITEM
 * ───────────────────────────────────────────────────────── */
interface TracePillRowProps {
  node: TraceNode;
  isActive: boolean;
  isFinished: boolean;
  toolRegistry?: Record<string, ToolDefinition>;
}

export function TracePillRow({
  node,
  isActive,
  isFinished,
  toolRegistry = DEFAULT_TOOL_REGISTRY,
}: TracePillRowProps) {
  const [open, setOpen] = React.useState(false);

  const toolDef = node.toolName ? toolRegistry[node.toolName] : undefined;

  const isCommandNode = Boolean(
    node.command || node.type === "terminal" || node.type === "command"
  );

  const hasDetails = Boolean(
    isCommandNode ||
      node.renderContent ||
      toolDef?.renderCustomContent ||
      node.diffRows ||
      node.codeSnippet ||
      (node.details && node.details.length > 0) ||
      (node.sources && node.sources.length > 0) ||
      node.args ||
      node.result
  );

  const primaryText =
    node.primary ||
    (isCommandNode ? "Run" : undefined) ||
    (typeof toolDef?.label === "function" ? toolDef.label(node.args) : toolDef?.label) ||
    toolDef?.name ||
    node.type;

  const secondaryText =
    node.secondary ||
    node.command ||
    (toolDef?.formatChip ? toolDef.formatChip(node.args, node.result) : undefined) ||
    (typeof node.args === "string" ? node.args : undefined);

  const isMono = node.mono ?? (isCommandNode || Boolean(toolDef?.monoChip));

  const renderIcon = () => {
    if (isActive) {
      return (
        <span
          aria-hidden="true"
          className="size-3.5 shrink-0 animate-spin rounded-full border-[1.5px] border-muted-foreground/30 border-t-foreground"
        />
      );
    }
    if (node.status === "failed" || (node.exitCode !== undefined && node.exitCode > 0)) {
      return <AlertCircle className="size-3.5 text-rose-500 shrink-0" aria-hidden="true" />;
    }

    if (node.icon) return renderDynamicIcon(node.icon, node.iconClassName);
    if (toolDef?.icon) return renderDynamicIcon(toolDef.icon, toolDef.iconClassName);

    const semanticKey = `${node.primary || ""} ${node.toolName || ""} ${node.type || ""} ${node.command || ""}`.toLowerCase();

    if (semanticKey.includes("read") || semanticKey.includes("inspect") || semanticKey.includes("parse")) {
      return <FileText className="size-3.5 text-muted-foreground/80 shrink-0" aria-hidden="true" />;
    }
    if (
      semanticKey.includes("edit") ||
      semanticKey.includes("write") ||
      semanticKey.includes("patch") ||
      semanticKey.includes("create")
    ) {
      return <FileCode2 className="size-3.5 text-amber-500 shrink-0" aria-hidden="true" />;
    }
    if (
      isCommandNode ||
      semanticKey.includes("run") ||
      semanticKey.includes("test") ||
      semanticKey.includes("compile") ||
      semanticKey.includes("tsc") ||
      semanticKey.includes("exec")
    ) {
      return <Terminal className="size-3.5 text-violet-500 shrink-0" aria-hidden="true" />;
    }
    if (semanticKey.includes("search") || semanticKey.includes("query") || semanticKey.includes("lookup")) {
      return <Search className="size-3.5 text-blue-500 shrink-0" aria-hidden="true" />;
    }
    if (semanticKey.includes("db") || semanticKey.includes("database") || semanticKey.includes("sql") || semanticKey.includes("redis")) {
      return <Database className="size-3.5 text-emerald-500 shrink-0" aria-hidden="true" />;
    }
    if (semanticKey.includes("deploy") || semanticKey.includes("canary") || semanticKey.includes("cluster")) {
      return <Cpu className="size-3.5 text-sky-500 shrink-0" aria-hidden="true" />;
    }
    if (node.type === "step") {
      return <Check className="size-3.5 text-emerald-500 shrink-0" aria-hidden="true" />;
    }

    return <Command className="size-3.5 text-muted-foreground/80 shrink-0" aria-hidden="true" />;
  };

  return (
    <div className="flex flex-col my-0.5" style={{ animation: "agent-fade 280ms cubic-bezier(0.23,1,0.32,1) both" }}>
      <button
        type="button"
        disabled={!hasDetails}
        aria-expanded={open}
        onClick={() => hasDetails && setOpen((v) => !v)}
        className={cn(
          "group/row relative flex h-7 w-full items-center gap-2 rounded-md px-1.5 text-left text-[12px] transition-colors duration-150",
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          hasDetails ? "hover:bg-muted/60 cursor-pointer active:scale-[0.98]" : "cursor-default"
        )}
      >
        <span className="relative flex size-4 shrink-0 items-center justify-center text-muted-foreground">
          <span
            className={cn(
              "transition-opacity duration-150 flex items-center justify-center",
              hasDetails && "group-hover/row:opacity-0",
              open && "opacity-0"
            )}
          >
            {renderIcon()}
          </span>
          {hasDetails && (
            <ChevronDown
              aria-hidden="true"
              className={cn(
                "absolute size-3.5 transition-transform duration-200 opacity-0",
                "group-hover/row:opacity-100",
                open ? "opacity-100 rotate-0" : "-rotate-90"
              )}
            />
          )}
        </span>

        <span className="shrink-0 text-[12px] font-medium text-foreground tracking-tight">
          {primaryText}
        </span>

        {secondaryText && (
          <span
            className={cn(
              "inline-flex h-5 min-w-0 max-w-[65%] items-center truncate rounded-md bg-muted/80 px-1.5 text-[11px] text-muted-foreground border border-border/40 transition-colors group-hover/row:border-border/80 group-hover/row:text-foreground",
              isMono ? "font-mono" : "font-sans"
            )}
          >
            <span className="truncate">{secondaryText}</span>
          </span>
        )}

        {(node.add !== undefined || node.del !== undefined) && (
          <span className="ml-auto flex items-center gap-1 font-mono text-[11px] tabular-nums shrink-0">
            {node.add !== undefined && node.add > 0 && (
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">+{node.add}</span>
            )}
            {node.del !== undefined && node.del > 0 && (
              <span className="text-rose-600 dark:text-rose-400 font-medium">−{node.del}</span>
            )}
          </span>
        )}
      </button>

      {hasDetails && (
        <div
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.23,1,0.32,1)]",
            open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0 pointer-events-none"
          )}
        >
          <div className="min-h-0 overflow-hidden">
            <div className="mt-1 mb-1.5 ml-2.5 flex flex-col gap-1.5 border-l border-border/70 py-0.5 pl-2.5">
              {/* Custom Viewport Renderers */}
              {node.renderContent ? (
                node.renderContent()
              ) : toolDef?.renderCustomContent ? (
                toolDef.renderCustomContent({
                  args: node.args,
                  result: node.result,
                  node,
                })
              ) : null}

              {/* Dedicated Terminal Execution Format */}
              {isCommandNode && node.command && (
                <TerminalCommand
                  command={node.command}
                  output={node.output}
                  exitCode={node.exitCode ?? 0}
                  durationMs={node.durationMs}
                  isRunning={isActive}
                />
              )}

              {/* Real Embedded FileDiff Component */}
              {node.diffRows && (
                <FileDiff
                  file={node.diffFile || (typeof node.secondary === "string" ? node.secondary : "patch.ts")}
                  rows={node.diffRows}
                />
              )}

              {/* Structured Line Details */}
              {!isCommandNode && node.details && node.details.length > 0 && (
                <div className="flex flex-col gap-1">
                  {node.details.map((line, lIdx) => (
                    <span
                      key={lIdx}
                      className={cn(
                        "text-[11.5px] leading-relaxed",
                        line.tone === "add" && "text-emerald-600 dark:text-emerald-400 font-mono",
                        line.tone === "del" && "text-rose-600 dark:text-rose-400 font-mono",
                        line.tone === "ctx" && "text-muted-foreground font-mono",
                        line.tone === "error" && "text-rose-600 dark:text-rose-400 font-medium",
                        (!line.tone || line.tone === "muted") && "text-muted-foreground"
                      )}
                    >
                      {line.text}
                    </span>
                  ))}
                </div>
              )}

              {/* Code Snippet Fallback */}
              {!isCommandNode && !node.diffRows && node.codeSnippet && (
                <div className="rounded-lg border border-border/70 bg-muted/40 p-2.5 font-mono text-[11px] leading-relaxed text-foreground overflow-x-auto">
                  <pre className="whitespace-pre">{node.codeSnippet}</pre>
                </div>
              )}

              {/* Sources */}
              {node.sources && node.sources.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                  {node.sources.map((src, sIdx) => (
                    <a
                      key={sIdx}
                      href={src.url || "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-background px-2.5 py-0.5 text-[11px] text-muted-foreground hover:border-border hover:text-foreground transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                    >
                      <Globe className="size-2.5 opacity-70" aria-hidden="true" />
                      <span>{src.name}</span>
                      <ExternalLink className="size-2.5 opacity-50" aria-hidden="true" />
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
 * THINKING STATE (Unboxed Seamless Trigger)
 * ───────────────────────────────────────────────────────── */
export const ThinkingState = React.forwardRef<HTMLDivElement, ThinkingStateProps>(
  (
    {
      nodes = [],
      tools = DEFAULT_TOOL_REGISTRY,
      autoPlay = true,
      defaultExpanded,
      workingLabel = "Working...",
      onSettled,
      className,
      style,
      ...props
    },
    ref
  ) => {
    const totalNodes = nodes.length;
    const [activeIndex, setActiveIndex] = React.useState(autoPlay ? 0 : totalNodes);
    const [isWorking, setIsWorking] = React.useState(autoPlay);
    const [manualExpanded, setManualExpanded] = React.useState<boolean | null>(
      defaultExpanded !== undefined ? defaultExpanded : null
    );

    const startTimeRef = React.useRef<number>(Date.now());
    const [elapsedSeconds, setElapsedSeconds] = React.useState<number>(0);
    const isWorkingRef = React.useRef(isWorking);
    isWorkingRef.current = isWorking;

    const onSettledRef = React.useRef(onSettled);
    onSettledRef.current = onSettled;

    React.useEffect(() => {
      if (!autoPlay) return;
      startTimeRef.current = Date.now();

      const timer = setInterval(() => {
        if (!isWorkingRef.current) {
          clearInterval(timer);
          return;
        }
        const diff = Math.max(1, Math.round((Date.now() - startTimeRef.current) / 1000));
        setElapsedSeconds(diff);
      }, 250);

      return () => clearInterval(timer);
    }, [autoPlay]);

    const advanceStep = React.useCallback(() => {
      setActiveIndex((prev) => {
        const next = prev + 1;
        if (next >= totalNodes) {
          setIsWorking(false);
          const finalDuration = Math.max(1, Math.round((Date.now() - startTimeRef.current) / 1000));
          setElapsedSeconds(finalDuration);
        }
        return next;
      });
    }, [totalNodes]);

    React.useEffect(() => {
      if (!autoPlay || !isWorking || activeIndex >= totalNodes) return;

      const currentNode = nodes[activeIndex];
      if (currentNode?.type === "reasoning") return;

      const delay =
        currentNode?.type === "tool" || currentNode?.type === "terminal"
          ? 2200
          : currentNode?.type === "search"
          ? 2400
          : 1700;

      const timer = setTimeout(() => {
        advanceStep();
      }, delay);

      return () => clearTimeout(timer);
    }, [activeIndex, autoPlay, isWorking, totalNodes, nodes, advanceStep]);

    React.useEffect(() => {
      if (!isWorking && autoPlay) {
        onSettledRef.current?.();
      }
    }, [isWorking, autoPlay]);

    const isGlobalExpanded = manualExpanded !== null ? manualExpanded : isWorking;

    return (
      <div
        ref={ref}
        className={cn("flex w-full flex-col font-sans select-none text-foreground", className)}
        style={style}
        {...props}
      >
        <style>{`
          @keyframes agent-pixel-on {
            0%, 100% { opacity: 0.15; transform: scale(0.9); }
            50% { opacity: 0.95; transform: scale(1.1); }
          }
          @keyframes agent-shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
          @keyframes agent-fade {
            from { opacity: 0; transform: translateY(2px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>

        {/* Master Header Trigger (Seamless unboxed prose integration) */}
        <button
          type="button"
          aria-expanded={isGlobalExpanded}
          onClick={() => setManualExpanded((prev) => !(prev !== null ? prev : isWorking))}
          className={cn(
            "group flex w-fit items-center gap-1.5 p-0 bg-transparent text-left transition-colors duration-150 cursor-pointer",
            "text-muted-foreground/75 hover:text-foreground font-normal text-[13.5px] leading-relaxed",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none rounded-xs"
          )}
        >
          {isWorking && <PixelDotsLoader />}

          <span className="text-[13.5px] font-normal transition-colors">
            {isWorking ? (
              <span
                className="bg-clip-text text-transparent font-medium"
                style={{
                  backgroundImage:
                    "linear-gradient(90deg, var(--color-muted-foreground, oklch(0.55 0 0)) 35%, var(--color-foreground, oklch(0.95 0 0)) 50%, var(--color-muted-foreground, oklch(0.55 0 0)) 65%)",
                  backgroundSize: "200% 100%",
                  animation: "agent-shimmer 1.5s linear infinite",
                }}
              >
                {workingLabel}
              </span>
            ) : (
              <span>
                Worked for <span className="tabular-nums font-mono text-[12px]">{elapsedSeconds}</span> {elapsedSeconds === 1 ? "second" : "seconds"}
              </span>
            )}
          </span>

          <ChevronDown
            aria-hidden="true"
            className={cn(
              "size-3 opacity-30 transition-transform duration-300 group-hover:opacity-80",
              isGlobalExpanded ? "rotate-180" : "rotate-0"
            )}
          />
        </button>

        {/* Master Collapsible Timeline Channel */}
        <div
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-out",
            isGlobalExpanded
              ? "grid-rows-[1fr] opacity-100"
              : "grid-rows-[0fr] opacity-0 pointer-events-none"
          )}
        >
          <div className="min-h-0 overflow-hidden">
            <div className="mt-1 ml-2 border-l border-border/60 py-0.5 pl-2 flex flex-col gap-0.5">
              {nodes.slice(0, activeIndex + 1).map((node, idx) => {
                const isNodeActive = idx === activeIndex && isWorking;
                const isNodeFinished = idx < activeIndex || !isWorking;

                if (node.type === "reasoning" && node.sentences) {
                  return (
                    <NestedReasoningBlock
                      key={idx}
                      sentences={node.sentences}
                      durationSeconds={node.durationSeconds}
                      isActive={isNodeActive}
                      isFinished={isNodeFinished}
                      onFinished={advanceStep}
                    />
                  );
                }

                return (
                  <TracePillRow
                    key={idx}
                    node={node}
                    isActive={isNodeActive}
                    isFinished={isNodeFinished}
                    toolRegistry={tools}
                  />
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  }
);
ThinkingState.displayName = "ThinkingState";
