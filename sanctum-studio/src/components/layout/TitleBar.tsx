"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Search,
  Cpu,
  LogOut,
  HardDrive,
} from "lucide-react";
import { SanctumLogo } from "@/components/ui/sanctum-logo";
import { ScreenType, SystemTelemetry } from "@/types";

interface TitleBarProps {
  telemetry: SystemTelemetry;
  currentScreen?: ScreenType;
  onSelectScreen?: (screen: ScreenType) => void;
  onOpenCommandPalette: () => void;
  onExitToHome?: () => void;
}

export const TitleBar: React.FC<TitleBarProps> = ({
  telemetry,
  currentScreen = "workspace",
  onSelectScreen,
  onOpenCommandPalette,
  onExitToHome,
}) => {
  return (
    <header className="h-14 bg-[#0c0e0d] border-b border-[#1f2622] flex items-center justify-between px-4 select-none z-30 shrink-0 shadow-md">
      {/* Left: Brand Identity */}
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={() => onSelectScreen && onSelectScreen("overview")}
          className="flex items-center gap-2.5 group cursor-pointer"
          title="Sanctum Home / Overview"
        >
          <SanctumLogo
            size={26}
            color="#76B900"
            className="shrink-0 transition-transform duration-200 group-hover:scale-105 drop-shadow-[0_0_12px_rgba(118,185,0,0.4)]"
          />
          <span className="text-white font-mono text-sm font-bold tracking-[0.18em]">
            SANCTUM
          </span>
          <span className="hidden sm:inline-block px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold tracking-wider bg-[#76B900]/15 text-[#76B900] border border-[#76B900]/30">
            SOVEREIGN
          </span>
        </button>
      </div>

      {/* Center: Command Palette Trigger */}
      <div className="flex-1 max-w-sm sm:max-w-md mx-3">
        <motion.button
          whileHover={{ scale: 1.01, borderColor: "rgba(118, 185, 0, 0.4)" }}
          whileTap={{ scale: 0.99 }}
          onClick={onOpenCommandPalette}
          className="w-full h-8 px-3 rounded-lg bg-[#141816] hover:bg-[#181f1a] border border-[#232c26] text-xs text-neutral-400 flex items-center justify-between transition-colors shadow-inner cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-neutral-400" />
            <span className="text-xs text-neutral-300 truncate">
              Search commands, files, tools...
            </span>
          </div>
          <kbd className="px-1.5 py-0.5 bg-[#202722] border border-[#2f3832] rounded text-[10px] text-neutral-300 font-mono">
            ⌘K
          </kbd>
        </motion.button>
      </div>

      {/* Right: Telemetry, Model & Controls */}
      <div className="flex items-center gap-2.5 text-xs font-mono shrink-0">
        {/* Offline Loopback Badge */}
        <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#131b14] border border-[#76B900]/30 text-[#76B900] text-[11px]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] animate-pulse" />
          <span className="font-semibold">Loopback Active</span>
        </div>

        {/* Active Model Pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#141816] border border-[#232c26] text-neutral-300 text-[11px]">
          <Cpu className="w-3.5 h-3.5 text-[#76B900]" />
          <span className="font-medium">{telemetry.activeModel}</span>
        </div>

        {/* VRAM Telemetry */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#141816] border border-[#232c26] text-neutral-400 text-[11px]">
          <HardDrive className="w-3 h-3 text-neutral-500" />
          <span>{telemetry.vramUsageGb} / {telemetry.totalVramGb} GB</span>
        </div>

        {/* Exit to Home */}
        {onExitToHome && (
          <button
            onClick={onExitToHome}
            title="Exit to Landing Page"
            className="p-2 rounded-lg hover:bg-[#1a211c] text-neutral-400 hover:text-white transition-colors cursor-pointer ml-1"
          >
            <LogOut className="w-4 h-4" />
          </button>
        )}
      </div>
    </header>
  );
};
