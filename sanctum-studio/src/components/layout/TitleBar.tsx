"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Cpu,
  LogOut,
  HardDrive,
  Sun,
  Moon,
} from "lucide-react";
import { SanctumLogo } from "@/components/ui/sanctum-logo";
import { ScreenType, SystemTelemetry } from "@/types";
import { useTheme } from "@/lib/theme";

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
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="h-14 bg-header-theme border-b border-theme flex items-center justify-between px-4 select-none z-30 shrink-0 shadow-sm transition-colors duration-200">
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
          <span className="text-main font-mono text-sm font-bold tracking-[0.18em]">
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
          className="w-full h-8 px-3 rounded-lg bg-input-theme hover:bg-card-theme border border-theme text-xs text-muted-theme flex items-center justify-between transition-colors shadow-inner cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-muted-theme" />
            <span className="text-xs text-muted-theme truncate">
              Search commands, files, tools...
            </span>
          </div>
          <kbd className="px-1.5 py-0.5 bg-surface border border-theme rounded text-[10px] text-muted-theme font-mono">
            ⌘K
          </kbd>
        </motion.button>
      </div>

      {/* Right: Telemetry, Model & Controls */}
      <div className="flex items-center gap-2 text-xs font-mono shrink-0">
        {/* Offline Loopback Badge */}
        <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#76B900]/10 border border-[#76B900]/30 text-[#76B900] text-[11px]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] animate-pulse" />
          <span className="font-semibold">Loopback Active</span>
        </div>

        {/* Active Model Pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface border border-theme text-main text-[11px]">
          <Cpu className="w-3.5 h-3.5 text-[#76B900]" />
          <span className="font-medium">{telemetry.activeModel}</span>
        </div>

        {/* VRAM Telemetry */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface border border-theme text-muted-theme text-[11px]">
          <HardDrive className="w-3 h-3 text-muted-theme" />
          <span>{telemetry.vramUsageGb} / {telemetry.totalVramGb} GB</span>
        </div>

        {/* Theme Mode Toggle Button */}
        <motion.button
          type="button"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.96 }}
          onClick={toggleTheme}
          title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
          aria-label="Toggle Theme Mode"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface border border-theme hover:border-[#76B900]/40 text-main transition-all cursor-pointer shadow-sm group ml-1"
        >
          <div className="relative w-3.5 h-3.5 flex items-center justify-center">
            <AnimatePresence mode="wait" initial={false}>
              {theme === "dark" ? (
                <motion.div
                  key="dark-icon"
                  initial={{ rotate: -90, opacity: 0, scale: 0.7 }}
                  animate={{ rotate: 0, opacity: 1, scale: 1 }}
                  exit={{ rotate: 90, opacity: 0, scale: 0.7 }}
                  transition={{ duration: 0.15 }}
                >
                  <Moon className="w-3.5 h-3.5 text-[#76B900] group-hover:text-[#86d000]" />
                </motion.div>
              ) : (
                <motion.div
                  key="light-icon"
                  initial={{ rotate: 90, opacity: 0, scale: 0.7 }}
                  animate={{ rotate: 0, opacity: 1, scale: 1 }}
                  exit={{ rotate: -90, opacity: 0, scale: 0.7 }}
                  transition={{ duration: 0.15 }}
                >
                  <Sun className="w-3.5 h-3.5 text-amber-500 group-hover:text-amber-600" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <span className="text-[11px] font-mono font-medium tracking-wide">
            {theme === "dark" ? "Dark" : "Light"}
          </span>
        </motion.button>

        {/* Exit to Home */}
        {onExitToHome && (
          <button
            onClick={onExitToHome}
            title="Exit to Landing Page"
            className="p-2 rounded-lg hover:bg-card-theme text-muted-theme hover:text-main transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        )}
      </div>
    </header>
  );
};
