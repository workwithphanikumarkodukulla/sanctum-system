"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Terminal as TerminalIcon,
  Play,
  RotateCcw,
  Trash2,
  CheckCircle2,
  XCircle,
  Folder,
  Loader2,
  CornerDownLeft,
} from "lucide-react";

interface CommandHistoryItem {
  id: string;
  command: string;
  cwd: string;
  stdout: string;
  stderr: string;
  exitCode: number;
  durationMs: number;
  timestamp: string;
}

interface InteractiveTerminalProps {
  onClose?: () => void;
  initialHeight?: number;
}

// Strip ANSI escape codes from shell output
function cleanAnsi(text: string): string {
  return text.replace(/\u001b\[[0-9;]*[a-zA-Z]/g, "").replace(/\u001b\([a-zA-Z]/g, "");
}

export function InteractiveTerminal({ onClose }: InteractiveTerminalProps) {
  const [cwd, setCwd] = useState<string>("");
  const [history, setHistory] = useState<CommandHistoryItem[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);

  // Buffer of sent commands for up/down arrow cycling
  const commandListRef = useRef<string[]>([]);

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Initialize cwd on mount with pwd or whoami
  useEffect(() => {
    async function initCwd() {
      try {
        const res = await fetch("/api/terminal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: "pwd" }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.cwd) {
            setCwd(data.cwd);
          }
        }
      } catch {
        // ignore
      }
    }
    initCwd();
  }, []);

  // Auto-scroll on new output
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, isRunning]);

  // Focus input when clicking anywhere in terminal body
  const handleContainerClick = (e: React.MouseEvent) => {
    // Don't steal focus if user is selecting text
    if (window.getSelection()?.toString()) return;
    inputRef.current?.focus();
  };

  const handleRunCommand = async (cmdToRun?: string) => {
    const command = (cmdToRun !== undefined ? cmdToRun : inputValue).trim();
    if (!command || isRunning) return;

    if (command === "clear") {
      setHistory([]);
      setInputValue("");
      setHistoryIndex(-1);
      return;
    }

    // Add to history navigation list
    commandListRef.current.push(command);
    setHistoryIndex(-1);
    setInputValue("");
    setIsRunning(true);

    const startTime = Date.now();

    try {
      const res = await fetch("/api/terminal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, cwd }),
      });

      const data = await res.json();
      const durationMs = data.durationMs ?? (Date.now() - startTime);

      if (data.cwd) {
        setCwd(data.cwd);
      }

      setHistory((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(2, 9),
          command,
          cwd: cwd || data.cwd,
          stdout: cleanAnsi(data.stdout || ""),
          stderr: cleanAnsi(data.stderr || ""),
          exitCode: data.exitCode ?? 0,
          durationMs,
          timestamp: new Date().toLocaleTimeString([], { hour12: false }),
        },
      ]);
    } catch (err: any) {
      setHistory((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(2, 9),
          command,
          cwd,
          stdout: "",
          stderr: `Failed to execute: ${err?.message || "Network/Server error"}`,
          exitCode: 1,
          durationMs: Date.now() - startTime,
          timestamp: new Date().toLocaleTimeString([], { hour12: false }),
        },
      ]);
    } finally {
      setIsRunning(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleRunCommand();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const list = commandListRef.current;
      if (list.length === 0) return;
      const nextIndex = historyIndex === -1 ? list.length - 1 : Math.max(0, historyIndex - 1);
      setHistoryIndex(nextIndex);
      setInputValue(list[nextIndex] || "");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const list = commandListRef.current;
      if (list.length === 0 || historyIndex === -1) return;
      const nextIndex = historyIndex + 1;
      if (nextIndex >= list.length) {
        setHistoryIndex(-1);
        setInputValue("");
      } else {
        setHistoryIndex(nextIndex);
        setInputValue(list[nextIndex] || "");
      }
    } else if (e.key === "c" && (e.ctrlKey || e.metaKey) && !window.getSelection()?.toString()) {
      // Ctrl+C to cancel typed command
      setInputValue("");
      setHistoryIndex(-1);
    }
  };

  // Get shortened folder name for prompt
  const folderName = cwd ? cwd.split("/").filter(Boolean).pop() || "sanctum" : "sanctum";

  return (
    <div className="flex flex-col h-full bg-[#0b0b0b] font-mono text-xs overflow-hidden select-text">
      {/* ── Terminal Header ── */}
      <div className="h-7 px-3 bg-[#131313] border-b border-[#202020] flex items-center justify-between text-[11px] text-neutral-400 shrink-0 select-none">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5 text-white font-semibold shrink-0">
            <TerminalIcon className="w-3.5 h-3.5 text-[#76B900]" />
            <span>zsh</span>
          </div>

          <span className="text-neutral-600">•</span>

          <div
            className="flex items-center gap-1 text-neutral-400 hover:text-neutral-200 transition-colors truncate max-w-[280px]"
            title={cwd || "Current Directory"}
          >
            <Folder className="w-3 h-3 text-[#76B900]/70 shrink-0" />
            <span className="truncate">{folderName}</span>
          </div>

          <span className="text-neutral-600">•</span>

          <div className="flex items-center gap-1 text-[#76B900]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] animate-pulse" />
            <span className="text-[10px]">live</span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setHistory([])}
            title="Clear terminal output (or type 'clear')"
            className="flex items-center gap-1 px-1.5 py-0.5 rounded text-neutral-400 hover:text-white hover:bg-white/5 transition-colors text-[10px]"
          >
            <Trash2 className="w-3 h-3" />
            <span className="hidden sm:inline">Clear</span>
          </button>

          {onClose && (
            <button
              onClick={onClose}
              title="Close terminal"
              className="p-1 text-neutral-400 hover:text-white hover:bg-white/5 rounded transition-colors text-sm leading-none ml-1"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* ── Terminal Output & Interactive Prompt ── */}
      <div
        onClick={handleContainerClick}
        className="flex-1 p-3 text-neutral-300 font-mono text-xs overflow-y-auto space-y-2 cursor-text"
      >
        {/* Sovereign Diagnostics Banner */}
        <div className="pb-1 border-b border-white/[0.04] text-[11px] text-neutral-500 space-y-0.5 select-none">
          <div className="flex items-center justify-between text-neutral-400 font-medium">
            <span>Sanctum Sovereign Interactive Shell (darwin-arm64)</span>
          </div>
          <div className="text-[10px] text-neutral-500 flex items-center gap-2">
            <span>Runtime: Node.js {process.version}</span>
            <span>•</span>
            <span className="text-[#76B900]/80">Local Process Isolation Active</span>
          </div>
        </div>

        {/* Render History */}
        {history.map((item) => (
          <div key={item.id} className="space-y-1 group">
            {/* Command Header */}
            <div className="flex items-center justify-between text-xs pt-0.5">
              <div className="flex items-center gap-2 text-neutral-200">
                <span className="text-[#86e810] font-semibold">$</span>
                <span className="font-semibold text-white">{item.command}</span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-neutral-500 select-none">
                <span>{item.durationMs}ms</span>
                {item.exitCode === 0 ? (
                  <span className="flex items-center gap-0.5 text-emerald-400">
                    <CheckCircle2 className="w-2.5 h-2.5" /> 0
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 text-red-400">
                    <XCircle className="w-2.5 h-2.5" /> {item.exitCode}
                  </span>
                )}
              </div>
            </div>

            {/* Command stdout */}
            {item.stdout && (
              <pre className="text-neutral-300 text-[11px] leading-relaxed whitespace-pre-wrap font-mono pl-3 border-l border-white/5 overflow-x-auto selection:bg-[#76B900]/30">
                {item.stdout}
              </pre>
            )}

            {/* Command stderr */}
            {item.stderr && (
              <pre className="text-red-400/90 text-[11px] leading-relaxed whitespace-pre-wrap font-mono pl-3 border-l border-red-500/30 overflow-x-auto">
                {item.stderr}
              </pre>
            )}
          </div>
        ))}

        {/* Active Command Execution Loading State */}
        {isRunning && (
          <div className="flex items-center gap-2 text-neutral-400 text-xs py-1">
            <Loader2 className="w-3 h-3 animate-spin text-[#76B900]" />
            <span className="text-neutral-400">Executing command...</span>
          </div>
        )}

        {/* Active Input Line */}
        <div className="flex items-center gap-2 pt-1">
          <div className="flex items-center gap-1 text-xs shrink-0 select-none">
            <span className="text-neutral-500 font-medium">{folderName}</span>
            <span className="text-[#86e810] font-bold">$</span>
          </div>

          <div className="flex-1 relative flex items-center">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRunning}
              autoFocus
              spellCheck={false}
              autoComplete="off"
              className="w-full bg-transparent border-none outline-none text-white text-xs font-mono focus:ring-0 p-0 caret-[#76B900]"
            />
            {inputValue && !isRunning && (
              <button
                onClick={() => handleRunCommand()}
                title="Execute (Enter)"
                className="text-neutral-500 hover:text-[#76B900] transition-colors p-1"
              >
                <CornerDownLeft className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Scroll anchor */}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
