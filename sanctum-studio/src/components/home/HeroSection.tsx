"use client";

import React from "react";
import { motion } from "framer-motion";
import { ChevronRight, ShieldCheck, Terminal, Cpu, Zap, Code2, Sun, Moon } from "lucide-react";
import Vortex from "@/components/Vortex";
import { SanctumLogo } from "@/components/ui/sanctum-logo";
import { useTheme } from "@/lib/theme";

interface HeroSectionProps {
  onExploreAI: () => void;
  onRequestDemo: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onExploreAI,
  onRequestDemo,
}) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <section className="relative w-full h-screen overflow-hidden bg-black select-none flex items-center">
      {/* Top-Right Theme Toggle */}
      <div className="absolute top-6 right-8 z-30 pointer-events-auto">
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={toggleTheme}
          title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
          aria-label="Toggle Theme Mode"
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-black/40 hover:bg-black/60 border border-white/10 hover:border-[#22c55e]/40 text-neutral-200 text-xs backdrop-blur-md shadow-lg transition-colors cursor-pointer"
        >
          {theme === "dark" ? (
            <Moon className="w-3.5 h-3.5 text-[#22c55e]" />
          ) : (
            <Sun className="w-3.5 h-3.5 text-amber-400" />
          )}
          <span className="font-mono text-[11px] font-medium tracking-wide">
            {theme === "dark" ? "Dark" : "Light"}
          </span>
        </motion.button>
      </div>

      {/* 3D Vortex / Tornado Canvas - Full Screen with xOffset shifting it to the right */}
      <div className="absolute inset-0 z-0 pointer-events-auto">
        <Vortex
          background="#000000"
          topRadius={450}
          waistRadius={65}
          waistPosition={50}
          bottomRadius={1350}
          twist={3.3}
          zoom={76}
          xOffset={-3.8} // Shifts camera left by 3.8 units so the tornado is on the right side (~71% width)
          speed={10}
          direction="right"
          lineOptions={{
            count: 270,
            color: "#22c55e",
            glow: 10,
          }}
          dots={true}
          dotOptions={{
            count: 8500,
            size: 22,
            color: "#ffffff",
            glow: 10,
            flicker: 10,
          }}
          comets={true}
          cometOptions={{
            count: 14,
            speed: 6.5,
            color: "#f97316",
            glow: 9,
            tail: 24,
            delay: 6,
            collide: 7,
          }}
          repel={true}
          repelOptions={{
            radius: 80,
            strength: 12,
          }}
        />
      </div>

      {/* ═══════════ TOP-LEFT ETHEREAL EMERALD VOLUMETRIC GRADIENT ═══════════ */}
      {/* 1. Deep Ambient Emerald Atmosphere - Rich saturated corner wash */}
      <div
        className="absolute top-0 left-0 w-[850px] h-[750px] pointer-events-none z-10 opacity-95"
        style={{
          background:
            "radial-gradient(ellipse 75% 65% at 0% 0%, rgba(34, 197, 94, 0.45) 0%, rgba(22, 163, 74, 0.35) 25%, rgba(6, 78, 36, 0.38) 50%, rgba(2, 44, 18, 0.18) 70%, transparent 88%)",
          filter: "blur(36px)",
        }}
      />

      {/* 2. Primary Luminous Emerald Diagonal Shaft (The bright signature beam) */}
      <div
        className="absolute -top-44 -left-36 w-[520px] h-[1400px] pointer-events-none z-10 opacity-90 mix-blend-screen transform -rotate-[34deg] origin-top-left"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(22, 163, 74, 0.15) 15%, rgba(34, 197, 94, 0.65) 35%, rgba(74, 222, 128, 0.95) 50%, rgba(134, 239, 172, 0.75) 55%, rgba(34, 197, 94, 0.6) 65%, rgba(22, 163, 74, 0.25) 85%, transparent 100%)",
          maskImage:
            "linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0.95) 35%, rgba(0,0,0,0.45) 70%, transparent 95%)",
          WebkitMaskImage:
            "linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0.95) 35%, rgba(0,0,0,0.45) 70%, transparent 95%)",
          filter: "blur(18px)",
        }}
      />

      {/* 3. Secondary Parallel Soft Green Ray (Creates the crepuscular dual-beam effect) */}
      <div
        className="absolute -top-28 left-20 w-[360px] h-[1300px] pointer-events-none z-10 opacity-75 mix-blend-screen transform -rotate-[35deg] origin-top-left"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(22, 163, 74, 0.2) 20%, rgba(34, 197, 94, 0.55) 45%, rgba(74, 222, 128, 0.7) 55%, rgba(34, 197, 94, 0.4) 70%, transparent 100%)",
          maskImage:
            "linear-gradient(to bottom, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.8) 40%, rgba(0,0,0,0.3) 75%, transparent 95%)",
          WebkitMaskImage:
            "linear-gradient(to bottom, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.8) 40%, rgba(0,0,0,0.3) 75%, transparent 95%)",
          filter: "blur(20px)",
        }}
      />

      {/* 4. Top-Corner Vibrant Emerald Core Glow */}
      <div
        className="absolute -top-12 -left-12 w-[480px] h-[400px] pointer-events-none z-10 opacity-90"
        style={{
          background:
            "radial-gradient(ellipse 90% 80% at 8% 8%, rgba(74, 222, 128, 0.65) 0%, rgba(34, 197, 94, 0.5) 30%, rgba(20, 83, 45, 0.3) 60%, transparent 85%)",
          filter: "blur(24px)",
        }}
      />

      {/* 5. Top Header Horizontal Ambient Wash */}
      <div
        className="absolute top-0 left-0 w-[780px] h-[220px] pointer-events-none z-10 opacity-80"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 20% 0%, rgba(34, 197, 94, 0.45) 0%, rgba(21, 128, 61, 0.28) 42%, rgba(6, 78, 36, 0.12) 68%, transparent 88%)",
          filter: "blur(32px)",
        }}
      />

      {/* Hero Content Container - Sanctum Sovereign Studio Content */}
      <div className="relative z-20 w-full max-w-7xl mx-auto px-8 sm:px-14 lg:px-20 pointer-events-none">
        <div className="max-w-2xl space-y-5 sm:space-y-6 pointer-events-auto">
          {/* Brand Header with Standalone SanctumLogo */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="flex items-center gap-3.5"
          >
            <SanctumLogo
              size={52}
              color="#22c55e"
              className="shrink-0 drop-shadow-[0_0_24px_rgba(34,197,94,0.55)]"
            />
            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl sm:text-3xl font-extrabold text-white tracking-[0.22em] font-mono">
                  SANCTUM
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold tracking-wider bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30 shadow-sm">
                  v1.0 • SOVEREIGN
                </span>
              </div>
              <span className="mt-0.5 w-fit rounded bg-black/35 px-1.5 py-0.5 text-xs font-mono tracking-wider text-neutral-100 backdrop-blur-sm">
                Local-First Desktop AI Agent Studio
              </span>
            </div>
          </motion.div>

          {/* Pill Badge */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05, ease: "easeOut" }}
            className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-[#0a1e10]/80 border border-[#22c55e]/40 text-neutral-200 text-xs backdrop-blur-md shadow-inner"
          >
            <span className="w-2 h-2 rounded-full bg-[#22c55e] animate-pulse shrink-0" />
            <span className="text-neutral-200 font-medium tracking-tight font-mono text-[11px]">
              Sovereign Loopback Studio • Zero Egress
            </span>
          </motion.div>

          {/* Headline in Editorial Serif */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
            className="max-w-2xl text-3xl sm:text-4xl lg:text-5xl xl:text-[3.5rem] font-serif text-white tracking-tight leading-[1.1] font-normal text-balance"
          >
            Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work
          </motion.h1>

          {/* Subtitle describing Sanctum */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
            className="text-neutral-300 text-sm sm:text-base leading-relaxed max-w-md font-light"
          >
            A local-first desktop agent studio. Run inference strictly over loopback with Ollama and vLLM. Zero data leaves your machine.
          </motion.p>

          {/* Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
            className="flex items-center gap-3 pt-1"
          >
            <motion.button
              whileHover={{ scale: 1.04, boxShadow: "0 0 25px rgba(34,197,94,0.4)" }}
              whileTap={{ scale: 0.98 }}
              onClick={onExploreAI}
              className="px-6 py-2.5 rounded-full bg-[#22c55e] hover:bg-[#16a34a] text-white font-medium text-xs sm:text-sm flex items-center gap-1.5 transition-all cursor-pointer shadow-lg shadow-green-950 font-mono"
            >
              <span>Launch Studio</span>
              <ChevronRight className="w-4 h-4" />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.98 }}
              onClick={onRequestDemo}
              className="px-6 py-2.5 rounded-full bg-[#141414]/80 hover:bg-[#202020] text-neutral-300 hover:text-white font-medium text-xs sm:text-sm border border-white/10 flex items-center gap-1.5 transition-all cursor-pointer backdrop-blur-md font-mono"
            >
              <span>Sign In</span>
              <ChevronRight className="w-4 h-4" />
            </motion.button>
          </motion.div>

          {/* Local Inference Engines */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.45 }}
            className="pt-8 space-y-3"
          >
            <p className="text-[11px] font-mono text-neutral-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-[#22c55e]" />
              <span>100% Loopback Inference Engines</span>
            </p>

            <div className="flex items-center gap-6 sm:gap-8 text-neutral-400 font-medium text-xs font-mono">
              {/* Ollama */}
              <div className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                <Terminal className="w-3.5 h-3.5 text-[#4ade80]" />
                <span className="font-semibold tracking-wide text-neutral-300">Ollama</span>
              </div>

              {/* vLLM */}
              <div className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                <Zap className="w-3.5 h-3.5 text-[#4ade80]" />
                <span className="font-semibold tracking-wide text-neutral-300">vLLM</span>
              </div>

              {/* LM Studio */}
              <div className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                <Cpu className="w-3.5 h-3.5 text-[#4ade80]" />
                <span className="font-semibold tracking-wide text-neutral-300">LM Studio</span>
              </div>

              {/* llama.cpp */}
              <div className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                <Code2 className="w-3.5 h-3.5 text-[#4ade80]" />
                <span className="font-semibold tracking-wide text-neutral-300">llama.cpp</span>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Bottom left minimal icon */}
      <div className="absolute bottom-6 left-6 z-20">
        <div className="w-7 h-7 rounded-full bg-black/70 border border-white/10 flex items-center justify-center text-[10px] text-neutral-400 backdrop-blur-md">
          <span>⬡</span>
        </div>
      </div>
    </section>
  );
};
