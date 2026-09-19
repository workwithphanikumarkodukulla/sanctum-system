"use client";

import React from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { SanctumLogo } from "@/components/ui/sanctum-logo";

interface HeroNavbarProps {
  onOpenLogin: () => void;
  onLaunchStudio?: () => void;
}

export const HeroNavbar: React.FC<HeroNavbarProps> = ({
  onOpenLogin,
  onLaunchStudio,
}) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-40 h-24 px-8 sm:px-14 lg:px-20 flex items-center justify-between select-none bg-black/40 backdrop-blur-2xl border-b border-[#22c55e]/15 shadow-[0_8px_32px_rgba(0,0,0,0.6)]">
      {/* Brand Logo - Sanctum */}
      <div className="flex items-center gap-4">
        <div
          onClick={onLaunchStudio || onOpenLogin}
          className="flex items-center gap-4 text-white tracking-wide group cursor-pointer"
        >
          <SanctumLogo
            size={48}
            color="#22c55e"
            className="shrink-0 transition-transform duration-300 group-hover:scale-105 drop-shadow-[0_0_20px_rgba(34,197,94,0.45)]"
          />
          <div className="flex flex-col">
            <div className="flex items-center gap-2.5">
              <span className="text-2xl sm:text-3xl font-extrabold text-white tracking-[0.2em] font-mono">
                SANCTUM
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold tracking-wider bg-[#22c55e]/20 text-[#22c55e] border border-[#22c55e]/40 shadow-sm">
                v1.0 • SOVEREIGN
              </span>
            </div>
            <span className="text-xs font-mono tracking-wider text-neutral-400">
              Local-First Desktop AI Agent Studio
            </span>
          </div>
        </div>
      </div>

      {/* Center Navigation Links */}
      <nav className="hidden xl:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#121614]/80 border border-white/10 backdrop-blur-md">
        <button
          onClick={onLaunchStudio || onOpenLogin}
          className="px-4 py-2 rounded-full text-xs font-mono font-medium text-neutral-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
        >
          Workspace
        </button>
        <button
          onClick={onLaunchStudio || onOpenLogin}
          className="px-4 py-2 rounded-full text-xs font-mono font-medium text-neutral-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
        >
          Local Models
        </button>
        <button
          onClick={onLaunchStudio || onOpenLogin}
          className="px-4 py-2 rounded-full text-xs font-mono font-medium text-neutral-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
        >
          Crypto Locker
        </button>
        <button
          onClick={onLaunchStudio || onOpenLogin}
          className="px-4 py-2 rounded-full text-xs font-mono font-medium text-neutral-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
        >
          Security Radar
        </button>
      </nav>

      {/* Right Action Area */}
      <div className="flex items-center gap-4">
        {/* Offline Status Badge */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#101913]/90 border border-[#22c55e]/30 text-[#22c55e] text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-[#22c55e] animate-pulse" />
          <span className="font-semibold tracking-wide">100% Loopback Offline</span>
        </div>

        {/* Secondary Sign In */}
        <button
          onClick={onOpenLogin}
          className="px-5 py-2.5 rounded-full text-xs sm:text-sm font-mono font-medium text-neutral-300 hover:text-white hover:bg-white/5 border border-neutral-700/80 transition-all cursor-pointer"
        >
          Sign In
        </button>

        {/* Primary CTA Button */}
        <motion.button
          whileHover={{ scale: 1.04, boxShadow: "0 0 35px rgba(34,197,94,0.5)" }}
          whileTap={{ scale: 0.98 }}
          onClick={onLaunchStudio || onOpenLogin}
          className="px-6 sm:px-7 py-2.5 sm:py-3 rounded-full bg-[#22c55e] hover:bg-[#28df6c] text-black font-bold text-xs sm:text-sm font-mono flex items-center gap-2.5 shadow-[0_0_25px_rgba(34,197,94,0.35)] transition-all cursor-pointer"
        >
          <span>Launch Studio</span>
          <ArrowRight className="w-4 h-4 text-black stroke-[2.5]" />
        </motion.button>
      </div>
    </header>
  );
};
