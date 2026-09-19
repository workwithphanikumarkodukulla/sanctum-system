"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Wrench,
  Terminal,
  FileCode,
  FolderSearch,
  Code2,
  FileText,
  Play,
  CheckCircle2,
  AlertCircle,
  Copy,
  ChevronRight,
  ShieldCheck,
  Zap,
  Activity,
  GitBranch,
  Cpu,
  Lock,
  Layers,
  Search,
} from "lucide-react";

interface MCPTool {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: React.ElementType;
  parameters: Record<string, string>;
  sampleInput: string;
  sampleOutput: string;
}

const mcpTools: MCPTool[] = [
  {
    id: "file_tool",
    name: "File Operations Tool",
    category: "Filesystem",
    description: "Read, write, create, and modify workspace files under host path constraints.",
    icon: FileCode,
    parameters: {
      action: "read | write | append | delete",
      file_path: "string (relative to workspace)",
      content: "string (optional for write)",
    },
    sampleInput: '{"action": "read", "file_path": "calculator.py"}',
    sampleOutput: '{"status": "ok", "lines": 42, "bytes": 640, "content": "# calculator.py..."}',
  },
  {
    id: "python_tool",
    name: "Python Sandbox",
    category: "Execution",
    description: "Executes Python code snippets securely inside isolated subprocess sandboxes.",
    icon: Code2,
    parameters: {
      code: "string (valid Python script)",
      timeout_seconds: "number (default: 10)",
    },
    sampleInput: '{"code": "import math\\nprint(math.sqrt(144))"}',
    sampleOutput: '{"stdout": "12.0\\n", "stderr": "", "exit_code": 0, "duration_ms": 18}',
  },
  {
    id: "terminal_tool",
    name: "Terminal Command Runner",
    category: "System",
    description: "Runs shell commands in host environment with strict policy whitelisting.",
    icon: Terminal,
    parameters: {
      command: "string (whitelisted command line)",
      cwd: "string (restricted to workspace root)",
    },
    sampleInput: '{"command": "python3 -m py_compile calculator.py"}',
    sampleOutput: '{"exit_code": 0, "stdout": "", "stderr": ""}',
  },
  {
    id: "workspace_tool",
    name: "Workspace Inspector",
    category: "Filesystem",
    description: "Generates recursive directory trees and file metadata for agent awareness.",
    icon: FolderSearch,
    parameters: {
      max_depth: "number (default: 3)",
      include_hidden: "boolean (default: false)",
    },
    sampleInput: '{"max_depth": 2, "include_hidden": false}',
    sampleOutput: '{"total_files": 18, "directories": 3, "root": "/workspace"}',
  },
  {
    id: "document_tool",
    name: "Document & PDF Parser",
    category: "RAG & Parsing",
    description: "Extracts textual content and structural tables from PDF, Word, and text documents.",
    icon: FileText,
    parameters: {
      path: "string (path to PDF or DOCX file)",
      pages: "string (optional page range, e.g. 1-5)",
    },
    sampleInput: '{"path": "sample_inspection.pdf", "pages": "1"}',
    sampleOutput: '{"pages_parsed": 1, "text_length": 1840, "extracted_at": "2026-09-13"}',
  },
];

interface ProductivityTool {
  id: string;
  title: string;
  category: "Testing" | "Quality" | "Security" | "System";
  command: string;
  description: string;
  icon: React.ElementType;
  lastOutput?: string;
  lastExitCode?: number;
}

const PRODUCTIVITY_TOOLS: ProductivityTool[] = [
  {
    id: "unit-tests",
    title: "Python Test Suite",
    category: "Testing",
    command: "python3 -m unittest discover -s tests -v",
    description: "Execute all unit assertions in local isolated sandbox with zero side effects.",
    icon: CheckCircle2,
    lastOutput: "Ran 4 tests in 0.038s\n\ntest_add (tests.test_calc) ... ok\ntest_reciprocal_zero (tests.test_calc) ... ok\n\nOK",
    lastExitCode: 0,
  },
  {
    id: "code-formatter",
    title: "Black Code Formatter",
    category: "Quality",
    command: "black --check --diff workspace/",
    description: "Validate deterministic AST formatting according to strict PEP8 rules.",
    icon: Code2,
    lastOutput: "All done! ✨ 3 files would be left unchanged.",
    lastExitCode: 0,
  },
  {
    id: "type-checker",
    title: "Mypy Strict Typing",
    category: "Quality",
    command: "mypy --strict workspace/calculator.py",
    description: "Verify algebraic type signatures and disallow untyped dynamic definitions.",
    icon: ShieldCheck,
    lastOutput: "Success: no issues found in 1 source file",
    lastExitCode: 0,
  },
  {
    id: "linter",
    title: "Ruff Linter & AST Guard",
    category: "Quality",
    command: "ruff check workspace/",
    description: "High-speed Rust-based linter enforcing safety guards and import sorting.",
    icon: Zap,
    lastOutput: "All checks passed! 0 errors, 0 warnings.",
    lastExitCode: 0,
  },
  {
    id: "security-audit",
    title: "Airgap Dependency Audit",
    category: "Security",
    command: "pip-audit --local --isolated",
    description: "Scan installed Python wheel manifests against known CVE vulnerability databases.",
    icon: ShieldCheck,
    lastOutput: "No known vulnerabilities found in 24 packages.",
    lastExitCode: 0,
  },
  {
    id: "git-diff",
    title: "Git Workspace Diff",
    category: "System",
    command: "git diff --stat HEAD",
    description: "Inspect uncommitted modifications made by autonomous agent turns.",
    icon: GitBranch,
    lastOutput: " calculator.py | 4 +++-\n 1 file changed, 3 insertions(+), 1 deletion(-)",
    lastExitCode: 0,
  },
  {
    id: "ast-complexity",
    title: "Radon AST Complexity",
    category: "Quality",
    command: "radon cc -s -a workspace/",
    description: "Compute cyclomatic complexity grade (A-F) for all functions and classes.",
    icon: Cpu,
    lastOutput: "calculator.py\n    F 12:0 reciprocal - A (score 2)\n    F 4:0 add - A (score 1)\nAverage complexity: A (1.5)",
    lastExitCode: 0,
  },
  {
    id: "loopback-ports",
    title: "Loopback Port Inspector",
    category: "Security",
    command: "lsof -iTCP -sTCP:LISTEN -P",
    description: "Verify all open daemon sockets bind exclusively to 127.0.0.1.",
    icon: Terminal,
    lastOutput: "COMMAND   PID      USER   FD   TYPE             DEVICE NODE NAME\nollama  14902  developer    3u  IPv4 0x76b900...      0t0  TCP 127.0.0.1:11434 (LISTEN)\nsanctum 14908  developer    4u  IPv4 0x76b901...      0t0  TCP 127.0.0.1:5050 (LISTEN)",
    lastExitCode: 0,
  },
  {
    id: "rag-summarizer",
    title: "LKB Vector Ingestion",
    category: "System",
    command: "sanctum lkb index --path=workspace/docs",
    description: "Index local engineering notes and specifications into loopback vector store.",
    icon: FileText,
    lastOutput: "Indexed 14 files into 142 embedding chunks using nomic-embed-text (0 external calls).",
    lastExitCode: 0,
  },
  {
    id: "locker-zip",
    title: "Encrypted Locker Archiver",
    category: "Security",
    command: "sanctum locker zip --algo=aes256gcm",
    description: "Package workspace into an Argon2id password-protected zero-knowledge archive.",
    icon: Lock,
    lastOutput: "Created workspace_archive.locked (4.2 KB) using Argon2id key derivation.",
    lastExitCode: 0,
  },
];

export const ToolsScreen: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"launcher" | "mcp">("launcher");
  const [selectedTool, setSelectedTool] = useState<MCPTool>(mcpTools[0]);
  const [runningToolId, setRunningToolId] = useState<string | null>(null);
  const [toolOutputs, setToolOutputs] = useState<Record<string, { output: string; exitCode: number }>>({});
  const [activePreviewTool, setActivePreviewTool] = useState<ProductivityTool | null>(null);

  const handleRunTool = (tool: ProductivityTool) => {
    setRunningToolId(tool.id);
    setTimeout(() => {
      setToolOutputs((prev) => ({
        ...prev,
        [tool.id]: {
          output: tool.lastOutput || "Command completed with exit code 0.",
          exitCode: tool.lastExitCode ?? 0,
        },
      }));
      setRunningToolId(null);
      setActivePreviewTool(tool);
    }, 600);
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-[#76B900] bg-[#1a2512] px-2 py-0.5 rounded border border-[#76B900]/30 flex items-center gap-1.5">
              <Wrench className="w-3 h-3" />
              SOVEREIGN TOOLING & PRODUCTIVITY
            </span>
            <span className="text-xs font-mono text-neutral-400">
              Zero Network Egress • Sandboxed Execution
            </span>
          </div>
          <h1 className="text-xl font-bold text-white">Engineering Tools & MCP Directory</h1>
          <p className="text-xs text-neutral-400 mt-0.5">
            Launch local developer utilities with one click, or inspect Model Context Protocol (MCP) primitives available to the agent.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("launcher")}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-colors cursor-pointer ${
              activeTab === "launcher"
                ? "bg-[#76B900] text-black font-semibold shadow-md"
                : "bg-[#181818] text-neutral-300 hover:bg-[#222]"
            }`}
          >
            Productivity Launcher (10)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("mcp")}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-colors cursor-pointer ${
              activeTab === "mcp"
                ? "bg-[#76B900] text-black font-semibold shadow-md"
                : "bg-[#181818] text-neutral-300 hover:bg-[#222]"
            }`}
          >
            MCP Primitives ({mcpTools.length})
          </button>
        </div>
      </div>

      {activeTab === "launcher" ? (
        <div className="space-y-6">
          {/* 10 Productivity Tools Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {PRODUCTIVITY_TOOLS.map((tool) => {
              const Icon = tool.icon;
              const isRunning = runningToolId === tool.id;
              const hasRun = toolOutputs[tool.id] !== undefined;

              return (
                <motion.div
                  key={tool.id}
                  whileHover={{ y: -2 }}
                  className="p-4 rounded-xl bg-[#121317] border border-[#23242a] hover:border-[#76B900]/40 transition-all flex flex-col justify-between space-y-3"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <div className="p-2 rounded-lg bg-[#1a1b22] text-[#76B900] border border-white/5">
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <h3 className="text-xs font-semibold text-white">{tool.title}</h3>
                          <span className="text-[9px] font-mono uppercase px-1.5 py-0.2 rounded bg-white/5 text-neutral-400">
                            {tool.category}
                          </span>
                        </div>
                      </div>

                      {hasRun && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#162210] text-[#86e810] border border-[#76B900]/30 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          EXIT 0
                        </span>
                      )}
                    </div>

                    <p className="text-[11px] text-neutral-400 leading-relaxed min-h-[32px]">
                      {tool.description}
                    </p>

                    <div className="mt-2 p-1.5 rounded bg-[#0b0c0e] font-mono text-[10px] text-neutral-300 border border-white/5 truncate">
                      $ {tool.command}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => handleRunTool(tool)}
                      disabled={isRunning}
                      className="flex-1 py-1.5 rounded-lg bg-[#1f2b14] hover:bg-[#2c3c1a] text-[#86e810] border border-[#76B900]/40 text-xs font-mono flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <Play className={`w-3 h-3 ${isRunning ? "animate-spin text-[#76B900]" : ""}`} />
                      <span>{isRunning ? "Running..." : "Run Tool"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActivePreviewTool(tool)}
                      className="px-2.5 py-1.5 rounded-lg bg-[#18191f] hover:bg-[#23242c] text-neutral-300 text-xs font-mono border border-white/5 transition-colors cursor-pointer"
                      title="Inspect tool stdout"
                    >
                      Output
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>

          {/* Tool Output Inspector Drawer / Modal */}
          {activePreviewTool && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl p-5 bg-[#0f1013] border border-[#2c2d36] space-y-3 font-mono text-xs"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-[#76B900]" />
                  <span className="font-semibold text-white">{activePreviewTool.title} Console Output</span>
                  <span className="text-[10px] text-neutral-500">$ {activePreviewTool.command}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setActivePreviewTool(null)}
                  className="text-neutral-400 hover:text-white text-xs px-2 py-0.5 rounded bg-white/5"
                >
                  Close
                </button>
              </div>

              <div className="p-3 rounded-lg bg-[#070709] border border-white/5 text-neutral-200 overflow-x-auto max-h-48 leading-relaxed">
                <pre className="font-mono text-[11px] whitespace-pre-wrap">
                  {toolOutputs[activePreviewTool.id]?.output || activePreviewTool.lastOutput}
                </pre>
              </div>
            </motion.div>
          )}
        </div>
      ) : (
        /* MCP Primitives Master-Detail View */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Tool List */}
          <div className="space-y-2">
            <h2 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
              Registered MCP Tools ({mcpTools.length})
            </h2>
            {mcpTools.map((tool) => {
              const Icon = tool.icon;
              const isSelected = selectedTool.id === tool.id;

              return (
                <div
                  key={tool.id}
                  onClick={() => setSelectedTool(tool)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? "bg-[#141d0f] border-[#76B900] shadow-md shadow-[#76B900]/10"
                      : "bg-[#141414] border-[#242424] hover:border-[#383838]"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        isSelected
                          ? "bg-[#76B900] text-black"
                          : "bg-[#1f1f1f] text-neutral-400"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-xs font-semibold text-white">{tool.name}</h3>
                      <span className="text-[10px] font-mono text-neutral-500">{tool.category}</span>
                    </div>
                  </div>
                  <ChevronRight className={`w-4 h-4 ${isSelected ? "text-[#76B900]" : "text-neutral-600"}`} />
                </div>
              );
            })}
          </div>

          {/* Selected Tool Detail */}
          <div className="lg:col-span-2 glass-panel rounded-xl p-6 border border-[#262626] space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-mono text-[#86e810] bg-[#162210] px-2 py-0.5 rounded border border-[#76B900]/30 inline-block mb-2">
                  {selectedTool.category} MCP PRIMITIVE
                </span>
                <h2 className="text-lg font-bold text-white">{selectedTool.name}</h2>
                <p className="text-xs text-neutral-300 mt-1">{selectedTool.description}</p>
              </div>
            </div>

            {/* Parameters Schema */}
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
                Input Parameters Schema
              </h3>
              <div className="rounded-lg bg-[#0e0e0e] border border-[#202020] p-3 space-y-2">
                {Object.entries(selectedTool.parameters).map(([key, type]) => (
                  <div key={key} className="flex items-center justify-between text-xs font-mono">
                    <span className="text-neutral-300 font-semibold">{key}</span>
                    <span className="text-[#86e810] bg-[#141a10] px-2 py-0.5 rounded">{type}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Sample Invocation Input */}
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
                Sample Agent Tool Call (JSON-RPC)
              </h3>
              <pre className="rounded-lg bg-[#0a0a0a] border border-[#202020] p-3 text-xs font-mono text-neutral-300 overflow-x-auto">
                {selectedTool.sampleInput}
              </pre>
            </div>

            {/* Sample Return Output */}
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
                Sample Tool Return Output
              </h3>
              <pre className="rounded-lg bg-[#0a0a0a] border border-[#202020] p-3 text-xs font-mono text-[#86e810] overflow-x-auto">
                {selectedTool.sampleOutput}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
