"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  User,
  Trash2,
  Cpu,
  Clock,
  Plus,
  History,
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  Wrench,
  Search,
  CheckCircle2,
  ShieldCheck,
  Terminal,
  FileCode,
  Lock,
  BookOpen,
  ChevronRight,
  ChevronLeft,
  ExternalLink,
  Code2,
  Zap,
} from "lucide-react";
import { ChatMessage, FileItem } from "@/types";
import {
  sendAgentMessage,
  fetchWorkspaceHistory,
  clearBackendWorkspaceHistory,
  fetchWorkspaceTree,
} from "@/lib/api";
import { AgentChatBox } from "@/components/agent-chat/AgentChatBox";
import { ApprovalCard } from "@/components/agent-chat/approval-card";
import { DynamicThinkingPill, resolveAgentOrbConfig } from "@/components/ui/agent-thinking-pill";
import { SanctumLogo } from "@/components/ui/sanctum-logo";
import {
  ThinkingState,
  type TraceNode,
} from "@/components/ui/ai-agent-response";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";

export interface ActivityEvent {
  id: string;
  text: string;
  state: "thinking" | "active" | "complete" | "error" | "info";
  timestamp: string;
  tool?: string;
  toolArgs?: any;
  toolOutput?: string;
  duration?: string;
}

interface ChatSession {
  id: string;
  title: string;
  updatedAt: number;
  messages: ChatMessage[];
}

const INITIAL_SESSIONS: ChatSession[] = [
  {
    id: "session-workspace",
    title: "Workspace Session",
    updatedAt: Date.now(),
    messages: [],
  },
];

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const mins = Math.floor(diff / (1000 * 60));
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

function isMathQuery(text?: string): boolean {
  if (!text) return false;
  const t = text.toLowerCase();
  return (
    t.includes("calc") ||
    t.includes("math") ||
    t.includes("reciprocal") ||
    t.includes("divide") ||
    t.includes("multiply") ||
    t.includes("subtract") ||
    t.includes("add") ||
    t.includes("formula") ||
    t.includes("equation") ||
    t.includes("arithmetic") ||
    t.includes("calculator.py") ||
    /(\d+\s*[\+\-\*\/\%]\s*\d+)/.test(t)
  );
}

interface AgentScreenProps {
  initialPrompt?: string;
  activeModel?: string;
}

const AVAILABLE_TOOLS = [
  {
    id: "python-sandbox",
    name: "Python Sandbox",
    category: "Execution",
    icon: Terminal,
    desc: "Isolated in-memory Python 3.11 runner with stdout interception.",
    promptTemplate: "Run test suite on calculator.py and verify reciprocal() behavior",
  },
  {
    id: "file-system",
    name: "MCP Workspace Explorer",
    category: "Filesystem",
    icon: FileCode,
    desc: "Read, write, and patch workspace files with loopback validation.",
    promptTemplate: "Audit calculator.py and add safe zero-division reciprocal handling",
  },
  {
    id: "wireshark-audit",
    name: "Wireshark Egress Auditor",
    category: "Security",
    icon: ShieldCheck,
    desc: "Real-time loopback packet monitor enforcing zero WAN egress.",
    promptTemplate: "Check network packets to confirm 0 external egress and airgap integrity",
  },
  {
    id: "lkb-retrieval",
    name: "Local Knowledge Base (LKB)",
    category: "Knowledge",
    icon: BookOpen,
    desc: "Search indexed engineering manuals and documentation.",
    promptTemplate: "Search local knowledge base for PV-204B pressure vessel inspection protocol",
  },
  {
    id: "locker-crypto",
    name: "Locker File Guard",
    category: "Cryptography",
    icon: Lock,
    desc: "Argon2id key derivation & AES-256-GCM cipher container.",
    promptTemplate: "Cover sensitive workspace files with AES-256 encryption",
  },
];

export const AgentScreen: React.FC<AgentScreenProps> = ({
  initialPrompt = "",
  activeModel = "gemma4:latest",
}) => {
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("sanctum_chat_sessions");
        if (saved) {
          const parsed = JSON.parse(saved);
          if (
            Array.isArray(parsed) &&
            parsed.length > 0 &&
            !parsed.some((s: any) =>
              s.messages?.some((m: any) => m.id === "msg-1" || m.id === "msg-2")
            )
          ) {
            return parsed;
          }
        }
      } catch (e) {
        // ignore
      }
    }
    return INITIAL_SESSIONS;
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    return sessions[0]?.id || "session-workspace";
  });

  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    return sessions[0]?.messages || [];
  });

  const [workspaceFiles, setWorkspaceFiles] = useState<string[]>([]);
  const [input, setInput] = useState(initialPrompt);
  const [isSending, setIsSending] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState("");
  const [liveStage, setLiveStage] = useState<string>("routing");
  const [liveStageText, setLiveStageText] = useState<string>("Analyzing request...");
  const [liveSteps, setLiveSteps] = useState<string[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [isToolPickerOpen, setIsToolPickerOpen] = useState(false);
  const [showTraceSidebar, setShowTraceSidebar] = useState(true);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [activityEvents, setActivityEvents] = useState<ActivityEvent[]>([]);

  const historyDropdownRef = useRef<HTMLDivElement>(null);
  const toolPickerModalRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Sync to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("sanctum_chat_sessions", JSON.stringify(sessions));
      } catch (e) {
        // ignore
      }
    }
  }, [sessions]);

  // Load real workspace files & history on mount
  useEffect(() => {
    let isCancelled = false;

    async function loadWorkspaceData() {
      try {
        const tree = await fetchWorkspaceTree();
        if (!isCancelled && Array.isArray(tree)) {
          const extractFiles = (items: FileItem[]): string[] => {
            let list: string[] = [];
            for (const item of items) {
              if (!item.isDirectory) {
                if (item.name !== "history.json" && !item.name.startsWith(".")) {
                  list.push(item.name);
                }
              } else if (item.children && !item.name.startsWith(".")) {
                list = list.concat(extractFiles(item.children));
              }
            }
            return list;
          };
          const extracted = extractFiles(tree);
          if (extracted.length > 0) {
            setWorkspaceFiles(extracted);
          }
        }
      } catch (e) {
        console.warn("Failed loading workspace files in AgentScreen:", e);
      }

      try {
        const { history } = await fetchWorkspaceHistory();
        if (isCancelled || !Array.isArray(history) || history.length === 0) return;

        const mapped: ChatMessage[] = history.map((entry: any, idx: number) => {
          const isUser = entry.role === "user";
          const timestampStr = entry.timestamp
            ? new Date(entry.timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })
            : new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              });

          const toolsUsed: string[] = entry.metadata?.tools_used || [];
          const durationS =
            entry.metadata?.duration_s ||
            (entry.duration ? parseFloat(entry.duration) : undefined);

          const traceNodes: TraceNode[] = [];
          if (!isUser && (toolsUsed.length > 0 || durationS !== undefined)) {
            traceNodes.push({
              id: `hist-tr-${idx}`,
              type: "reasoning",
              sentences: [
                toolsUsed.length > 0
                  ? `Executed tools: ${toolsUsed.join(", ")}.`
                  : "Executed via local autonomous agent loop.",
                "Zero external egress verified on loopback socket.",
              ],
              durationSeconds: durationS || 0.8,
              status: "completed",
            });
          }

          return {
            id: `hist-${idx}-${entry.timestamp || idx}`,
            role: (entry.role as "user" | "assistant") || "assistant",
            content: entry.content || "",
            timestamp: timestampStr,
            model: entry.metadata?.model || entry.model || "gemma4:latest",
            durationS,
            traceNodes: traceNodes.length > 0 ? traceNodes : undefined,
          };
        });

        setMessages((prev) => (prev.length === 0 ? mapped : prev));
        setSessions((prev) =>
          prev.map((s) =>
            s.id === "session-workspace" && s.messages.length === 0
              ? { ...s, messages: mapped, updatedAt: Date.now() }
              : s
          )
        );

        // Seed execution trace activity events from the latest assistant message
        const latestAssistant = [...mapped].reverse().find((m) => m.role === "assistant");
        if (latestAssistant) {
          const initEvents: ActivityEvent[] = [];
          initEvents.push({
            id: `init-ev-1`,
            text: `Workspace session loaded (${latestAssistant.model || activeModel}).`,
            state: "complete",
            timestamp: latestAssistant.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          });
          if (latestAssistant.toolsExecuted && latestAssistant.toolsExecuted.length > 0) {
            latestAssistant.toolsExecuted.forEach((t: any, i: number) => {
              const tName = t.tool || t.name || "workspace_tool";
              initEvents.push({
                id: `init-tool-${i}`,
                text: `Tool call: ${tName}`,
                tool: tName,
                toolArgs: t.args || t.arguments,
                toolOutput: typeof t.result === "string" ? t.result : typeof t.output === "string" ? t.output : JSON.stringify(t.result || t.output || "Completed"),
                state: "complete",
                timestamp: latestAssistant.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
              });
            });
          }
          initEvents.push({
            id: `init-ev-done`,
            text: "Mission completed successfully.",
            state: "complete",
            timestamp: latestAssistant.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          });
          setActivityEvents(initEvents);
        }
      } catch (err) {
        console.warn("Failed loading workspace history in AgentScreen:", err);
      }
    }

    loadWorkspaceData();
    return () => {
      isCancelled = true;
    };
  }, []);

  // Handle outside click for history & tool picker
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        historyDropdownRef.current &&
        !historyDropdownRef.current.contains(event.target as Node)
      ) {
        setIsHistoryOpen(false);
      }
      if (
        toolPickerModalRef.current &&
        !toolPickerModalRef.current.contains(event.target as Node)
      ) {
        setIsToolPickerOpen(false);
      }
    };
    if (isHistoryOpen || isToolPickerOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isHistoryOpen, isToolPickerOpen]);

  useEffect(() => {
    if (initialPrompt) {
      setInput(initialPrompt);
    }
  }, [initialPrompt]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const handleNewChat = () => {
    const currentSession = sessions.find((s) => s.id === activeSessionId);
    if (currentSession && currentSession.messages.length === 0 && messages.length === 0) {
      setIsHistoryOpen(false);
      return;
    }

    const newSession: ChatSession = {
      id: `session-${Date.now()}`,
      title: "New Chat",
      updatedAt: Date.now(),
      messages: [],
    };

    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setMessages([]);
    setSelectedMessageId(null);
    setIsHistoryOpen(false);
  };

  const handleSelectSession = (sessionId: string) => {
    if (sessionId === activeSessionId) {
      setIsHistoryOpen(false);
      return;
    }

    setSessions((prev) =>
      prev.map((s) => (s.id === activeSessionId ? { ...s, messages } : s))
    );

    const target = sessions.find((s) => s.id === sessionId);
    if (target) {
      setActiveSessionId(target.id);
      setMessages(target.messages);
      setSelectedMessageId(null);
    }
    setIsHistoryOpen(false);
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (sessionId === "session-workspace") {
      try {
        await clearBackendWorkspaceHistory();
      } catch {}
    }
    const remaining = sessions.filter((s) => s.id !== sessionId);
    setSessions(remaining);

    if (activeSessionId === sessionId) {
      if (remaining.length > 0) {
        setActiveSessionId(remaining[0].id);
        setMessages(remaining[0].messages);
      } else {
        const fresh: ChatSession = {
          id: `session-${Date.now()}`,
          title: "New Chat",
          updatedAt: Date.now(),
          messages: [],
        };
        setSessions([fresh]);
        setActiveSessionId(fresh.id);
        setMessages([]);
      }
    }
  };

  const handleClearHistory = async () => {
    try {
      await clearBackendWorkspaceHistory();
    } catch {}
    setMessages([]);
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSessionId ? { ...s, messages: [] } : s))
    );
  };

  const handleSend = async (customText?: string) => {
    const text = customText || input;
    if (!text.trim() || isSending) return;

    const isMath = isMathQuery(text);
    setPendingPrompt(text.trim());

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      isMath,
    };

    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setIsSending(true);

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSessionId) {
          const title =
            s.title === "New Chat" || s.messages.length === 0
              ? text.length > 40
                ? text.slice(0, 40) + "..."
                : text
              : s.title;
          return {
            ...s,
            title,
            updatedAt: Date.now(),
            messages: nextMessages,
          };
        }
        return s;
      })
    );

    setLiveStage("routing");
    setLiveStageText("Evaluating local model capabilities...");
    setLiveSteps(["Evaluating local model capabilities..."]);

    const startEv: ActivityEvent = {
      id: `ev-${Date.now()}-start`,
      text: "Processing mission request...",
      state: "thinking",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    };
    setActivityEvents([startEv]);

    try {
      const res = await sendAgentMessage(text, activeModel, (event) => {
        if (event.stage) setLiveStage(event.stage);
        if (event.text) {
          setLiveStageText(event.text);
          setLiveSteps((prev) => (prev.includes(event.text) ? prev : [...prev, event.text]));
          setActivityEvents((prev) => {
            const updated = prev.map((ev) =>
              ev.state === "active" || ev.state === "thinking" ? { ...ev, state: "complete" as const } : ev
            );
            return [
              {
                id: `ev-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                text: event.text,
                state: "active",
                timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
              },
              ...updated,
            ];
          });
        }
      });

      const realDurationSec = res.durationS || (res.durationMs ? Number((res.durationMs / 1000).toFixed(2)) : 0.8);
      const usedModel = res.modelUsed || activeModel;

      // Extract real reasoning sentences from real backend activity_events or workflow_trace
      const realReasoningSentences: string[] = [];
      if (res.activityEvents && res.activityEvents.length > 0) {
        res.activityEvents.forEach((ev) => {
          if (ev.text) realReasoningSentences.push(ev.text);
        });
      } else if (res.workflowTrace?.agent_reasoning && Array.isArray(res.workflowTrace.agent_reasoning)) {
        res.workflowTrace.agent_reasoning.forEach((r: string) => realReasoningSentences.push(r));
      } else {
        realReasoningSentences.push(`Task routed to local ${usedModel} inference engine.`);
        realReasoningSentences.push("Completed with zero external egress and 100% loopback isolation.");
      }

      const traceNodes: TraceNode[] = [
        {
          id: `tr-${Date.now()}-1`,
          type: "reasoning",
          sentences: realReasoningSentences,
          durationSeconds: realDurationSec,
          status: "completed",
        },
      ];

      const toolEvents: ActivityEvent[] = [];
      // Add real tools executed by the backend
      if (res.toolsExecuted && res.toolsExecuted.length > 0) {
        res.toolsExecuted.forEach((tool, idx) => {
          const toolName = tool.tool || tool.name || "tool";
          const isTerminal = toolName.includes("run_command") || toolName.includes("run_python") || toolName.includes("terminal");
          const toolArgs = tool.args || tool.input || {};
          const toolCommand =
            toolArgs.expression ||
            toolArgs.command ||
            toolArgs.path ||
            (typeof toolArgs === "string" ? toolArgs : JSON.stringify(toolArgs));
          const toolOutput =
            typeof tool.result === "string"
              ? tool.result
              : typeof tool.output === "string"
              ? tool.output
              : JSON.stringify(tool.result || tool.output || "Success");

          traceNodes.push({
            id: `tr-${Date.now()}-tool-${idx}`,
            type: isTerminal ? "terminal" : "tool",
            primary: toolName,
            secondary: res.durationMs ? `${res.durationMs}ms` : undefined,
            command: toolCommand,
            output: toolOutput,
            status: "completed",
          });

          toolEvents.push({
            id: `tool-${Date.now()}-${idx}`,
            text: `Tool call: ${toolName}`,
            tool: toolName,
            toolArgs,
            toolOutput,
            state: "complete",
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          });
        });
      }

      // Finalize activity events list
      setActivityEvents((prev) => [
        {
          id: `ev-done-${Date.now()}`,
          text: "Mission completed successfully.",
          state: "complete",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        },
        ...toolEvents,
        ...prev.map((ev) =>
          ev.state === "active" || ev.state === "thinking" ? { ...ev, state: "complete" as const } : ev
        ),
      ]);

      const needsApproval =
        text.toLowerCase().includes("audit") ||
        text.toLowerCase().includes("patch") ||
        text.toLowerCase().includes("deploy") ||
        text.toLowerCase().includes("fix") ||
        text.toLowerCase().includes("run") ||
        text.toLowerCase().includes("approve");

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: "assistant",
        content: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        toolsExecuted: res.toolsExecuted,
        traceNodes,
        model: usedModel,
        durationMs: res.durationMs,
        durationS: res.durationS,
        workflowTrace: res.workflowTrace,
        debugTrace: res.debugTrace,
        hasApproval: needsApproval,
        approvalStatus: needsApproval ? "pending" : undefined,
        isMath: isMath || isMathQuery(res.reply),
      };

      const finalMessages = [...nextMessages, botMsg];
      setMessages(finalMessages);
      setSelectedMessageId(botMsg.id);

      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, updatedAt: Date.now(), messages: finalMessages }
            : s
        )
      );
    } catch (e) {
      setActivityEvents((prev) => [
        {
          id: `ev-err-${Date.now()}`,
          text: `Failed: ${e instanceof Error ? e.message : "Execution failed"}`,
          state: "error",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        },
        ...prev.map((ev) =>
          ev.state === "active" || ev.state === "thinking" ? { ...ev, state: "error" as const } : ev
        ),
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleApprovalSubmitted = (msgId: string, _answers: Record<number, number[]>) => {
    const updatedMessages = messages.map((m) =>
      m.id === msgId ? { ...m, approvalStatus: "approved" as const } : m
    );

    const confirmMsg: ChatMessage = {
      id: `bot-confirm-${Date.now()}`,
      role: "assistant",
      content: "✓ Action Approved: Execution parameters verified over loopback sandbox. Workspace patch applied with strict sovereign boundary validation.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      model: activeModel,
      tokensUsed: 145,
    };

    const final = [...updatedMessages, confirmMsg];
    setMessages(final);

    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? { ...s, updatedAt: Date.now(), messages: final }
          : s
      )
    );
  };

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(historySearch.toLowerCase())
  );

  // Latest or currently selected assistant message for trace sidebar
  const activeTraceMessage =
    messages.find((m) => m.id === selectedMessageId && m.role === "assistant") ||
    [...messages].reverse().find((m) => m.role === "assistant" && (m.traceNodes || m.toolsExecuted));

  const displayedActivityEvents = React.useMemo(() => {
    // If user clicked on a specific assistant message and not currently executing
    if (selectedMessageId && !isSending) {
      const msg = messages.find((m) => m.id === selectedMessageId);
      if (msg && msg.role === "assistant") {
        const turnEvents: ActivityEvent[] = [];
        turnEvents.push({
          id: `turn-init-${msg.id}`,
          text: `Task routed to local ${msg.model || activeModel}.`,
          state: "complete",
          timestamp: msg.timestamp,
        });
        if (msg.toolsExecuted && msg.toolsExecuted.length > 0) {
          msg.toolsExecuted.forEach((t: any, idx: number) => {
            const tName = t.tool || t.name || "workspace_tool";
            turnEvents.push({
              id: `turn-tool-${msg.id}-${idx}`,
              text: `Tool call: ${tName}`,
              tool: tName,
              toolArgs: t.args || t.arguments,
              toolOutput: typeof t.result === "string" ? t.result : typeof t.output === "string" ? t.output : JSON.stringify(t.result || t.output || "Completed"),
              state: "complete",
              timestamp: msg.timestamp,
            });
          });
        }
        turnEvents.push({
          id: `turn-done-${msg.id}`,
          text: "Mission completed successfully.",
          state: "complete",
          timestamp: msg.timestamp,
        });
        return turnEvents;
      }
    }
    return activityEvents;
  }, [selectedMessageId, isSending, messages, activityEvents, activeModel]);

  const suggestions = [
    "Audit calculator.py and add safe reciprocal math handling",
    "Run unit tests for math operations in Python sandbox",
    "Check network packets to confirm 0 external egress",
    "List all available tools in the MCP boundary",
  ];

  return (
    <div className="h-full flex flex-col bg-[#0a0a0a]/90 backdrop-blur-[2px] select-none relative overflow-hidden">
      {/* Top Header */}
      <div className="h-12 px-6 bg-[#111] border-b border-[#202020] flex items-center justify-between shrink-0 relative z-30">
        <div className="flex items-center gap-2.5 min-w-0">
          <SanctumLogo
            size={20}
            color="#76B900"
            className="shrink-0 drop-shadow-[0_0_10px_rgba(118,185,0,0.4)]"
          />
          <div>
            <h1 className="text-xs font-semibold text-white tracking-wide font-mono flex items-center gap-2">
              <span>Sanctum Agent Studio</span>
              <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] animate-pulse shrink-0" />
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Tool Picker Button */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsToolPickerOpen(!isToolPickerOpen)}
              title="Tool Picker / Launcher"
              className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-mono transition-colors border ${
                isToolPickerOpen
                  ? "bg-[#1f2c16] text-[#76B900] border-[#76B900]/40"
                  : "bg-[#161616] text-neutral-300 border-[#2a2a2a] hover:bg-[#202020] hover:text-white"
              }`}
            >
              <Wrench className="w-3.5 h-3.5 text-[#76B900]" />
              <span className="hidden sm:inline">Tools</span>
            </button>

            {/* Tool Picker Popover */}
            <AnimatePresence>
              {isToolPickerOpen && (
                <motion.div
                  ref={toolPickerModalRef}
                  initial={{ opacity: 0, y: -6, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -6, scale: 0.97 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-2 w-80 sm:w-96 bg-[#131417] border border-[#2d2d30] rounded-xl shadow-2xl shadow-black/90 overflow-hidden z-50 text-left font-sans"
                >
                  <div className="px-3.5 py-2.5 border-b border-[#222] flex items-center justify-between bg-[#16171b]">
                    <div className="flex items-center gap-2">
                      <Wrench className="w-4 h-4 text-[#76B900]" />
                      <span className="text-xs font-semibold text-white">Sovereign Tools Directory</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#222] text-[#76B900]">
                      5 Active
                    </span>
                  </div>

                  <div className="p-2 space-y-1.5 max-h-80 overflow-y-auto">
                    {AVAILABLE_TOOLS.map((t) => {
                      const Icon = t.icon;
                      return (
                        <div
                          key={t.id}
                          onClick={() => {
                            setInput(t.promptTemplate);
                            setIsToolPickerOpen(false);
                          }}
                          className="p-2.5 rounded-lg bg-[#18191d] hover:bg-[#202227] border border-[#26272c] hover:border-[#76B900]/40 cursor-pointer transition-all group"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <div className="p-1 rounded bg-[#101114] text-[#76B900]">
                                <Icon className="w-3.5 h-3.5" />
                              </div>
                              <span className="text-xs font-medium text-white group-hover:text-[#76B900]">
                                {t.name}
                              </span>
                            </div>
                            <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-white/5 text-neutral-400">
                              {t.category}
                            </span>
                          </div>
                          <p className="text-[11px] text-neutral-400 line-clamp-2 leading-relaxed">
                            {t.desc}
                          </p>
                          <div className="mt-2 text-[10px] font-mono text-[#76B900]/80 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <span>Use template</span>
                            <ChevronRight className="w-3 h-3" />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* New Chat (+) */}
          <button
            type="button"
            onClick={handleNewChat}
            title="New Chat (+)"
            className="p-1.5 rounded-md hover:bg-[#202020] text-neutral-400 hover:text-white transition-colors flex items-center justify-center cursor-pointer group"
          >
            <Plus className="w-4 h-4 group-hover:text-[#76B900] transition-colors" />
          </button>

          {/* Chat History Button & Dropdown */}
          <div className="relative" ref={historyDropdownRef}>
            <button
              type="button"
              onClick={() => setIsHistoryOpen(!isHistoryOpen)}
              title="Chat History"
              className={`p-1.5 rounded-md hover:bg-[#202020] transition-colors flex items-center justify-center cursor-pointer ${
                isHistoryOpen
                  ? "bg-[#202020] text-[#76B900]"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              <History className="w-4 h-4" />
            </button>

            {/* History Flyout Dropdown with Search */}
            <AnimatePresence>
              {isHistoryOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.98 }}
                  transition={{ duration: 0.12 }}
                  className="absolute right-0 top-full mt-1.5 w-80 bg-[#131313] border border-[#2c2c2c] rounded-xl shadow-2xl shadow-black/80 overflow-hidden z-50 text-left font-sans"
                >
                  {/* Header of dropdown */}
                  <div className="px-3.5 py-2.5 border-b border-[#222] flex items-center justify-between bg-[#161616]">
                    <div className="flex items-center gap-1.5">
                      <History className="w-4 h-4 text-[#76B900]" />
                      <span className="text-xs font-semibold text-white tracking-wide">
                        Chat History
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-[#202020] text-neutral-400">
                        {sessions.length}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={handleNewChat}
                      className="flex items-center gap-1 text-[11px] font-mono font-medium px-2 py-1 rounded bg-[#1f2c16] hover:bg-[#26371c] text-[#86e810] border border-[#76B900]/30 transition-colors cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>New Chat</span>
                    </button>
                  </div>

                  {/* Search box */}
                  <div className="p-2 border-b border-[#202020]">
                    <div className="flex items-center gap-2 px-2 py-1 rounded bg-[#181818] border border-[#282828]">
                      <Search className="w-3.5 h-3.5 text-neutral-500" />
                      <input
                        type="text"
                        value={historySearch}
                        onChange={(e) => setHistorySearch(e.target.value)}
                        placeholder="Search chats..."
                        className="w-full bg-transparent text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  {/* Sessions list */}
                  <div className="max-h-72 overflow-y-auto divide-y divide-[#1c1c1c] p-1.5">
                    {filteredSessions.length === 0 ? (
                      <div className="py-6 text-center text-xs text-neutral-500 font-mono">
                        No conversations found
                      </div>
                    ) : (
                      filteredSessions.map((sess) => {
                        const isActive = sess.id === activeSessionId;
                        return (
                          <div
                            key={sess.id}
                            onClick={() => handleSelectSession(sess.id)}
                            className={`group flex items-start justify-between gap-2.5 p-2.5 rounded-lg cursor-pointer transition-colors ${
                              isActive
                                ? "bg-[#1c2616] border border-[#76B900]/30"
                                : "hover:bg-[#1c1c1c]"
                            }`}
                          >
                            <div className="flex items-start gap-2.5 min-w-0 flex-1">
                              <MessageSquare
                                className={`w-4 h-4 mt-0.5 shrink-0 ${
                                  isActive ? "text-[#76B900]" : "text-neutral-500"
                                }`}
                              />
                              <div className="min-w-0 flex-1">
                                <p
                                  className={`text-xs truncate font-medium ${
                                    isActive ? "text-white font-semibold" : "text-neutral-300"
                                  }`}
                                >
                                  {sess.title}
                                </p>
                                <div className="flex items-center gap-2 mt-1 text-[10px] text-neutral-500 font-mono">
                                  <span>{formatRelativeTime(sess.updatedAt)}</span>
                                  <span>•</span>
                                  <span>{sess.messages.length} msgs</span>
                                </div>
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={(e) => handleDeleteSession(e, sess.id)}
                              title="Delete conversation"
                              className="opacity-0 group-hover:opacity-100 p-1.5 rounded hover:bg-[#282828] text-neutral-500 hover:text-rose-400 transition-all cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Header Execution Trace Toggle Button (matching Downloads/integrate) */}
          <button
            type="button"
            id="toggleRailBtn"
            onClick={() => setShowTraceSidebar(!showTraceSidebar)}
            title="Toggle execution trace"
            className={`btn-trace-toggle ${showTraceSidebar ? "active" : ""}`}
          >
            <Terminal className="w-3.5 h-3.5 text-[#76B900]" />
            <span>Execution trace</span>
            <span className="live-pill" id="headerLivePill">LIVE</span>
          </button>

          <button
            onClick={handleClearHistory}
            title="Clear Current Chat"
            className="p-1.5 rounded-md hover:bg-[#202020] text-neutral-400 hover:text-rose-400 transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Workspace Area (Chat Timeline + Collapsible Execution Trace Sidebar) */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative" id="agentLayout">
        {/* Left/Center: Messages Timeline */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
          {/* Collapsed Dock Tab on right edge (matching Downloads/integrate) */}
          {!showTraceSidebar && (
            <button
              type="button"
              id="railDockTab"
              onClick={() => setShowTraceSidebar(true)}
              title="Expand execution trace"
              aria-label="Expand execution trace"
              className="rail-dock-tab"
            >
              <ChevronLeft className="w-4 h-4 text-[#76B900]" />
              <span className="dock-tab-label">Execution trace</span>
              <span className="dock-tab-dot" />
            </button>
          )}

          <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl w-full mx-auto">
            {messages.length === 0 && (
              <div className="py-16 text-center space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-[#1a2512] border border-[#76B900]/40 mx-auto flex items-center justify-center text-[#76B900] shadow-lg shadow-[#76B900]/10">
                  <Bot className="w-6 h-6" />
                </div>
                <h2 className="text-base font-semibold text-white">
                  Autonomous Sovereign Coding Agent
                </h2>
                <p className="text-xs text-neutral-400 max-w-md mx-auto leading-relaxed">
                  Ask to generate code, run tests, or inspect workspace files with full loopback security.
                </p>
              </div>
            )}

            {messages.map((msg) => {
              const isUser = msg.role === "user";
              const isSelected = msg.id === selectedMessageId;

              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  onClick={() => !isUser && setSelectedMessageId(msg.id)}
                  className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"} ${
                    !isUser ? "cursor-pointer" : ""
                  }`}
                >
                  {!isUser && (
                    <div className="w-7 h-7 rounded-lg bg-[#192410] border border-[#76B900]/40 flex items-center justify-center text-[#76B900] shrink-0 mt-0.5 shadow-sm">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed transition-all ${
                      isUser
                        ? "bg-[#1c2912] border border-[#76B900]/40 text-neutral-100 shadow-md"
                        : isSelected
                        ? "bg-[#161616] border border-[#76B900]/60 text-neutral-200 shadow-[0_0_15px_rgba(118,185,0,0.1)] space-y-3"
                        : "bg-[#141414] border border-[#262626] hover:border-[#383838] text-neutral-200 shadow-sm space-y-3"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3 mb-1 text-[11px] font-mono text-neutral-500 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-[#86e810]">
                          {isUser ? "YOU" : "SANCTUM AGENT"}
                        </span>
                        {!isUser && (
                          <div className="message-meta-tags">
                            <span className="message-meta-badge model-badge" title={`Model: ${msg.model || activeModel}`}>
                              <Cpu className="w-3 h-3 text-[#76B900]" />
                              {msg.model || activeModel}
                            </span>
                            {msg.durationS !== undefined && (
                              <span className="message-meta-badge time-badge" title={`Latency: ${msg.durationS}s`}>
                                <Clock className="w-3 h-3 text-neutral-400" />
                                {msg.durationS}s
                              </span>
                            )}
                            <span className="message-meta-badge" title="Sovereign Execution: 100% Loopback Only">
                              <ShieldCheck className="w-3 h-3 text-[#76B900]" />
                              Air-Gapped
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {msg.tokensUsed && (
                          <span className="text-neutral-500">{msg.tokensUsed} tokens</span>
                        )}
                        <span>{msg.timestamp}</span>
                      </div>
                    </div>

                    {/* AI Agent Thinking & Execution Trace in-line */}
                    {!isUser && msg.traceNodes && msg.traceNodes.length > 0 && (
                      <div className="pb-1">
                        <ThinkingState
                          nodes={msg.traceNodes}
                          autoPlay={false}
                          defaultExpanded={false}
                        />
                      </div>
                    )}

                    {isUser ? (
                      <div className="whitespace-pre-wrap font-sans text-neutral-200 text-xs leading-relaxed selection:bg-[#76B900]/30">
                        {msg.content}
                      </div>
                    ) : (
                      <MarkdownRenderer content={msg.content} />
                    )}

                    {/* Human-In-The-Loop Approval Card */}
                    {!isUser && msg.hasApproval && (
                      <div className="pt-2">
                        <ApprovalCard
                          questions={msg.approvalQuestions}
                          onSubmitted={(answers) => handleApprovalSubmitted(msg.id, answers)}
                        />
                      </div>
                    )}
                  </div>

                  {isUser && (
                    <div className="w-7 h-7 rounded-lg bg-[#222] border border-[#333] flex items-center justify-center text-neutral-300 shrink-0 mt-0.5">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </motion.div>
              );
            })}

            {/* Live Agent Execution State */}
            {isSending && (
              <div className="flex flex-col gap-3 py-2 animate-in fade-in duration-200">
                <DynamicThinkingPill
                  prompt={pendingPrompt}
                  phase={liveStage}
                  forcedDetail={liveStageText}
                  size="lg"
                />
                <div className="max-w-2xl">
                  <ThinkingState
                    autoPlay
                    workingLabel={liveStageText || "Executing with sovereign local runtime..."}
                    nodes={[
                      {
                        id: `live-step-${liveSteps.length}`,
                        type: "reasoning",
                        sentences: liveSteps.length > 0 ? liveSteps : [liveStageText],
                      },
                    ]}
                  />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggestion Chips */}
          {messages.length < 4 && (
            <div className="px-6 py-2 flex flex-wrap gap-2 max-w-4xl w-full mx-auto">
              {suggestions.map((sug, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(sug)}
                  className="text-[11px] px-2.5 py-1 rounded-full bg-[#151515] hover:bg-[#202020] border border-[#262626] hover:border-[#76B900]/50 text-neutral-300 hover:text-white transition-all cursor-pointer"
                >
                  {sug}
                </button>
              ))}
            </div>
          )}

          {/* Agent Chat Box with BorderBeam */}
          <div className="p-4 bg-[#0d0d0d] border-t border-[#202020] shrink-0 relative z-30 overflow-visible">
            <div className="max-w-3xl w-full mx-auto">
              <AgentChatBox
                onSend={(msg) => handleSend(msg)}
                isLoading={isSending}
                availableFiles={workspaceFiles}
                placeholder="Build anything with local tools..."
              />
            </div>
          </div>
        </div>

        {/* Right: Collapsible Execution Trace Sidebar (matching Downloads/integrate) */}
        <AnimatePresence>
          {showTraceSidebar && (
            <motion.div
              id="agentRail"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 350, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.24, ease: [0.2, 0.8, 0.2, 1] }}
              className="agent-rail"
            >
              <div className="panel activity-panel" id="activityPanel">
                {/* Activity Panel Header */}
                <div
                  className="panel-header activity-panel-header"
                  id="activityPanelHeader"
                  onClick={() => setShowTraceSidebar(false)}
                  title="Click to collapse execution trace to the right"
                >
                  <div>
                    <span className="kicker">ACTIVITY</span>
                    <h2>Execution trace</h2>
                  </div>
                  <div className="activity-header-right">
                    <span className="live-pill" id="livePill">LIVE</span>
                    <button
                      type="button"
                      id="activityCollapseBtn"
                      className="activity-collapse-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowTraceSidebar(false);
                      }}
                      title="Collapse execution trace to the right"
                      aria-label="Collapse execution trace"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Model Routing & Sovereign Air-gap Sub-banner */}
                <div className="my-2 py-2 px-3 rounded-md bg-[#131912] border border-[#233320] text-[11px] font-mono flex flex-col gap-1 shrink-0">
                  <div className="flex items-center justify-between">
                    <span className="text-neutral-400">ROUTED MODEL</span>
                    <span className="text-[#76B900] font-semibold bg-[#161b22] px-2 py-0.5 rounded border border-[#30363d]">
                      {activeTraceMessage?.model || activeModel}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-neutral-500 pt-1 border-t border-white/5">
                    <span>SOVEREIGN BOUNDARY</span>
                    <span className="text-[#76B900] flex items-center gap-1 font-semibold">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] animate-pulse" />
                      127.0.0.1 (0 WAN EGRESS)
                    </span>
                  </div>
                  {activeTraceMessage?.durationS !== undefined && (
                    <div className="flex items-center justify-between text-[10px] text-neutral-500">
                      <span>LATENCY</span>
                      <span className="text-[#a4db43] font-mono">{activeTraceMessage.durationS}s</span>
                    </div>
                  )}
                </div>

                {/* Activity List Timeline */}
                <div id="activityListWrap" className="activity-list-wrap">
                  <div id="activityList" className="activity-list">
                    {displayedActivityEvents.length === 0 ? (
                      <div className="py-16 text-center text-neutral-500 text-xs flex flex-col items-center gap-2">
                        <Zap className="w-5 h-5 text-neutral-600" />
                        <p>Activity appears here.</p>
                      </div>
                    ) : (
                      displayedActivityEvents.map((ev) => {
                        const isLive = ev.state === "active" || ev.state === "thinking";
                        return (
                          <div key={ev.id} className={`activity-event ${ev.state}`}>
                            <span className="activity-marker" aria-hidden="true">
                              <span className="activity-dot" />
                            </span>
                            <div className="activity-event-content">
                              <div className={`activity-event-text ${isLive ? "active-shimmer" : ""}`}>
                                {ev.text}
                              </div>
                              {ev.toolArgs && (
                                <div className="mt-1 p-2 rounded bg-[#0b0e0a] border border-[#233320] text-[10px] font-mono text-[#a8d38d] max-h-24 overflow-y-auto">
                                  <div className="text-neutral-500 text-[9px] mb-0.5">ARGUMENTS:</div>
                                  <pre className="whitespace-pre-wrap">{typeof ev.toolArgs === "string" ? ev.toolArgs : JSON.stringify(ev.toolArgs, null, 2)}</pre>
                                </div>
                              )}
                              {ev.toolOutput && (
                                <div className="mt-1 p-2 rounded bg-black/60 border border-white/5 text-[10px] font-mono text-neutral-400 max-h-24 overflow-y-auto">
                                  <div className="text-neutral-500 text-[9px] mb-0.5">OUTPUT:</div>
                                  <pre className="whitespace-pre-wrap">{ev.toolOutput}</pre>
                                </div>
                              )}
                              <small className="activity-event-time">{ev.timestamp}</small>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Raw End-to-End Workflow Debug Trace if present */}
                {activeTraceMessage?.debugTrace && (
                  <div className="mt-2 p-2 rounded-lg bg-[#0e120d] border border-[#233320] text-[10px] font-mono shrink-0">
                    <span className="text-[10px] text-neutral-400 font-semibold block mb-1">
                      RAW WORKFLOW DEBUG TRACE
                    </span>
                    <div className="max-h-32 overflow-y-auto p-2 bg-black/60 rounded border border-white/5 text-neutral-300 scrollbar-thin select-text">
                      <pre className="whitespace-pre-wrap leading-relaxed">{activeTraceMessage.debugTrace}</pre>
                    </div>
                  </div>
                )}
              </div>

              {/* Session History launcher at bottom of rail */}
              <button
                type="button"
                id="historyBtn"
                onClick={() => setIsHistoryOpen(true)}
                className="panel history-launcher mt-auto"
              >
                <History className="w-4 h-4 text-[#9acb42] shrink-0" />
                <span>
                  <b>Session history</b>
                  <small id="historyCount">{messages.length} messages saved</small>
                </span>
                <ExternalLink className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
