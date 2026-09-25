"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  FolderTree,
  Bot,
  Cpu,
  BookOpen,
  Wrench,
  Lock,
  ShieldCheck,
  TerminalSquare,
  HardDrive,
} from "lucide-react";
import { ScreenType } from "@/types";

interface ActivityRailProps {
  currentScreen: ScreenType;
  onSelectScreen: (screen: ScreenType) => void;
}

interface RailItem {
  id: ScreenType;
  label: string;
  icon: React.ElementType;
  shortcut: string;
}

const primaryItems: RailItem[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, shortcut: "1" },
  { id: "workspace", label: "Workspace Explorer", icon: FolderTree, shortcut: "2" },
  { id: "agent", label: "Agent Assistant", icon: Bot, shortcut: "3" },
];

const secondaryItems: RailItem[] = [
  { id: "models", label: "Local Models", icon: Cpu, shortcut: "4" },
  { id: "lkb", label: "Local Knowledge Base", icon: BookOpen, shortcut: "5" },
  { id: "tools", label: "MCP Tools Catalog", icon: Wrench, shortcut: "6" },
  { id: "locker", label: "Sanctum Locker", icon: Lock, shortcut: "7" },
  { id: "security", label: "Security & Radar", icon: ShieldCheck, shortcut: "8" },
  { id: "logs", label: "System & Network Logs", icon: TerminalSquare, shortcut: "9" },
];

export const ActivityRail: React.FC<ActivityRailProps> = ({
  currentScreen,
  onSelectScreen,
}) => {
  return (
    <aside className="w-14 bg-rail-theme border-r border-theme flex flex-col items-center py-2 select-none z-20 shrink-0 transition-colors duration-200">
      {/* Primary Navigation */}
      <div className="flex flex-col gap-1 w-full px-1.5">
        {primaryItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentScreen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectScreen(item.id)}
              title={`${item.label} (${item.shortcut})`}
              className={`relative w-full h-10 rounded-md flex items-center justify-center transition-all group cursor-pointer ${
                isActive
                  ? "text-[#76B900] bg-[#76B900]/15 shadow-sm"
                  : "text-muted-theme hover:text-main hover:bg-card-theme"
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="activeRailPill"
                  className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-[#76B900] rounded-r"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                />
              )}
              <Icon className="w-4 h-4 transition-transform group-hover:scale-110" />
            </button>
          );
        })}
      </div>

      <div className="w-8 h-[1px] bg-[var(--border-subtle)] my-2.5 opacity-60" />

      {/* Secondary Navigation */}
      <div className="flex flex-col gap-1 w-full px-1.5 flex-1">
        {secondaryItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentScreen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectScreen(item.id)}
              title={`${item.label} (${item.shortcut})`}
              className={`relative w-full h-10 rounded-md flex items-center justify-center transition-all group cursor-pointer ${
                isActive
                  ? "text-[#76B900] bg-[#76B900]/15 shadow-sm"
                  : "text-muted-theme hover:text-main hover:bg-card-theme"
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="activeRailPill"
                  className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-[#76B900] rounded-r"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                />
              )}
              <Icon className="w-4 h-4 transition-transform group-hover:scale-110" />
            </button>
          );
        })}
      </div>

      {/* Footer indicator */}
      <div className="pt-2 w-full px-2 flex flex-col items-center">
        <div
          title="Host storage: /workspace mounted locally"
          className="w-full h-8 rounded flex items-center justify-center text-muted-theme hover:text-[#76B900] transition-colors cursor-pointer"
        >
          <HardDrive className="w-3.5 h-3.5" />
        </div>
      </div>
    </aside>
  );
};
