"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  ShieldAlert,
  Cpu,
  Zap,
  HardDrive,
  FolderTree,
  Terminal,
  Activity,
  CheckCircle2,
  Lock,
  ArrowUpRight,
  Radio,
  Server,
  Bot,
  BookOpen,
  Play,
  FileText,
} from "lucide-react";
import { SanctumLogo } from "@/components/ui/sanctum-logo";
import { SystemTelemetry, ScreenType } from "@/types";

interface OverviewScreenProps {
  telemetry: SystemTelemetry;
  onNavigate: (screen: ScreenType) => void;
  onQuickPrompt: (prompt: string) => void;
}

export const OverviewScreen: React.FC<OverviewScreenProps> = ({
  telemetry,
  onNavigate,
  onQuickPrompt,
}) => {
  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Banner / Hero */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="relative overflow-hidden rounded-xl border border-[#262626] bg-gradient-to-r from-[#12180e] via-[#141414] to-[#121212] p-6"
      >
        <div className="absolute right-0 top-0 bottom-0 w-96 bg-[radial-gradient(circle_at_top_right,rgba(118,185,0,0.15),transparent_70%)] pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium tracking-tight bg-[#76B900]/15 text-[#76B900] border border-[#76B900]/30 flex items-center gap-1.5">
                <span className="radar-dot" />
                SOVEREIGN AIRGAP SYSTEM ACTIVE
              </span>
              <span className="text-xs font-mono text-neutral-400">
                100% Loopback Socket • Zero External Egress
              </span>
            </div>
            <div className="flex items-center gap-3.5">
              <SanctumLogo
                size={34}
                color="#76B900"
                className="shrink-0 drop-shadow-[0_0_16px_rgba(118,185,0,0.35)]"
              />
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2 font-mono">
                Sanctum
              </h1>
            </div>
            <p className="text-neutral-300 text-sm mt-1 max-w-2xl">
              Local-first desktop agent environment. All model inference runs through Ollama/vLLM on loopback (<code className="text-[#9ae018] font-mono">127.0.0.1:5050</code>). Your code, vectors, and memory never leave this machine.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => onNavigate("agent")}
              className="px-4 py-2 rounded-lg bg-[#76B900] hover:bg-[#86d000] text-black font-semibold text-xs transition-all flex items-center gap-2 shadow-lg shadow-[#76B900]/20 cursor-pointer"
            >
              <span>Launch Agent Assistant</span>
              <ArrowUpRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => onNavigate("security")}
              className="px-3.5 py-2 rounded-lg bg-[#1a1a1a] hover:bg-[#222] border border-[#333] text-neutral-200 text-xs transition-colors flex items-center gap-2 cursor-pointer"
            >
              <Radio className="w-3.5 h-3.5 text-[#76B900]" />
              <span>Verify Airgap Radar</span>
            </button>
          </div>
        </div>
      </motion.div>

      {/* ═══════════ ECOSYSTEM ORBIT MAP ═══════════ */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
        className="glass-panel rounded-xl border border-[#242424] p-6 relative overflow-hidden"
      >
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs font-mono text-[#76B900] bg-[#1a2512] px-2 py-0.5 rounded border border-[#76B900]/30">
            SANCTUM / COMMAND CENTER
          </span>
          <span className="text-xs text-neutral-400 font-mono">Everything local. Everything in orbit.</span>
        </div>

        <div className="relative h-[280px] flex items-center justify-center">
          {/* Orbit rings */}
          <div className="absolute w-[220px] h-[220px] rounded-full border border-[#76B900]/15 animate-[spin_40s_linear_infinite]" />
          <div className="absolute w-[160px] h-[160px] rounded-full border border-[#76B900]/10 animate-[spin_30s_linear_infinite_reverse]" />

          {/* Core */}
          <div className="relative z-10 flex flex-col items-center gap-1">
            <div className="w-14 h-14 rounded-full bg-[#1a2512] border-2 border-[#76B900]/50 flex items-center justify-center shadow-[0_0_30px_rgba(118,185,0,0.25)]">
              <span className="text-lg">◉</span>
            </div>
            <span className="text-[10px] font-mono font-bold text-white">SANCTUM</span>
            <span className="text-[9px] font-mono text-[#76B900]">FLUID CORE</span>
          </div>

          {/* Orbit Nodes */}
          {[
            { screen: "workspace" as ScreenType, icon: FolderTree, label: "Workspace", sub: `${telemetry.loopbackCalls > 0 ? "Active" : "—"} files`, angle: 0, color: "#4ade80" },
            { screen: "agent" as ScreenType, icon: Bot, label: "Agent", sub: "Ready to build", angle: 72, color: "#22d3ee" },
            { screen: "models" as ScreenType, icon: Cpu, label: "Models", sub: telemetry.activeModel?.split(":")[0] || "—", angle: 144, color: "#a78bfa" },
            { screen: "lkb" as ScreenType, icon: BookOpen, label: "Knowledge", sub: "Indexed", angle: 216, color: "#fbbf24" },
            { screen: "locker" as ScreenType, icon: Lock, label: "Locker", sub: "Local security", angle: 288, color: "#f87171" },
          ].map((node) => {
            const r = 120;
            const rad = (node.angle * Math.PI) / 180;
            const x = Math.cos(rad) * r;
            const y = Math.sin(rad) * r;
            const Icon = node.icon;
            return (
              <motion.button
                key={node.screen}
                whileHover={{ scale: 1.12 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onNavigate(node.screen)}
                className="absolute flex flex-col items-center gap-0.5 cursor-pointer group"
                style={{ transform: `translate(${x}px, ${y}px)` }}
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center border transition-colors"
                  style={{
                    backgroundColor: `${node.color}15`,
                    borderColor: `${node.color}40`,
                  }}
                >
                  <Icon className="w-4 h-4" style={{ color: node.color }} />
                </div>
                <span className="text-[10px] font-mono font-bold text-white group-hover:text-[#76B900] transition-colors">{node.label}</span>
                <span className="text-[9px] font-mono text-neutral-500">{node.sub}</span>
              </motion.button>
            );
          })}
        </div>

        {/* Ecosystem Footer */}
        <div className="flex items-center justify-between mt-2 pt-3 border-t border-[#242424]">
          <div className="flex items-center gap-2 text-xs font-mono text-neutral-400">
            <span className="w-2 h-2 rounded-full bg-[#76B900] animate-pulse" />
            <span><b className="text-white">Sanctum Intelligence</b> — Inference stays inside the loopback boundary</span>
          </div>
          <button
            onClick={() => onNavigate("security")}
            className="text-[11px] font-mono text-[#76B900] hover:text-[#86e810] transition-colors flex items-center gap-1 cursor-pointer"
          >
            View posture <ArrowUpRight className="w-3 h-3" />
          </button>
        </div>
      </motion.div>

      {/* ═══════════ INDUSTRY PIPELINE DEMO CARD ═══════════ */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="glass-panel rounded-xl border border-[#262626] p-5 relative overflow-hidden"
      >
        <div className="absolute right-0 top-0 bottom-0 w-64 bg-[radial-gradient(circle_at_right,rgba(118,185,0,0.08),transparent_70%)] pointer-events-none" />
        <div className="relative z-10">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
            <div>
              <span className="text-[10px] font-mono text-[#76B900] tracking-wider">FEATURED INDUSTRY PIPELINE</span>
              <h3 className="text-sm font-semibold text-white mt-1">Autonomous Inspection to Approval Note Pipeline</h3>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono text-[#76B900] bg-[#1a2512] border border-[#76B900]/30 flex items-center gap-1.5 self-start">
              <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] animate-pulse" />
              API 510 / ASME SEC VIII
            </span>
          </div>
          <p className="text-xs text-neutral-400 leading-relaxed mb-4">
            End-to-end refinery pressure vessel integrity audit: Ingests scanned ultrasonic thickness reports for Northern PSU Refinery Unit 4 Hydrocracker (PV-204B), evaluates minimum wall thickness compliance (t<sub>min</sub>), and drafts an authorized regulatory Word Approval Note (.docx) with Inspector sign-off.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => {
                onQuickPrompt("Run the autonomous Inspection to Approval Note pipeline for refinery pressure vessel PV-204B, evaluate API 510 ultrasonic readings and draft the signed approval note as Word file.");
                onNavigate("agent");
              }}
              className="px-3.5 py-2 rounded-lg bg-[#76B900] hover:bg-[#86d000] text-black font-semibold text-xs transition-all flex items-center gap-1.5 cursor-pointer shadow-lg shadow-[#76B900]/20"
            >
              <Play className="w-3.5 h-3.5" /> Run Inspection Pipeline Demo
            </button>
            <button
              onClick={() => onNavigate("workspace")}
              className="px-3.5 py-2 rounded-lg bg-[#1a1a1a] hover:bg-[#222] border border-[#333] text-neutral-300 text-xs transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <FileText className="w-3.5 h-3.5" /> Open Generated Approval Note (.docx)
            </button>
          </div>
        </div>
      </motion.div>

      {/* Telemetry Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.05 }}
          className="glass-card rounded-xl p-4 border border-[#252525] relative overflow-hidden"
        >
          <div className="flex items-center justify-between text-neutral-400 mb-2">
            <span className="text-xs font-mono">EGRESS RADAR</span>
            <ShieldAlert className="w-4 h-4 text-[#76B900]" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-2">
            <span>0</span>
            <span className="text-xs font-normal text-neutral-400">External Calls</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-neutral-400 font-mono">
            <span className="text-[#86e810] flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-[#76B900]" /> 1,482 Loopback Pkts
            </span>
            <span className="px-1.5 py-0.5 rounded bg-[#1f2917] text-[#9ae018] text-[10px]">100% Local</span>
          </div>
          <div className="w-full bg-[#202020] h-1 rounded-full mt-2 overflow-hidden">
            <div className="bg-[#76B900] h-full w-full" />
          </div>
        </motion.div>

        {/* Metric 2 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="glass-card rounded-xl p-4 border border-[#252525] relative overflow-hidden"
        >
          <div className="flex items-center justify-between text-neutral-400 mb-2">
            <span className="text-xs font-mono">VRAM ALLOCATION</span>
            <Cpu className="w-4 h-4 text-[#76B900]" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-2">
            <span>{telemetry.vramUsageGb}</span>
            <span className="text-xs font-normal text-neutral-400">/ {telemetry.totalVramGb} GB</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-neutral-400 font-mono">
            <span>GPU Active ({telemetry.activeModel})</span>
            <span className="text-neutral-300">34% Load</span>
          </div>
          <div className="w-full bg-[#202020] h-1 rounded-full mt-2 overflow-hidden">
            <div className="bg-[#76B900] h-full w-[34%]" />
          </div>
        </motion.div>

        {/* Metric 3 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.15 }}
          className="glass-card rounded-xl p-4 border border-[#252525] relative overflow-hidden"
        >
          <div className="flex items-center justify-between text-neutral-400 mb-2">
            <span className="text-xs font-mono">SOCKET LATENCY</span>
            <Zap className="w-4 h-4 text-[#76B900]" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-2">
            <span>{telemetry.averageLatencyMs}</span>
            <span className="text-xs font-normal text-neutral-400">ms Loopback</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-neutral-400 font-mono">
            <span>Zero Cloud Roundtrips</span>
            <span className="text-[#86e810]">Direct IPC</span>
          </div>
          <div className="w-full bg-[#202020] h-1 rounded-full mt-2 overflow-hidden">
            <div className="bg-[#76B900] h-full w-[88%]" />
          </div>
        </motion.div>

        {/* Metric 4 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.2 }}
          className="glass-card rounded-xl p-4 border border-[#252525] relative overflow-hidden"
        >
          <div className="flex items-center justify-between text-neutral-400 mb-2">
            <span className="text-xs font-mono">CONTEXT WINDOW</span>
            <Activity className="w-4 h-4 text-[#76B900]" />
          </div>
          <div className="text-2xl font-bold font-mono text-white flex items-baseline gap-2">
            <span>4.2k</span>
            <span className="text-xs font-normal text-neutral-400">/ 32k tokens</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-neutral-400 font-mono">
            <span>Local Flash Attention</span>
            <span className="text-neutral-300">13% Usage</span>
          </div>
          <div className="w-full bg-[#202020] h-1 rounded-full mt-2 overflow-hidden">
            <div className="bg-[#76B900] h-full w-[13%]" />
          </div>
        </motion.div>
      </div>

      {/* Quick Launch Action Cards */}
      <div className="space-y-3">
        <h2 className="text-xs font-mono uppercase tracking-wider text-neutral-400">
          Agent Capabilities & Quick Workflows
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <motion.div
            whileHover={{ y: -3 }}
            onClick={() => {
              onNavigate("agent");
              onQuickPrompt("Analyze calculator.py and add safe reciprocal math handling.");
            }}
            className="glass-card rounded-xl p-4 border border-[#262626] cursor-pointer group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-8 h-8 rounded-lg bg-[#1f2b14] text-[#76B900] flex items-center justify-center group-hover:bg-[#76B900] group-hover:text-black transition-colors">
                <FolderTree className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-mono text-[#76B900] bg-[#1a2512] px-2 py-0.5 rounded border border-[#76B900]/30">
                CODE AUDIT
              </span>
            </div>
            <h3 className="text-sm font-semibold text-white group-hover:text-[#76B900] transition-colors">
              Audit Workspace Files
            </h3>
            <p className="text-xs text-neutral-400 mt-1">
              Inspect calculator.py, run automated AST syntax analysis, and execute unit tests in Python sandbox.
            </p>
          </motion.div>

          <motion.div
            whileHover={{ y: -3 }}
            onClick={() => onNavigate("models")}
            className="glass-card rounded-xl p-4 border border-[#262626] cursor-pointer group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-8 h-8 rounded-lg bg-[#1f2b14] text-[#76B900] flex items-center justify-center group-hover:bg-[#76B900] group-hover:text-black transition-colors">
                <Cpu className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-mono text-[#76B900] bg-[#1a2512] px-2 py-0.5 rounded border border-[#76B900]/30">
                FLUID ROUTING
              </span>
            </div>
            <h3 className="text-sm font-semibold text-white group-hover:text-[#76B900] transition-colors">
              Benchmark Local Models
            </h3>
            <p className="text-xs text-neutral-400 mt-1">
              Switch between Gemma 4, DeepSeek Coder 6.7B, and Qwen 2.5 with quantization telemetry.
            </p>
          </motion.div>

          <motion.div
            whileHover={{ y: -3 }}
            onClick={() => onNavigate("locker")}
            className="glass-card rounded-xl p-4 border border-[#262626] cursor-pointer group"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-8 h-8 rounded-lg bg-[#1f2b14] text-[#76B900] flex items-center justify-center group-hover:bg-[#76B900] group-hover:text-black transition-colors">
                <Lock className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-mono text-[#76B900] bg-[#1a2512] px-2 py-0.5 rounded border border-[#76B900]/30">
                CRYPTO LOCKER
              </span>
            </div>
            <h3 className="text-sm font-semibold text-white group-hover:text-[#76B900] transition-colors">
              Cover & Protect Files
            </h3>
            <p className="text-xs text-neutral-400 mt-1">
              Encrypt and decrypt sensitive project files locally with Argon2id and AES-256-GCM.
            </p>
          </motion.div>
        </div>
      </div>

      {/* Activity Timeline & System Trace */}
      <div className="glass-panel rounded-xl p-5 border border-[#242424]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-[#76B900]" />
            <h3 className="text-xs font-mono uppercase tracking-wider text-white">
              Real-time Sovereign Activity Feed
            </h3>
          </div>
          <span className="text-[11px] font-mono text-neutral-500">Live Agent IPC Log</span>
        </div>

        <div className="space-y-2.5 font-mono text-xs">
          <div className="p-2.5 rounded-lg bg-[#151515] border border-[#202020] flex items-center justify-between">
            <div className="flex items-center gap-2 text-neutral-300">
              <span className="w-2 h-2 rounded-full bg-[#76B900]" />
              <span className="text-[#86e810]">AGENT_LOOP:</span>
              <span>Loaded memory context from local SQLite database (4.2k tokens).</span>
            </div>
            <span className="text-[10px] text-neutral-500">12s ago</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#151515] border border-[#202020] flex items-center justify-between">
            <div className="flex items-center gap-2 text-neutral-300">
              <span className="w-2 h-2 rounded-full bg-[#76B900]" />
              <span className="text-[#86e810]">MCP_TOOL:</span>
              <span>Tool <code className="text-white">file_tool.read</code> inspected <code className="text-[#76B900]">workspace/calculator.py</code>.</span>
            </div>
            <span className="text-[10px] text-neutral-500">45s ago</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#151515] border border-[#202020] flex items-center justify-between">
            <div className="flex items-center gap-2 text-neutral-300">
              <span className="w-2 h-2 rounded-full bg-[#76B900]" />
              <span className="text-[#86e810]">WIRESHARK:</span>
              <span>Loopback socket verified. 0 outbound network attempts intercepted.</span>
            </div>
            <span className="text-[10px] text-neutral-500">2m ago</span>
          </div>
        </div>
      </div>
    </div>
  );
};
