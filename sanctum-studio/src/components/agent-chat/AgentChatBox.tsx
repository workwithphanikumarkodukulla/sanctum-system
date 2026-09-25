"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { BorderBeam } from "@/components/ui/border-beam";
import { Check, FileCode } from "lucide-react";
import { fetchWorkspaceTree } from "@/lib/api";
import { FileItem } from "@/types";

function extractFilesFromTree(items: FileItem[]): string[] {
  let list: string[] = [];
  for (const item of items) {
    if (!item.isDirectory) {
      if (item.name !== "history.json" && !item.name.startsWith(".")) {
        list.push(item.name);
      }
    } else if (item.children && !item.name.startsWith(".")) {
      list = list.concat(extractFilesFromTree(item.children));
    }
  }
  return list;
}

function AtSignIcon() {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M10.4 5.59963V8.59962C10.4 9.07701 10.5896 9.53485 10.9272 9.87242C11.2648 10.21 11.7226 10.3996 12.2 10.3996C12.6774 10.3996 13.1352 10.21 13.4728 9.87242C13.8104 9.53485 14 9.07701 14 8.59962V7.99962C13.9999 6.64544 13.5417 5.33111 12.7 4.27035C11.8582 3.20958 10.6823 2.46476 9.36359 2.15701C8.04484 1.84925 6.66076 1.99665 5.43641 2.57525C4.21206 3.15384 3.21944 4.1296 2.61996 5.34386C2.02048 6.55812 1.84939 7.93947 2.13451 9.26329C2.41963 10.5871 3.14419 11.7756 4.19038 12.6354C5.23657 13.4952 6.54286 13.9758 7.89684 13.9991C9.25083 14.0224 10.5729 13.587 11.648 12.7636M10.4 7.99962C10.4 9.32511 9.32549 10.3996 8 10.3996C6.67452 10.3996 5.6 9.32511 5.6 7.99962C5.6 6.67414 6.67452 5.59963 8 5.59963C9.32549 5.59963 10.4 6.67414 10.4 7.99962Z"
        stroke="#808388"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg
      aria-hidden="true"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      style={{ transform: "rotate(90deg)" }}
    >
      <path
        d="M7 11L10 8L7 5"
        stroke="#8B9099"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.6"
      />
    </svg>
  );
}

function ArrowUpIcon({ stroke = "#8B8B8B" }: { stroke?: string }) {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M8 12.6667V3.33333M12.6667 8L8 3.33333L3.33333 8"
        stroke={stroke}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const CHIP: React.CSSProperties = {
  borderRadius: 36,
  background: "var(--chatbox-pill, rgba(255,255,255,0.04))",
  boxShadow:
    "inset 0 0 0 1px var(--border-subtle, rgba(255,255,255,0.08))",
};

export interface AgentChatBoxProps {
  onSend: (message: string, options?: { mode?: string; model?: string }) => void;
  isLoading?: boolean;
  activeFile?: string;
  availableFiles?: string[];
  placeholder?: string;
  value?: string;
  onChange?: (val: string) => void;
}

export type AntigravityChatBoxProps = AgentChatBoxProps;

export const AgentChatBox: React.FC<AgentChatBoxProps> = ({
  onSend,
  isLoading = false,
  activeFile,
  availableFiles,
  placeholder = "Build anything...",
  value,
  onChange,
}) => {
  const [internalText, setInternalText] = useState(value || "");
  const text = value !== undefined ? value : internalText;

  const updateText = (newVal: string | ((prev: string) => string)) => {
    const nextVal = typeof newVal === "function" ? newVal(text) : newVal;
    setInternalText(nextVal);
    if (onChange) onChange(nextVal);
  };
  const [agentMode, setAgentMode] = useState("Agent");
  const [routingMode, setRoutingMode] = useState("Auto");
  const [isAgentMenuOpen, setIsAgentMenuOpen] = useState(false);
  const [isRoutingMenuOpen, setIsRoutingMenuOpen] = useState(false);
  const [isFileMenuOpen, setIsFileMenuOpen] = useState(false);
  const [fileSearchQuery, setFileSearchQuery] = useState("");
  const [internalFiles, setInternalFiles] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const loadWorkspaceFiles = useCallback(async () => {
    try {
      const tree = await fetchWorkspaceTree();
      if (Array.isArray(tree)) {
        const extracted = extractFilesFromTree(tree);
        if (extracted.length > 0) {
          setInternalFiles(extracted);
        }
      }
    } catch (e) {
      console.warn("Could not load workspace files in AgentChatBox:", e);
    }
  }, []);

  useEffect(() => {
    if (!availableFiles || availableFiles.length === 0) {
      loadWorkspaceFiles();
    }
  }, [availableFiles, loadWorkspaceFiles]);

  const effectiveFiles =
    availableFiles && availableFiles.length > 0 ? availableFiles : internalFiles;

  // Close open menus on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsFileMenuOpen(false);
        setIsAgentMenuOpen(false);
        setIsRoutingMenuOpen(false);
      }
    };
    if (isFileMenuOpen || isAgentMenuOpen || isRoutingMenuOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
    }
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [isFileMenuOpen, isAgentMenuOpen, isRoutingMenuOpen]);

  useEffect(() => {
    if (value !== undefined) {
      setInternalText(value);
    }
  }, [value]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        140
      )}px`;
    }
  }, [text]);

  const handleSubmit = () => {
    if (!text.trim() || isLoading) return;
    onSend(text.trim(), { mode: agentMode, model: routingMode });
    updateText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleAttachFile = (fileName: string) => {
    updateText((prev) => (prev ? `${prev} @${fileName} ` : `@${fileName} `));
    setIsFileMenuOpen(false);
    setFileSearchQuery("");
    textareaRef.current?.focus();
  };

  // Filter available files based on search
  const filteredFiles = effectiveFiles.filter((f) =>
    f.toLowerCase().includes(fileSearchQuery.toLowerCase().trim())
  );

  return (
    <div ref={containerRef} className="flex items-center justify-center w-full py-1 relative z-30 overflow-visible">
      <div
        className="w-full relative overflow-visible transition-colors duration-200"
        style={{
          borderRadius: 20,
          background: "var(--chatbox-bg, #1d1d1d)",
          boxShadow:
            "0 4px 20px -2px rgba(0,0,0,0.06), inset 0 0 0 1px var(--chatbox-border, rgba(44,47,54,0.52))",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        {/* Isolated BorderBeam: overflow:hidden stays strictly inside this background element */}
        <div className="absolute inset-0 rounded-[20px] pointer-events-none overflow-hidden z-0">
          <BorderBeam size="md" colorVariant="colorful" borderRadius={20} className="w-full h-full">
            <div className="w-full h-full" />
          </BorderBeam>
        </div>

        <div
          style={{
            padding: "8px 10px 10px",
            display: "flex",
            flexDirection: "column",
            minHeight: 126,
            overflow: "visible",
            position: "relative",
            zIndex: 10,
          }}
        >
            {/* Top Row: Context @ Mention Tag */}
            <div className="relative" style={{ zIndex: isFileMenuOpen ? 100 : 20 }}>
              <div
                data-testid="at-mention-button"
                onClick={() => {
                  setIsFileMenuOpen((prev) => {
                    const next = !prev;
                    if (next && (!effectiveFiles || effectiveFiles.length === 0)) {
                      loadWorkspaceFiles();
                    }
                    return next;
                  });
                  setIsAgentMenuOpen(false);
                  setIsRoutingMenuOpen(false);
                }}
                title="Mention context or file (@)"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "fit-content",
                  height: 24,
                  padding: "0 5px",
                  marginLeft: 1,
                  cursor: "pointer",
                  ...CHIP,
                }}
              >
                <AtSignIcon />
              </div>

              {/* @ File Selection Popup (Opens Upwards Above Chatbox) */}
              {isFileMenuOpen && (
                <div
                  data-testid="at-files-popup"
                  className="absolute left-0 bottom-full mb-2.5 w-72 sm:w-80 bg-modal-theme border border-theme rounded-xl p-2 shadow-2xl z-[100] flex flex-col backdrop-blur-2xl"
                  onWheel={(e) => e.stopPropagation()}
                >
                  <div className="px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-theme border-b border-theme flex items-center justify-between shrink-0 select-none">
                    <span>Attach Context</span>
                    <span className="text-muted-theme font-sans text-[10px]">
                      {filteredFiles.length} file{filteredFiles.length === 1 ? "" : "s"}
                    </span>
                  </div>

                  <div className="px-1 pt-1.5 pb-1">
                    <input
                      type="text"
                      value={fileSearchQuery}
                      onChange={(e) => setFileSearchQuery(e.target.value)}
                      placeholder="Search files..."
                      autoFocus
                      className="w-full bg-surface border border-theme rounded-md px-2.5 py-1 text-[11px] font-mono text-main placeholder-muted-theme focus:outline-none focus:border-[#76B900]/40"
                    />
                  </div>

                  <div
                    className="overflow-y-auto max-h-56 p-0.5 space-y-1 scrollbar-thin scrollbar-thumb-white/20"
                    onWheel={(e) => e.stopPropagation()}
                  >
                    {filteredFiles.length === 0 ? (
                      <div className="py-4 text-center text-neutral-500 font-mono text-[11px]">
                        No matching files
                      </div>
                    ) : (
                      filteredFiles.map((file) => (
                        <button
                          key={file}
                          type="button"
                          onClick={() => handleAttachFile(file)}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono text-neutral-300 hover:bg-[#23252c] hover:text-white flex items-center justify-between transition-colors cursor-pointer group"
                        >
                          <span className="flex items-center gap-2 truncate">
                            <FileCode className="w-3.5 h-3.5 text-neutral-400 group-hover:text-[#76B900] shrink-0" />
                            <span className="truncate group-hover:text-[#76B900]">@{file}</span>
                          </span>
                          {activeFile === file && (
                            <span className="text-[10px] text-[#76B900] font-mono shrink-0 ml-1">active</span>
                          )}
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Middle: Text Area ("Build anything...") */}
            <div className="py-2.5 px-1 flex-1 flex items-center">
              <textarea
                ref={textareaRef}
                rows={1}
                wrap="soft"
                value={text}
                onChange={(e) => updateText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                className="w-full bg-transparent text-[13px] text-main placeholder-muted-theme font-sans font-normal leading-[16px] resize-none overflow-x-hidden overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden focus:outline-none"
              />
            </div>

            {/* Bottom Row: Mode Selectors & Send Button */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginTop: "auto",
                position: "relative",
                zIndex: isAgentMenuOpen || isRoutingMenuOpen ? 100 : 10,
              }}
            >
              {/* Agent Mode Pill */}
              <div className="relative" style={{ zIndex: isAgentMenuOpen ? 100 : 1 }}>
                <div
                  data-testid="agent-mode-button"
                  onClick={() => {
                    setIsAgentMenuOpen((prev) => !prev);
                    setIsRoutingMenuOpen(false);
                    setIsFileMenuOpen(false);
                  }}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    height: 24,
                    padding: "0 6px 0 8px",
                    fontSize: 12,
                    lineHeight: "14px",
                    color: "var(--text-main, #caccd2)",
                    marginLeft: 1,
                    cursor: "pointer",
                    ...CHIP,
                  }}
                >
                  {agentMode}
                  <ChevronDownIcon />
                </div>

                {/* Agent Mode Popup (Opens Upwards Above Chatbox) */}
                {isAgentMenuOpen && (
                  <div
                    data-testid="agent-mode-popup"
                    className="absolute left-0 bottom-full mb-2.5 w-56 bg-modal-theme border border-theme rounded-xl p-1.5 shadow-2xl z-[100] flex flex-col backdrop-blur-2xl"
                    onWheel={(e) => e.stopPropagation()}
                  >
                    <div className="px-2 py-1 text-[10px] font-mono uppercase tracking-wider text-muted-theme border-b border-theme mb-1 select-none">
                      Agent Mode
                    </div>
                    <div className="overflow-y-auto max-h-52 p-0.5 space-y-0.5 scrollbar-thin scrollbar-thumb-white/20">
                      {[
                        { mode: "Agent", desc: "Full autonomous execution" },
                        { mode: "Chat", desc: "Conversational Q&A" },
                        { mode: "Review", desc: "Code audit & safety check" },
                      ].map((item) => (
                        <button
                          key={item.mode}
                          type="button"
                          onClick={() => {
                            setAgentMode(item.mode);
                            setIsAgentMenuOpen(false);
                          }}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-main hover:bg-card-theme flex items-center justify-between transition-colors cursor-pointer group"
                        >
                          <div>
                            <div className="font-medium group-hover:text-[#76B900]">{item.mode}</div>
                            <div className="text-[10px] text-muted-theme">{item.desc}</div>
                          </div>
                          {agentMode === item.mode && (
                            <Check className="w-3.5 h-3.5 text-[#76B900] shrink-0" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Auto Routing Pill */}
              <div className="relative" style={{ zIndex: isRoutingMenuOpen ? 100 : 1 }}>
                <div
                  data-testid="routing-mode-button"
                  onClick={() => {
                    setIsRoutingMenuOpen((prev) => !prev);
                    setIsAgentMenuOpen(false);
                    setIsFileMenuOpen(false);
                  }}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    height: 24,
                    padding: "0 6px 0 8px",
                    fontSize: 12,
                    lineHeight: "14px",
                    color: "var(--text-main, #caccd2)",
                    cursor: "pointer",
                    ...CHIP,
                  }}
                >
                  {routingMode}
                  <ChevronDownIcon />
                </div>

                {/* Auto Routing Popup (Opens Upwards Above Chatbox) */}
                {isRoutingMenuOpen && (
                  <div
                    data-testid="routing-mode-popup"
                    className="absolute left-0 bottom-full mb-2.5 w-60 bg-modal-theme border border-theme rounded-xl p-1.5 shadow-2xl z-[100] flex flex-col backdrop-blur-2xl"
                    onWheel={(e) => e.stopPropagation()}
                  >
                    <div className="px-2 py-1 text-[10px] font-mono uppercase tracking-wider text-muted-theme border-b border-theme mb-1 select-none">
                      Model Routing
                    </div>
                    <div className="overflow-y-auto max-h-52 p-0.5 space-y-0.5 scrollbar-thin scrollbar-thumb-white/20">
                      {[
                        { r: "Auto", desc: "Dynamic task routing" },
                        { r: "Gemma 4", desc: "Local sovereign runtime" },
                        { r: "Qwen 2.5", desc: "High-precision coder" },
                      ].map((item) => (
                        <button
                          key={item.r}
                          type="button"
                          onClick={() => {
                            setRoutingMode(item.r);
                            setIsRoutingMenuOpen(false);
                          }}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-main hover:bg-card-theme flex items-center justify-between transition-colors cursor-pointer group"
                        >
                          <div>
                            <div className="font-medium group-hover:text-[#76B900]">{item.r}</div>
                            <div className="text-[10px] text-muted-theme">{item.desc}</div>
                          </div>
                          {routingMode === item.r && (
                            <Check className="w-3.5 h-3.5 text-[#76B900] shrink-0" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Send Button: Dynamic Sanctum Emerald (#76B900) when text is entered */}
              {(() => {
                const hasText = Boolean(text.trim());
                return (
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!hasText || isLoading}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 28,
                      height: 28,
                      marginLeft: "auto",
                      padding: 0,
                      borderRadius: 36,
                      border: hasText
                        ? "1px solid rgba(134, 232, 16, 0.6)"
                        : "1px solid rgba(255, 255, 255, 0.06)",
                      background: hasText ? "#76B900" : "rgba(255, 255, 255, 0.04)",
                      boxShadow: hasText
                        ? "0 0 14px rgba(118, 185, 0, 0.45)"
                        : "inset 0 1px 0 0 rgba(255, 255, 255, 0.05)",
                      cursor: hasText && !isLoading ? "pointer" : "default",
                      transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
                      transform: hasText ? "scale(1.05)" : "scale(1)",
                    }}
                    className={hasText ? "hover:brightness-110 active:scale-95 transition-all" : ""}
                    title={hasText ? "Send prompt (Enter)" : undefined}
                  >
                    {isLoading ? (
                      <span className="w-3 h-3 rounded-full border-2 border-neutral-900 border-t-transparent animate-spin" />
                    ) : (
                      <ArrowUpIcon stroke={hasText ? "#000000" : "#8B8B8B"} />
                    )}
                  </button>
                );
              })()}
            </div>
        </div>
      </div>
    </div>
  );
};

export const AntigravityChatBox = AgentChatBox;
export default AgentChatBox;
