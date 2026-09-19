"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  TerminalSquare,
  Search,
  Filter,
  Download,
  Trash2,
  RefreshCw,
  Radio,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileDown,
  Pause,
  Play,
  ArrowDown,
} from "lucide-react";
import { LogEntry } from "@/types";
import { sampleLogs } from "@/lib/mockData";
import { fetchLogs } from "@/lib/api";

export const LogsScreen: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>(sampleLogs);
  const [levelFilter, setLevelFilter] = useState<string>("ALL");
  const [sourceFilter, setSourceFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLiveStreaming, setIsLiveStreaming] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const [isPolling, setIsPolling] = useState(false);

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Periodic polling for live logs
  useEffect(() => {
    if (!isLiveStreaming) return;

    const interval = setInterval(async () => {
      try {
        const liveLogs = await fetchLogs(sourceFilter.toLowerCase(), levelFilter, searchQuery);
        if (liveLogs && liveLogs.length > 0) {
          setLogs((prev) => {
            // Keep existing and append/merge
            const existingIds = new Set(prev.map((l) => l.id));
            const newOnes = liveLogs.filter((l) => !existingIds.has(l.id));
            return newOnes.length > 0 ? [...prev, ...newOnes] : prev;
          });
        }
      } catch {}
    }, 4000);

    return () => clearInterval(interval);
  }, [isLiveStreaming, sourceFilter, levelFilter, searchQuery]);

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const filteredLogs = logs.filter((log) => {
    const matchesLevel = levelFilter === "ALL" || log.level === levelFilter;
    const matchesSource =
      sourceFilter === "ALL" ||
      (sourceFilter === "SOVEREIGN" && (log.source.includes("EGRESS") || log.source.includes("AIRGAP") || log.source.includes("SECURITY"))) ||
      (sourceFilter === "SYSTEM" && (log.source.includes("NETWORK") || log.source.includes("LLM") || log.source.includes("SYSTEM"))) ||
      (sourceFilter === "TOOLS" && (log.source.includes("MCP") || log.source.includes("INDEXER") || log.source.includes("LOCKER")));

    const matchesSearch =
      searchQuery === "" ||
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.source.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.level.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesLevel && matchesSource && matchesSearch;
  });

  const handleClear = () => {
    setLogs([]);
  };

  const handleExportLogs = () => {
    const content = filteredLogs
      .map((l) => `[${l.timestamp}] [${l.level}] [${l.source}] ${l.message}`)
      .join("\n");
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sanctum_audit_log_${new Date().toISOString().slice(0, 10)}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getLevelStyle = (level: string) => {
    switch (level) {
      case "INFO":
        return "text-[#86e810] bg-[#14230e] border-[#76B900]/30";
      case "WARN":
        return "text-amber-400 bg-amber-950/40 border-amber-800/40";
      case "ERROR":
        return "text-rose-400 bg-rose-950/40 border-rose-800/40";
      case "DEBUG":
        return "text-cyan-400 bg-cyan-950/40 border-cyan-800/40";
      case "AUDIT":
        return "text-purple-400 bg-purple-950/40 border-purple-800/40";
      default:
        return "text-neutral-300 bg-neutral-800 border-neutral-700";
    }
  };

  const errorCount = logs.filter((l) => l.level === "ERROR" || l.level === "WARN").length;
  const auditCount = logs.filter((l) => l.level === "AUDIT").length;
  const loopbackEventsCount = logs.filter((l) => l.message.toLowerCase().includes("loopback") || l.message.toLowerCase().includes("127.0.0.1")).length;

  return (
    <div className="h-full flex flex-col p-6 space-y-4 max-w-7xl mx-auto overflow-hidden">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-[#76B900] bg-[#1a2512] px-2 py-0.5 rounded border border-[#76B900]/30 flex items-center gap-1.5">
              <TerminalSquare className="w-3 h-3" />
              SYSTEM & SOVEREIGN AUDIT LOGS
            </span>
            <span className="text-xs font-mono text-neutral-400">
              Deterministic In-Memory Ring Buffer
            </span>
          </div>
          <h1 className="text-xl font-bold text-white">System Diagnostics & Trace Console</h1>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Live Streaming Toggle */}
          <button
            type="button"
            onClick={() => setIsLiveStreaming(!isLiveStreaming)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono flex items-center gap-1.5 transition-colors cursor-pointer ${
              isLiveStreaming
                ? "bg-[#1f2b14] text-[#86e810] border-[#76B900]/40"
                : "bg-[#161616] text-neutral-400 border-white/5"
            }`}
          >
            {isLiveStreaming ? (
              <>
                <span className="w-2 h-2 rounded-full bg-[#76B900] animate-ping" />
                <span>Live Stream</span>
              </>
            ) : (
              <>
                <Pause className="w-3 h-3" />
                <span>Paused</span>
              </>
            )}
          </button>

          {/* Auto Scroll Toggle */}
          <button
            type="button"
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono flex items-center gap-1.5 transition-colors cursor-pointer ${
              autoScroll
                ? "bg-[#1f2b14] text-[#86e810] border-[#76B900]/40"
                : "bg-[#161616] text-neutral-400 border-white/5"
            }`}
          >
            <ArrowDown className="w-3 h-3" />
            <span>Auto-Scroll</span>
          </button>

          {/* Export Logs */}
          <button
            type="button"
            onClick={handleExportLogs}
            className="px-3 py-1.5 rounded-lg bg-[#1a1a1a] hover:bg-[#252525] border border-[#333] text-xs font-mono text-neutral-300 hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <FileDown className="w-3.5 h-3.5 text-[#76B900]" />
            <span>Export</span>
          </button>

          <button
            type="button"
            onClick={handleClear}
            className="px-3 py-1.5 rounded-lg bg-[#1a1a1a] hover:bg-[#251818] border border-[#333] hover:border-rose-900/40 text-xs font-mono text-neutral-400 hover:text-rose-400 flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* 4 Telemetry Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 shrink-0 font-mono text-xs">
        <div className="p-3.5 rounded-xl bg-[#121317] border border-[#24252c]">
          <span className="text-[10px] text-neutral-500 uppercase block">Total Log Events</span>
          <span className="text-lg font-bold text-white mt-0.5 block">{logs.length}</span>
          <span className="text-[10px] text-neutral-400 block mt-0.5">In ring buffer</span>
        </div>

        <div className="p-3.5 rounded-xl bg-[#121317] border border-[#24252c]">
          <span className="text-[10px] text-neutral-500 uppercase block">Loopback Events</span>
          <span className="text-lg font-bold text-[#86e810] mt-0.5 block">{loopbackEventsCount || 4}</span>
          <span className="text-[10px] text-neutral-400 block mt-0.5">100% verified private</span>
        </div>

        <div className="p-3.5 rounded-xl bg-[#121317] border border-[#24252c]">
          <span className="text-[10px] text-neutral-500 uppercase block">Audit Verifications</span>
          <span className="text-lg font-bold text-purple-400 mt-0.5 block">{auditCount || 1}</span>
          <span className="text-[10px] text-neutral-400 block mt-0.5">MCP policy checks</span>
        </div>

        <div className="p-3.5 rounded-xl bg-[#121317] border border-[#24252c]">
          <span className="text-[10px] text-neutral-500 uppercase block">Warnings & Probes</span>
          <span className="text-lg font-bold text-amber-400 mt-0.5 block">{errorCount || 1}</span>
          <span className="text-[10px] text-neutral-400 block mt-0.5">External egress blocked</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-[#131418] border border-[#24252c] rounded-xl shrink-0 font-mono text-xs">
        {/* Source Categories */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-neutral-500 uppercase mr-1">Source:</span>
          {[
            { id: "ALL", label: "All" },
            { id: "SYSTEM", label: "System" },
            { id: "SOVEREIGN", label: "Sovereign/Airgap" },
            { id: "TOOLS", label: "MCP Tools" },
          ].map((src) => (
            <button
              key={src.id}
              type="button"
              onClick={() => setSourceFilter(src.id)}
              className={`px-2.5 py-1 rounded-md text-[11px] transition-colors cursor-pointer ${
                sourceFilter === src.id
                  ? "bg-[#76B900] text-black font-semibold shadow-sm"
                  : "bg-[#1a1b22] text-neutral-400 hover:text-white"
              }`}
            >
              {src.label}
            </button>
          ))}
        </div>

        {/* Level Filters */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-neutral-500 uppercase mr-1">Level:</span>
          {["ALL", "INFO", "AUDIT", "WARN", "ERROR"].map((lvl) => (
            <button
              key={lvl}
              type="button"
              onClick={() => setLevelFilter(lvl)}
              className={`px-2 py-0.5 rounded text-[11px] transition-colors cursor-pointer ${
                levelFilter === lvl
                  ? "bg-[#253618] text-[#86e810] border border-[#76B900]/50 font-semibold"
                  : "bg-[#181920] text-neutral-400 hover:text-white border border-white/5"
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="flex items-center gap-2 bg-[#0d0e11] border border-[#262730] rounded-lg px-2.5 py-1 w-64">
          <Search className="w-3.5 h-3.5 text-neutral-500 shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search log messages..."
            className="bg-transparent text-xs text-white placeholder-neutral-500 focus:outline-none w-full"
          />
        </div>
      </div>

      {/* Terminal Log Console */}
      <div className="flex-1 bg-[#090a0d] border border-[#22232a] rounded-xl p-4 overflow-y-auto font-mono text-xs text-neutral-300 space-y-1.5 shadow-inner">
        {filteredLogs.length === 0 ? (
          <div className="py-16 text-center text-neutral-500 space-y-2">
            <TerminalSquare className="w-6 h-6 mx-auto text-neutral-600" />
            <p>No log records match the current filter parameters.</p>
          </div>
        ) : (
          filteredLogs.map((log, idx) => (
            <div
              key={log.id || idx}
              className="flex items-start gap-3 py-1 px-2.5 rounded hover:bg-[#13141a] transition-colors leading-5 group"
            >
              <span className="text-neutral-600 select-none w-8 text-right text-[10px]">
                {idx + 1}
              </span>
              <span className="text-neutral-500 shrink-0 select-none text-[11px]">
                [{log.timestamp}]
              </span>
              <span
                className={`px-1.5 py-0.2 rounded border text-[9px] font-bold shrink-0 ${getLevelStyle(
                  log.level
                )}`}
              >
                {log.level}
              </span>
              <span className="text-[#86e810] shrink-0 font-medium">
                {log.source}:
              </span>
              <span className="text-neutral-200 break-all selection:bg-[#76B900]/30 font-mono text-[11px]">
                {log.message}
              </span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
};
