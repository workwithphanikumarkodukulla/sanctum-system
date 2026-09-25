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
  SunMoon,
} from "lucide-react";
import { ScreenType } from "@/types";
import { useTheme } from "@/lib/theme";

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
  action?: "toggle-theme";
}

const commands: CommandItem[] = [
  { id: "a-theme", title: "Toggle Dark / Light Theme", category: "Actions", icon: SunMoon, action: "toggle-theme" },
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
  const { toggleTheme } = useTheme();
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
    if (item.action === "toggle-theme") {
      toggleTheme();
    } else if (item.screen) {
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
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
          />

          {/* Modal box */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="relative w-full max-w-xl bg-modal-theme border border-theme rounded-xl shadow-2xl overflow-hidden z-10"
          >
            {/* Input bar */}
            <div className="flex items-center px-4 py-3 border-b border-theme gap-3">
              <Search className="w-4 h-4 text-[#76B900]" />
              <input
                type="text"
                autoFocus
                placeholder="Type a command or search workspace..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-transparent text-sm text-main placeholder-muted-theme focus:outline-none"
              />
              <span className="text-[10px] font-mono text-muted-theme px-1.5 py-0.5 rounded bg-surface border border-theme">
                ESC to close
              </span>
            </div>

            {/* Results list */}
            <div className="max-h-80 overflow-y-auto p-2 space-y-1">
              {filtered.length === 0 ? (
                <div className="py-8 text-center text-xs text-muted-theme font-mono">
                  No matching commands found.
                </div>
              ) : (
                filtered.map((item, index) => {
                  const Icon = item.icon;
                  const isSelected = index === selectedIndex;
                  return (
                    <div
                      key={item.id}
                      onClick={() => handleSelect(item)}
                      onMouseEnter={() => setSelectedIndex(index)}
                      className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-[#76B900]/15 text-[#76B900]"
                          : "text-main hover:bg-surface"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className="w-4 h-4 shrink-0" />
                        <span className="font-medium">{item.title}</span>
                      </div>
                      <span className="text-[10px] font-mono text-muted-theme px-1.5 py-0.5 rounded bg-surface border border-theme">
                        {item.category}
                      </span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer hints */}
            <div className="px-4 py-2 bg-surface border-t border-theme flex items-center justify-between text-[11px] text-muted-theme font-mono">
              <div className="flex items-center gap-3">
                <span>↑↓ Navigate</span>
                <span>↵ Select</span>
              </div>
              <span className="text-[#76B900]">Sanctum Sovereign Studio</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
