"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  LayoutDashboard,
  FolderTree,
  Bot,
  Cpu,
  BookOpen,
  Wrench,
  Lock,
  ShieldCheck,
  TerminalSquare,
  FileCode,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { ScreenType } from "@/types";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectScreen: (screen: ScreenType) => void;
  onSelectFile?: (filePath: string) => void;
}

interface CommandItem {
  id: string;
  title: string;
  category: "Screens" | "Actions" | "Files";
  icon: React.ElementType;
  screen?: ScreenType;
  file?: string;
}

const commands: CommandItem[] = [
  { id: "s-1", title: "Open Overview Dashboard", category: "Screens", icon: LayoutDashboard, screen: "overview" },
  { id: "s-2", title: "Open Workspace Explorer & Editor", category: "Screens", icon: FolderTree, screen: "workspace" },
  { id: "s-3", title: "Open AI Agent Assistant", category: "Screens", icon: Bot, screen: "agent" },
  { id: "s-4", title: "Open Local Models", category: "Screens", icon: Cpu, screen: "models" },
  { id: "s-5", title: "Open Local Knowledge Base (LKB)", category: "Screens", icon: BookOpen, screen: "lkb" },
  { id: "s-6", title: "Open MCP Tools Catalog", category: "Screens", icon: Wrench, screen: "tools" },
  { id: "s-7", title: "Open Sanctum Encrypted Locker", category: "Screens", icon: Lock, screen: "locker" },
  { id: "s-8", title: "Open Security & Loopback Radar", category: "Screens", icon: ShieldCheck, screen: "security" },
  { id: "s-9", title: "Open System & Network Logs", category: "Screens", icon: TerminalSquare, screen: "logs" },
  { id: "f-1", title: "calculator.py (Workspace)", category: "Files", icon: FileCode, screen: "workspace", file: "calculator.py" },
  { id: "f-2", title: "greet.py (Workspace)", category: "Files", icon: FileCode, screen: "workspace", file: "greet.py" },
  { id: "f-3", title: "to.rs (Workspace)", category: "Files", icon: FileCode, screen: "workspace", file: "to.rs" },
];

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectScreen,
  onSelectFile,
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filtered = commands.filter(
    (cmd) =>
      cmd.title.toLowerCase().includes(query.toLowerCase()) ||
      cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        isOpen ? onClose() : undefined;
      }
      if (!isOpen) return;

      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filtered.length) % (filtered.length || 1));
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        handleSelect(filtered[selectedIndex]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filtered, selectedIndex, onClose]);

  const handleSelect = (item: CommandItem) => {
    if (item.screen) {
      onSelectScreen(item.screen);
    }
    if (item.file && onSelectFile) {
      onSelectFile(item.file);
    }
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/75 backdrop-blur-sm"
          />

          {/* Modal box */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="relative w-full max-w-xl bg-[#141414] border border-[#2d2d2d] rounded-xl shadow-2xl overflow-hidden z-10"
          >
            {/* Input bar */}
            <div className="flex items-center px-4 py-3 border-b border-[#252525] gap-3">
              <Search className="w-4 h-4 text-[#76B900]" />
              <input
                type="text"
                autoFocus
                placeholder="Type a command or search workspace..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-transparent text-sm text-white placeholder-neutral-500 focus:outline-none"
              />
              <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-[#202020] text-neutral-400 border border-[#303030] rounded">
                ESC
              </kbd>
            </div>

            {/* Results list */}
            <div className="max-h-80 overflow-y-auto p-2 divide-y divide-[#1e1e1e]">
              {filtered.length === 0 ? (
                <div className="py-8 text-center text-xs text-neutral-500">
                  No matching commands found.
                </div>
              ) : (
                filtered.map((item, idx) => {
                  const Icon = item.icon;
                  const isSelected = idx === selectedIndex;
                  return (
                    <div
                      key={item.id}
                      onClick={() => handleSelect(item)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`px-3 py-2.5 rounded-lg flex items-center justify-between cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-[#202a15] text-[#9ae018]"
                          : "text-neutral-300 hover:bg-[#1a1a1a]"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-7 h-7 rounded flex items-center justify-center ${
                            isSelected ? "bg-[#76B900] text-black" : "bg-[#222] text-neutral-400"
                          }`}
                        >
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <div className="text-xs font-medium text-white">{item.title}</div>
                          <div className="text-[10px] text-neutral-500">{item.category}</div>
                        </div>
                      </div>

                      {isSelected && (
                        <ArrowRight className="w-3.5 h-3.5 text-[#76B900]" />
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-2 bg-[#0f0f0f] border-t border-[#222] flex items-center justify-between text-[11px] text-neutral-500 font-mono">
              <div className="flex items-center gap-2">
                <span>↑↓ Navigate</span>
                <span>•</span>
                <span>↵ Select</span>
              </div>
              <div className="flex items-center gap-1 text-[#76B900]">
                <Sparkles className="w-3 h-3" />
                <span>Sanctum Loopback Assistant</span>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
