"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { HeroSection } from "@/components/home/HeroSection";
import { LoginModal } from "@/components/home/LoginModal";
import { TitleBar } from "@/components/layout/TitleBar";
import { ActivityRail } from "@/components/layout/ActivityRail";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { OverviewScreen } from "@/components/screens/OverviewScreen";
import { WorkspaceScreen } from "@/components/screens/WorkspaceScreen";
import { AgentScreen } from "@/components/screens/AgentScreen";
import { ModelsScreen } from "@/components/screens/ModelsScreen";
import { LkbScreen } from "@/components/screens/LkbScreen";
import { ToolsScreen } from "@/components/screens/ToolsScreen";
import { LockerScreen } from "@/components/screens/LockerScreen";
import { SecurityScreen } from "@/components/screens/SecurityScreen";
import { LogsScreen } from "@/components/screens/LogsScreen";
import { ScreenType, SystemTelemetry } from "@/types";
import { initialTelemetry } from "@/lib/mockData";
import { fetchSystemTelemetry } from "@/lib/api";
import { ChevronRight, Folder } from "lucide-react";
import CursorRingField from "@/components/ui/cursor-ring-field";

export default function Home() {
  const [currentView, setCurrentView] = useState<"home" | "studio">("home");
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [currentScreen, setCurrentScreen] = useState<ScreenType>("overview");
  const [telemetry, setTelemetry] = useState<SystemTelemetry>(initialTelemetry);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [agentPrompt, setAgentPrompt] = useState("");
  const [activeModel, setActiveModel] = useState("gemma4:latest");

  // Fetch telemetry on load and periodically
  useEffect(() => {
    const loadTelemetry = async () => {
      const data = await fetchSystemTelemetry();
      setTelemetry(data);
      if (data.activeModel) setActiveModel(data.activeModel);
    };

    loadTelemetry();
    const interval = setInterval(loadTelemetry, 8000);
    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcut listener for numbers 1-9 and Cmd+K when in studio
  useEffect(() => {
    if (currentView !== "studio") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }

      const screenMap: Record<string, ScreenType> = {
        "1": "overview",
        "2": "workspace",
        "3": "agent",
        "4": "models",
        "5": "lkb",
        "6": "tools",
        "7": "locker",
        "8": "security",
        "9": "logs",
      };

      if (screenMap[e.key]) {
        e.preventDefault();
        setCurrentScreen(screenMap[e.key]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentView]);

  const handleQuickPrompt = (prompt: string) => {
    setAgentPrompt(prompt);
    setCurrentScreen("agent");
  };

  const handleAskAgentAboutFile = (fileName: string, content: string) => {
    setAgentPrompt(`Please review and audit the local file "${fileName}":\n\n${content.slice(0, 500)}...`);
    setCurrentScreen("agent");
  };

  const screenTitles: Record<ScreenType, string> = {
    overview: "Studio Overview",
    workspace: "Workspace Explorer & Code Editor",
    agent: "Sovereign Agent Chat & Tools",
    models: "Local Models",
    lkb: "Local Knowledge Base (LKB)",
    tools: "MCP Tools Boundary",
    locker: "Sanctum Cryptographic Locker",
    security: "Security Posture & Airgap Radar",
    logs: "System Diagnostics & Network Logs",
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-black text-white select-none">
      <AnimatePresence mode="wait">
        {currentView === "home" ? (
          /* ================= HERO / LANDING PAGE VIEW ================= */
          <motion.div
            key="landing-page"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.4 }}
            className="relative h-full w-full overflow-hidden"
          >
            {/* Hero Section with 3D Vortex Tornado */}
            <HeroSection
              onExploreAI={() => setCurrentView("studio")}
              onRequestDemo={() => setIsLoginModalOpen(true)}
            />

            {/* Login / Authentication Modal */}
            <LoginModal
              isOpen={isLoginModalOpen}
              onClose={() => setIsLoginModalOpen(false)}
              onLoginSuccess={() => {
                setIsLoginModalOpen(false);
                setCurrentView("studio");
              }}
            />
          </motion.div>
        ) : (
          /* ================= STUDIO DASHBOARD VIEW ================= */
          <motion.div
            key="studio-workspace"
            initial={{ opacity: 0, scale: 1.02 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35, ease: "easeInOut" }}
            className="flex flex-col h-full w-full overflow-hidden bg-[#0a0a0a]"
          >
            {/* Title Bar */}
            <TitleBar
              telemetry={telemetry}
              currentScreen={currentScreen}
              onSelectScreen={(screen) => setCurrentScreen(screen)}
              onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
              onExitToHome={() => setCurrentView("home")}
            />

            {/* Main Layout Area */}
            <div className="flex flex-1 overflow-hidden">
              {/* Left Activity Rail */}
              <ActivityRail
                currentScreen={currentScreen}
                onSelectScreen={(screen) => setCurrentScreen(screen)}
              />

              {/* Content Pane */}
              <div className="flex-1 flex flex-col overflow-hidden bg-[#0f0f0f]">
                {/* Breadcrumb strip */}
                <div className="h-9 px-4 bg-[#111111] border-b border-[#202020] flex items-center justify-between text-xs select-none shrink-0">
                  <div className="flex items-center gap-1.5 font-mono text-neutral-400">
                    <span className="text-[#76B900] font-bold">SANCTUM</span>
                    <ChevronRight className="w-3.5 h-3.5 text-neutral-600" />
                    <span className="text-white font-medium">
                      {screenTitles[currentScreen]}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 font-mono text-[11px] text-neutral-400">
                    <button
                      type="button"
                      onClick={() => {
                        if (currentScreen !== "workspace") {
                          setCurrentScreen("workspace");
                        }
                        setTimeout(() => {
                          window.dispatchEvent(new CustomEvent("sanctum:open-folder"));
                        }, 50);
                      }}
                      title="Click to Open/Change Workspace Folder (VS Code Style)"
                      className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#161616] hover:bg-[#202020] border border-[#252525] hover:border-[#76B900]/40 transition-colors cursor-pointer text-neutral-300 hover:text-white"
                    >
                      <Folder className="w-3 h-3 text-[#76B900]" />
                      <span>/workspace</span>
                    </button>
                  </div>
                </div>

                {/* Active Screen Transition */}
                <main className="flex-1 overflow-hidden relative">
                  {/* Cursor Ring Field Background (active on all screens EXCEPT workspace) */}
                  {currentScreen !== "workspace" && (
                    <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden opacity-65">
                      <CursorRingField
                        background="transparent"
                        density={260}
                        dotSize={110}
                        speed={5}
                      />
                    </div>
                  )}

                  <AnimatePresence mode="wait">
                    <motion.div
                      key={currentScreen}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18, ease: "easeInOut" }}
                      className="h-full w-full relative z-10"
                    >
                      {currentScreen === "overview" && (
                        <OverviewScreen
                          telemetry={telemetry}
                          onNavigate={(scr) => setCurrentScreen(scr)}
                          onQuickPrompt={handleQuickPrompt}
                        />
                      )}
                      {currentScreen === "workspace" && (
                        <WorkspaceScreen
                          onAskAgentAboutFile={handleAskAgentAboutFile}
                        />
                      )}
                      {currentScreen === "agent" && (
                        <AgentScreen
                          initialPrompt={agentPrompt}
                          activeModel={activeModel}
                        />
                      )}
                      {currentScreen === "models" && (
                        <ModelsScreen
                          activeModelId={activeModel}
                          onModelChange={(m) => {
                            setActiveModel(m);
                            setTelemetry((prev) => ({ ...prev, activeModel: m }));
                          }}
                        />
                      )}
                      {currentScreen === "lkb" && <LkbScreen />}
                      {currentScreen === "tools" && <ToolsScreen />}
                      {currentScreen === "locker" && <LockerScreen />}
                      {currentScreen === "security" && <SecurityScreen />}
                      {currentScreen === "logs" && <LogsScreen />}
                    </motion.div>
                  </AnimatePresence>
                </main>
              </div>
            </div>

            {/* Global Command Palette (Cmd+K) */}
            <CommandPalette
              isOpen={isCommandPaletteOpen}
              onClose={() => setIsCommandPaletteOpen(false)}
              onSelectScreen={(screen) => setCurrentScreen(screen)}
              onSelectFile={() => {
                setCurrentScreen("workspace");
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
