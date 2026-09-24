"use client";

import React, { useState, useMemo } from "react";
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
  FileSpreadsheet,
  Presentation,
  Bot,
  Sparkles,
  ArrowUpRight,
  Folder,
  SlidersHorizontal,
  X,
  Send,
  FilePlus,
  Check,
  ScanText,
  FileCheck,
} from "lucide-react";
import { ScreenType } from "@/types";

/* ══════════════════════════════════════════════════════════════════
   1. TYPES & DATA STRUCTURES
   ══════════════════════════════════════════════════════════════════ */

export interface ToolsScreenProps {
  onNavigate?: (screen: ScreenType) => void;
  onQuickPrompt?: (prompt: string) => void;
}

export type ToolCategory = "all" | "document" | "code" | "workspace";

export interface GenerativePreset {
  label: string;
  title: string;
  subtitle?: string;
  details: string;
  filename?: string;
}

export interface GenerativeTool {
  id: string;
  index: string;
  title: string;
  category: "document" | "code" | "workspace";
  categoryLabel: string;
  tagline: string;
  description: string;
  extensionBadge: string;
  badgeColor: string; // Tailwind color classes for accent badge
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  defaultPromptTemplate: string;
  defaultTitlePlaceholder: string;
  defaultDetailsPlaceholder: string;
  defaultFilename?: string;
  capabilities: string[];
  presets: GenerativePreset[];
  targetScreen?: ScreenType;
}

/* ══════════════════════════════════════════════════════════════════
   2. GENERATIVE TOOLS CATALOG (MERGED FROM INTEGRATE WITH ELEVATED UI)
   ══════════════════════════════════════════════════════════════════ */

export const GENERATIVE_TOOLS: GenerativeTool[] = [
  {
    id: "make_pdf",
    index: "01 / COMPOSE",
    title: "Make PDFs",
    category: "document",
    categoryLabel: "ReportLab Engine",
    tagline: "Shape research, audits, and briefs into a publication-ready PDF.",
    description: "Generates styled PDF documents locally with automated title blocks, headers, structured tables, and security callout cards.",
    extensionBadge: ".PDF",
    badgeColor: "text-rose-400 bg-rose-950/40 border-rose-800/40",
    icon: FileText,
    iconBg: "bg-rose-500/10 border-rose-500/30 text-rose-400",
    iconColor: "text-rose-400",
    defaultPromptTemplate: "Create a PDF report titled [title] about:",
    defaultTitlePlaceholder: "Quarterly Airgap & System Security Audit",
    defaultDetailsPlaceholder: "Cover local Ollama model benchmarks, zero network egress telemetry, and Argon2id sovereign vault status. Include summary tables.",
    defaultFilename: "reports/security_audit.pdf",
    capabilities: ["Automated Pagination", "Multi-column Data Tables", "Vault Auto-Lock In-Place"],
    presets: [
      {
        label: "Security Audit",
        title: "Sanctum Airgap & Sovereignty Audit",
        subtitle: "Zero External Egress Verification",
        details: "Documenting strict loopback-only communication, loopback port bindings, and AES-256 encrypted storage integrity.",
        filename: "reports/sanctum_security_audit.pdf",
      },
      {
        label: "Executive Brief",
        title: "Local Intelligence Architecture Brief",
        subtitle: "Enterprise Airgapped AI Deployment",
        details: "Executive summary detailing on-device LLM inference throughput, hardware resource constraints, and data sovereignty compliance.",
        filename: "briefs/executive_ai_brief.pdf",
      },
      {
        label: "Technical Spec",
        title: "Sovereign Agent Loop Specification",
        subtitle: "Autonomous Tool Calling & Trace Flow",
        details: "Technical breakdown of fluid agent turns, AST validation, execution trace rails, and sandboxed subprocess wrappers.",
        filename: "specs/agent_architecture.pdf",
      },
    ],
  },
  {
    id: "make_ppt",
    index: "02 / PRESENT",
    title: "Make Presentations",
    category: "document",
    categoryLabel: "PowerPoint Deck",
    tagline: "Turn an idea or analysis into a clear, widescreen 16:9 presentation.",
    description: "Builds PowerPoint (.pptx) decks complete with high-contrast title covers, structured bullet points, and multi-column visual cards.",
    extensionBadge: ".PPTX",
    badgeColor: "text-amber-400 bg-amber-950/40 border-amber-800/40",
    icon: Presentation,
    iconBg: "bg-amber-500/10 border-amber-500/30 text-amber-400",
    iconColor: "text-amber-400",
    defaultPromptTemplate: "Create a presentation titled [title] about:",
    defaultTitlePlaceholder: "Sanctum Sovereign Platform Overview",
    defaultDetailsPlaceholder: "Slide 1: Title & Executive Vision\nSlide 2: The Egress Threat Model\nSlide 3: Loopback Orchestration\nSlide 4: Benchmarks & Latency",
    defaultFilename: "presentations/sanctum_overview.pptx",
    capabilities: ["Widescreen 16:9 Format", "Card Containers & Bullets", "Dark/Light Theming"],
    presets: [
      {
        label: "System Architecture",
        title: "Sanctum Architecture & Data Flow",
        subtitle: "Airgapped Agentic Engineering",
        details: "1. Core Philosophy: Zero Network Egress\n2. The Sovereign Vault\n3. Local LLM Runtime\n4. MCP Tool Primitives\n5. Verifiable Telemetry",
        filename: "presentations/system_architecture.pptx",
      },
      {
        label: "Product Pitch",
        title: "Zero-Knowledge Enterprise AI",
        subtitle: "Deploying Autonomous Agents with Total Data Privacy",
        details: "1. The Enterprise Privacy Dilemma\n2. The Sanctum Solution\n3. Local Inference Speeds\n4. ROI & Compliance Roadmaps",
        filename: "presentations/enterprise_pitch.pptx",
      },
    ],
  },
  {
    id: "make_excel",
    index: "03 / ORGANIZE",
    title: "Make Excels",
    category: "document",
    categoryLabel: "OpenPyXL Engine",
    tagline: "Build clean workbooks, multi-sheet models, and structured data.",
    description: "Synthesizes multi-tab spreadsheets with styled headers, custom cell alignments, frozen top rows, and automated column width adjustments.",
    extensionBadge: ".XLSX",
    badgeColor: "text-emerald-400 bg-emerald-950/40 border-emerald-800/40",
    icon: FileSpreadsheet,
    iconBg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
    iconColor: "text-emerald-400",
    defaultPromptTemplate: "Create an Excel workbook at [path] with these sheets and data:",
    defaultTitlePlaceholder: "metrics/model_benchmarks.xlsx",
    defaultDetailsPlaceholder: "Sheet 1: 'Inference Benchmarks' with columns: Model, TTFT (ms), Tokens/Sec, VRAM (GB), Peak Latency.\nSheet 2: 'Loopback Telemetry' with columns: Port, Socket Type, Pkts In, Pkts Out, Status.",
    defaultFilename: "data/performance_metrics.xlsx",
    capabilities: ["Freeze Panes & Styled Headers", "Summary & Totals Row", "Multi-Sheet Support"],
    presets: [
      {
        label: "Model Benchmarks",
        title: "model_benchmarks.xlsx",
        details: "Create an Excel sheet comparing Gemma 2, Llama 3.1 8B, and Mistral 7B across TTFT, tokens/sec, and GPU VRAM footprint.",
        filename: "benchmarks/model_comparison.xlsx",
      },
      {
        label: "Financial Projection",
        title: "annual_projections.xlsx",
        details: "Create a financial workbook with columns: Quarter, Compute Hardware, Infrastructure, Operational Costs, Total.",
        filename: "finance/annual_projections.xlsx",
      },
    ],
  },
  {
    id: "make_docx",
    index: "04 / WRITE",
    title: "Make DOCX",
    category: "document",
    categoryLabel: "Word Document",
    tagline: "Draft polished Word documents, specifications, and whitepapers.",
    description: "Produces cleanly formatted Microsoft Word (.docx) documents featuring hierarchical headings, styled callout boxes, and formatted data tables.",
    extensionBadge: ".DOCX",
    badgeColor: "text-blue-400 bg-blue-950/40 border-blue-800/40",
    icon: FileText,
    iconBg: "bg-blue-500/10 border-blue-500/30 text-blue-400",
    iconColor: "text-blue-400",
    defaultPromptTemplate: "Create a Word document titled [title] about:",
    defaultTitlePlaceholder: "Autonomous Agent Operational Guidelines",
    defaultDetailsPlaceholder: "Include Section 1: Scope & Purpose, Section 2: Code Execution Safety Bounds, Section 3: Incident Response & Rollback Procedures. Include a policy table.",
    defaultFilename: "docs/operational_guidelines.docx",
    capabilities: ["Standard Headings & Typography", "Callout Paragraphs", "Styled Data Tables"],
    presets: [
      {
        label: "Whitepaper",
        title: "Sanctum Sovereign Computing Whitepaper",
        subtitle: "Technical Architecture for Airgapped Machine Learning",
        details: "Draft a formal whitepaper exploring local LLM reasoning, sandboxed tooling, zero-egress packet verification, and Argon2id disk encryption.",
        filename: "docs/sovereignty_whitepaper.docx",
      },
      {
        label: "Standard Operating Procedure",
        title: "Cryptographic Key Rotation SOP",
        subtitle: "Sovereign Vault Key Lifecycle Management",
        details: "Step-by-step procedures for rotating Argon2id master passphrases, re-encrypting workspace shards, and auditing vault checksums.",
        filename: "docs/key_rotation_sop.docx",
      },
    ],
  },
  {
    id: "write_code",
    index: "05 / BUILD",
    title: "Write Code",
    category: "code",
    categoryLabel: "AST & Sandbox",
    tagline: "Turn specifications into clean, working, and explainable software.",
    description: "Invokes the sovereign code synthesizer to generate production-ready Python, Bash, or TypeScript scripts with isolated AST verification.",
    extensionBadge: ".PY / .TS",
    badgeColor: "text-purple-400 bg-purple-950/40 border-purple-800/40",
    icon: Code2,
    iconBg: "bg-purple-500/10 border-purple-500/30 text-purple-400",
    iconColor: "text-purple-400",
    defaultPromptTemplate: "Write code that accomplishes the following:",
    defaultTitlePlaceholder: "Async CSV Parser with Anomaly Detection",
    defaultDetailsPlaceholder: "Write a self-contained Python script in the workspace that reads telemetry CSV files, computes exponential rolling averages, and flags outliers.",
    defaultFilename: "scripts/process_telemetry.py",
    capabilities: ["Airgapped Execution Sandbox", "PEP8 & Strict Type Hints", "Deterministic Unit Tests"],
    presets: [
      {
        label: "FastAPI Daemon",
        title: "Loopback REST Service",
        details: "Write a high-speed FastAPI microservice listening strictly on 127.0.0.1:8080 with pydantic request validation and zero telemetry.",
        filename: "services/loopback_api.py",
      },
      {
        label: "Data Pipeline",
        title: "Log Ingestion Pipeline",
        details: "Write a memory-efficient Python pipeline to stream through workspace log files, parse regex timestamp patterns, and compute latency percentiles.",
        filename: "scripts/log_pipeline.py",
      },
    ],
  },
  {
    id: "chat_ai",
    index: "06 / THINK",
    title: "Chat with AI",
    category: "code",
    categoryLabel: "Fluid Agent",
    tagline: "Ask, explore, plan, and analyze with your local sovereign agent.",
    description: "Launch multi-turn reasoning, architectural planning, system refactoring, and contextual code review backed by local Ollama models.",
    extensionBadge: "AGENT",
    badgeColor: "text-cyan-400 bg-cyan-950/40 border-cyan-800/40",
    icon: Bot,
    iconBg: "bg-cyan-500/10 border-cyan-500/30 text-cyan-400",
    iconColor: "text-cyan-400",
    defaultPromptTemplate: "Help me with the following task:",
    defaultTitlePlaceholder: "System Refactoring & Code Audit",
    defaultDetailsPlaceholder: "Inspect our workspace python files and identify opportunities to improve performance and remove redundant operations.",
    capabilities: ["Multi-turn Contextual Memory", "Local Tool Calling", "Zero External Token Egress"],
    presets: [
      {
        label: "Code Review",
        title: "Workspace Codebase Audit",
        details: "Review all workspace scripts for edge cases, resource leaks, and unhandled exceptions. Suggest concrete improvements.",
      },
      {
        label: "Architecture Q&A",
        title: "Explore Sanctum Internals",
        details: "Explain how Sanctum guarantees that no network packet leaves this machine during agent tool execution.",
      },
    ],
  },
  {
    id: "protect_files",
    index: "07 / SECURE",
    title: "Protect Files",
    category: "workspace",
    categoryLabel: "Cryptographic Locker",
    tagline: "Apply Argon2id cryptographic cover to sensitive files locally.",
    description: "Encrypt files and directories in-place using AES-256-GCM authenticated encryption and zero-knowledge key derivation.",
    extensionBadge: ".LOCKED",
    badgeColor: "text-[#76B900] bg-[#1a2512] border-[#76B900]/40",
    icon: Lock,
    iconBg: "bg-[#76B900]/10 border-[#76B900]/30 text-[#76B900]",
    iconColor: "text-[#76B900]",
    defaultPromptTemplate: "",
    defaultTitlePlaceholder: "Lock Confidential Workspace Files",
    defaultDetailsPlaceholder: "Navigate to Sanctum Cryptographic Locker workbench.",
    capabilities: ["Argon2id Key Derivation", "AES-256-GCM AEAD", "Zero Key Escrow"],
    presets: [],
    targetScreen: "locker",
  },
  {
    id: "connect_git",
    index: "08 / VERSION",
    title: "Connect to Git",
    category: "code",
    categoryLabel: "VCS Integration",
    tagline: "Understand branches, commits, diffs, and project history.",
    description: "Direct the agent to inspect modified files, draft atomic commit messages, create feature branches, and safely manage local Git workflows.",
    extensionBadge: "GIT",
    badgeColor: "text-indigo-400 bg-indigo-950/40 border-indigo-800/40",
    icon: GitBranch,
    iconBg: "bg-indigo-500/10 border-indigo-500/30 text-indigo-400",
    iconColor: "text-indigo-400",
    defaultPromptTemplate: "Help me connect this workspace to Git and set up the following workflow:",
    defaultTitlePlaceholder: "Git Workspace Staging & Commit Flow",
    defaultDetailsPlaceholder: "Check git status, display the concise diff of all changes made during the last turn, and create a descriptive commit.",
    capabilities: ["Atomic Commit Authoring", "Safe Branch Isolation", "Diff Inspection"],
    presets: [
      {
        label: "Commit Recent Work",
        title: "Stage and Commit Workspace Changes",
        details: "Inspect all untracked and modified files, verify tests pass, and generate an atomic conventional commit message.",
      },
      {
        label: "Branch Setup",
        title: "Feature Branch Workflow",
        details: "Create a new branch 'feature/offline-rag-pipeline' and establish clean commits without touching main.",
      },
    ],
  },
  {
    id: "work_terminal",
    index: "09 / EXECUTE",
    title: "Work on Terminal",
    category: "code",
    categoryLabel: "Subprocess Runner",
    tagline: "Run workspace commands, inspect outputs, and diagnose builds.",
    description: "Execute whitelisted shell commands safely inside workspace boundaries with full stdout/stderr capture and policy enforcement.",
    extensionBadge: "BASH",
    badgeColor: "text-zinc-400 bg-zinc-900 border-zinc-700",
    icon: Terminal,
    iconBg: "bg-zinc-800/50 border-zinc-700 text-zinc-300",
    iconColor: "text-zinc-300",
    defaultPromptTemplate: "Run this terminal command and explain the result:",
    defaultTitlePlaceholder: "Execute Unit Test Suite",
    defaultDetailsPlaceholder: "python3 -m unittest discover -s tests -v",
    capabilities: ["Subprocess Isolation", "Whitelisted Commands", "Live Output Capture"],
    presets: [
      {
        label: "Run Test Suite",
        title: "Run Python Unit Tests",
        details: "python3 -m unittest discover -s tests -v",
      },
      {
        label: "Check Open Sockets",
        title: "Audit Listening Ports",
        details: "lsof -iTCP -sTCP:LISTEN -P",
      },
    ],
  },
  {
    id: "explore_files",
    index: "10 / EXPLORE",
    title: "Explore Files",
    category: "workspace",
    categoryLabel: "Workspace Explorer",
    tagline: "Browse, read, edit, and organize files in your active workspace.",
    description: "Navigate to the Sanctum Workspace explorer with integrated Monaco code editor, file tree, search, and instant document previewers.",
    extensionBadge: "FILES",
    badgeColor: "text-yellow-400 bg-yellow-950/40 border-yellow-800/40",
    icon: Folder,
    iconBg: "bg-yellow-500/10 border-yellow-500/30 text-yellow-400",
    iconColor: "text-yellow-400",
    defaultPromptTemplate: "",
    defaultTitlePlaceholder: "Browse Active Workspace",
    defaultDetailsPlaceholder: "Navigate to Workspace Explorer screen.",
    capabilities: ["Monaco Code Editor", "Image & Document Viewers", "Real-Time File Tree"],
    presets: [],
    targetScreen: "workspace",
  },
  {
    id: "ocr_parser",
    index: "11 / PARSE",
    title: "OCR & Doc Parser",
    category: "workspace",
    categoryLabel: "Tesseract & PyMuPDF",
    tagline: "Extract high-fidelity text and tables from images and multi-page PDFs.",
    description: "Parses complex documents and scanned images with automatic page orientation detection, Tesseract OCR, and tabular text extraction.",
    extensionBadge: "OCR / RAG",
    badgeColor: "text-teal-400 bg-teal-950/40 border-teal-800/40",
    icon: ScanText,
    iconBg: "bg-teal-500/10 border-teal-500/30 text-teal-400",
    iconColor: "text-teal-400",
    defaultPromptTemplate: "Extract and analyze the content of document:",
    defaultTitlePlaceholder: "sample_inspection.pdf",
    defaultDetailsPlaceholder: "Read pages 1 through 3, extract any equipment inspection tables, and provide a summary of all flagged defects.",
    capabilities: ["Auto-Rotation OCR", "PDF Table Reconstruction", "Word & Excel Ingestion"],
    presets: [
      {
        label: "Scan Invoice/Report",
        title: "Extract Scanned Document",
        details: "Inspect the file 'sample_inspection.pdf', extract all paragraphs and structured tables, and summarize the key findings.",
      },
    ],
  },
  {
    id: "structured_notes",
    index: "12 / NOTES",
    title: "Structured Notes",
    category: "document",
    categoryLabel: "Markdown Note",
    tagline: "Generate markdown notes with YAML frontmatter, checklists, and summaries.",
    description: "Creates clean engineering notes and Architecture Decision Records (ADRs) with metadata tags, summaries, and action checklists.",
    extensionBadge: ".MD",
    badgeColor: "text-pink-400 bg-pink-950/40 border-pink-800/40",
    icon: FileCode,
    iconBg: "bg-pink-500/10 border-pink-500/30 text-pink-400",
    iconColor: "text-pink-400",
    defaultPromptTemplate: "Create a structured Markdown note titled [title] about:",
    defaultTitlePlaceholder: "Architecture Decision Record: Offline Document Engine",
    defaultDetailsPlaceholder: "Record ADR-005: Choice of ReportLab and python-pptx for 100% offline document creation. List context, decisions, and consequences.",
    defaultFilename: "notes/adr_005_doc_engine.md",
    capabilities: ["YAML Frontmatter Metadata", "Task Lists & Checklists", "Direct Workspace Output"],
    presets: [
      {
        label: "Architecture ADR",
        title: "ADR-004: In-Place Vault Key Architecture",
        details: "Documenting the decision to lock files in-place with Argon2id headers instead of copying to temporary caches.",
        filename: "notes/adr_004_vault_locking.md",
      },
      {
        label: "Meeting Summary",
        title: "Engineering Sprint Alignment",
        details: "Summarize sprint objectives: 1. Complete PDF tool UI, 2. Verify OCR orientation handling, 3. Validate airgap firewall rules.",
        filename: "notes/sprint_alignment.md",
      },
    ],
  },
];

/* ══════════════════════════════════════════════════════════════════
   3. MCP PROTOCOL TOOLS (LOW LEVEL JSON-RPC PRIMITIVES)
   ══════════════════════════════════════════════════════════════════ */

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

const MCP_PRIMITIVES: MCPTool[] = [
  {
    id: "generate_pdf_report",
    name: "generate_pdf_report",
    category: "Document Synthesis",
    description: "Synthesizes publication-grade PDF reports directly to workspace with automated styling and in-place vault protection.",
    icon: FileText,
    parameters: {
      filepath: "string (e.g. reports/audit.pdf)",
      title: "string (main title)",
      subtitle: "string (optional secondary subtitle)",
      sections_json: "array or json string (sections with heading, content, tables, callouts)",
    },
    sampleInput: '{"filepath": "reports/audit.pdf", "title": "Security Audit", "subtitle": "Airgap Verification", "sections_json": [{"heading": "Executive Summary", "content": "100% loopback validated."}]}',
    sampleOutput: '{"status": "success", "file": "reports/audit.pdf", "format": "pdf", "file_exists": true, "size_bytes": 14280, "error": null}',
  },
  {
    id: "generate_presentation",
    name: "generate_presentation",
    category: "Document Synthesis",
    description: "Compiles widescreen 16:9 PowerPoint presentations (.pptx) with structured cards and bullet points.",
    icon: Presentation,
    parameters: {
      filepath: "string (e.g. decks/architecture.pptx)",
      title: "string (deck cover title)",
      subtitle: "string (deck cover subtitle)",
      slides_json: "array (slides with title and cards or bullet_points)",
    },
    sampleInput: '{"filepath": "decks/arch.pptx", "title": "Sanctum Overview", "slides_json": [{"title": "Airgap Guarantee", "bullet_points": ["Zero egress", "Local Ollama"]}]}',
    sampleOutput: '{"status": "success", "file": "decks/arch.pptx", "format": "pptx", "file_exists": true, "size_bytes": 38400, "error": null}',
  },
  {
    id: "generate_excel_sheet",
    name: "generate_excel_sheet",
    category: "Document Synthesis",
    description: "Constructs multi-sheet Excel spreadsheets with headers, column widths, freeze panes, and totals.",
    icon: FileSpreadsheet,
    parameters: {
      filepath: "string (e.g. metrics/stats.xlsx)",
      sheets_json: "array (sheets with title, headers, rows, and optional totals_row)",
    },
    sampleInput: '{"filepath": "data/metrics.xlsx", "sheets_json": [{"title": "Throughput", "headers": ["Model", "Tok/s"], "rows": [["gemma4", 42]]}]}',
    sampleOutput: '{"status": "success", "file": "data/metrics.xlsx", "format": "xlsx", "file_exists": true, "size_bytes": 8920, "error": null}',
  },
  {
    id: "generate_word_document",
    name: "generate_word_document",
    category: "Document Synthesis",
    description: "Generates formatted Microsoft Word (.docx) specifications with styled headers and tables.",
    icon: FileCode,
    parameters: {
      filepath: "string (e.g. docs/spec.docx)",
      title: "string (document title)",
      subtitle: "string (optional)",
      sections_json: "array (sections with heading, content, callout, table)",
    },
    sampleInput: '{"filepath": "docs/spec.docx", "title": "System Specification", "sections_json": [{"heading": "Overview", "content": "Airgapped system."}]}',
    sampleOutput: '{"status": "success", "file": "docs/spec.docx", "format": "docx", "file_exists": true, "size_bytes": 11450, "error": null}',
  },
  {
    id: "file_tool",
    name: "file_tool",
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
    name: "python_tool",
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
    name: "terminal_tool",
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
    name: "workspace_tool",
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
    name: "document_tool",
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

/* ══════════════════════════════════════════════════════════════════
   4. PRODUCTIVITY & DEV UTILITIES (FOR DEV TAB)
   ══════════════════════════════════════════════════════════════════ */

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
    id: "loopback-ports",
    title: "Loopback Port Inspector",
    category: "Security",
    command: "lsof -iTCP -sTCP:LISTEN -P",
    description: "Verify all open daemon sockets bind exclusively to 127.0.0.1.",
    icon: Terminal,
    lastOutput: "COMMAND   PID      USER   FD   TYPE             DEVICE NODE NAME\nollama  14902  developer    3u  IPv4 0x76b900...      0t0  TCP 127.0.0.1:11434 (LISTEN)\nsanctum 14908  developer    4u  IPv4 0x76b901...      0t0  TCP 127.0.0.1:5050 (LISTEN)",
    lastExitCode: 0,
  },
];

/* ══════════════════════════════════════════════════════════════════
   5. MAIN COMPONENT: ToolsScreen
   ══════════════════════════════════════════════════════════════════ */

export const ToolsScreen: React.FC<ToolsScreenProps> = ({
  onNavigate,
  onQuickPrompt,
}) => {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<"generative" | "mcp" | "utilities">("generative");

  // Filter & Search State
  const [selectedCategory, setSelectedCategory] = useState<ToolCategory>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Modal / Prompt Configurator State
  const [activeConfigTool, setActiveConfigTool] = useState<GenerativeTool | null>(null);
  const [customTitle, setCustomTitle] = useState("");
  const [customSubtitle, setCustomSubtitle] = useState("");
  const [customDetails, setCustomDetails] = useState("");
  const [customFilename, setCustomFilename] = useState("");
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  // MCP Tab State
  const [selectedMCPTool, setSelectedMCPTool] = useState<MCPTool>(MCP_PRIMITIVES[0]);

  // Dev Utilities State
  const [runningToolId, setRunningToolId] = useState<string | null>(null);
  const [toolOutputs, setToolOutputs] = useState<Record<string, { output: string; exitCode: number }>>({});
  const [activePreviewTool, setActivePreviewTool] = useState<ProductivityTool | null>(null);

  // Filter generative tools
  const filteredGenerativeTools = useMemo(() => {
    return GENERATIVE_TOOLS.filter((tool) => {
      const matchesCategory =
        selectedCategory === "all" || tool.category === selectedCategory;
      const matchesSearch =
        tool.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.tagline.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.extensionBadge.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  // Open prompt configurator modal for a specific tool
  const handleOpenConfigurator = (tool: GenerativeTool) => {
    // If it's a direct navigation tool (e.g. Locker or Workspace), handle direct jump
    if (tool.targetScreen) {
      if (onNavigate) {
        onNavigate(tool.targetScreen);
      }
      return;
    }

    setActiveConfigTool(tool);
    setCustomTitle(tool.presets[0]?.title || tool.defaultTitlePlaceholder);
    setCustomSubtitle(tool.presets[0]?.subtitle || "");
    setCustomDetails(tool.presets[0]?.details || tool.defaultDetailsPlaceholder);
    setCustomFilename(tool.presets[0]?.filename || tool.defaultFilename || "");
    setCopiedPrompt(false);
  };

  // Close configurator modal
  const handleCloseConfigurator = () => {
    setActiveConfigTool(null);
    setCopiedPrompt(false);
  };

  // Compute live assembled prompt from configurator inputs
  const liveAssembledPrompt = useMemo(() => {
    if (!activeConfigTool) return "";

    const titlePart = customTitle.trim() || "[Title]";
    const detailsPart = customDetails.trim() ? `\n\nRequirements & Focus Areas:\n${customDetails.trim()}` : "";
    const subtitlePart = customSubtitle.trim() ? `\nSubtitle: ${customSubtitle.trim()}` : "";
    const filePart = customFilename.trim() ? `\nSave directly to workspace at path: "${customFilename.trim()}"` : "";

    if (activeConfigTool.id === "make_pdf") {
      return `Create a PDF report titled "${titlePart}" about:${subtitlePart}${detailsPart}${filePart}`;
    }
    if (activeConfigTool.id === "make_ppt") {
      return `Create a presentation titled "${titlePart}" about:${subtitlePart}${detailsPart}${filePart}`;
    }
    if (activeConfigTool.id === "make_excel") {
      const path = customFilename.trim() || customTitle.trim() || "data/workbook.xlsx";
      return `Create an Excel workbook at "${path}" with these sheets and data:${detailsPart || "\nSheet 1: Summary with appropriate headers and totals."}`;
    }
    if (activeConfigTool.id === "make_docx") {
      return `Create a Word document titled "${titlePart}" about:${subtitlePart}${detailsPart}${filePart}`;
    }
    if (activeConfigTool.id === "write_code") {
      return `Write code that accomplishes the following:\nTask: ${titlePart}${detailsPart}${filePart}`;
    }
    if (activeConfigTool.id === "chat_ai") {
      return `Help me with the following task: ${titlePart}${detailsPart}`;
    }
    if (activeConfigTool.id === "connect_git") {
      return `Help me connect this workspace to Git and set up the following workflow:\n${titlePart}${detailsPart}`;
    }
    if (activeConfigTool.id === "work_terminal") {
      return `Run this terminal command and explain the result:\n${customDetails.trim() || customTitle.trim()}`;
    }
    if (activeConfigTool.id === "ocr_parser") {
      return `Extract and analyze the content of document: "${customTitle.trim() || "document.pdf"}"${detailsPart}`;
    }
    if (activeConfigTool.id === "structured_notes") {
      return `Create a structured Markdown note titled "${titlePart}" with YAML frontmatter about:${detailsPart}${filePart}`;
    }

    return `${activeConfigTool.defaultPromptTemplate} ${titlePart}${detailsPart}`;
  }, [activeConfigTool, customTitle, customSubtitle, customDetails, customFilename]);

  // Direct fast launch with default prompt
  const handleQuickLaunchDirect = (tool: GenerativeTool, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    if (tool.targetScreen) {
      if (onNavigate) onNavigate(tool.targetScreen);
      return;
    }

    const defaultTitle = tool.presets[0]?.title || tool.defaultTitlePlaceholder;
    let initialPrompt = tool.defaultPromptTemplate.replace("[title]", `"${defaultTitle}"`);
    if (tool.defaultFilename && initialPrompt.includes("[path]")) {
      initialPrompt = initialPrompt.replace("[path]", `"${tool.defaultFilename}"`);
    } else if (initialPrompt.includes("[title]")) {
      initialPrompt = initialPrompt.replace("[title]", `"${defaultTitle}"`);
    } else {
      initialPrompt = `${tool.defaultPromptTemplate} "${defaultTitle}"`;
    }

    if (onQuickPrompt) {
      onQuickPrompt(initialPrompt);
    } else if (onNavigate) {
      onNavigate("agent");
    }
  };

  // Launch from Configurator Modal
  const handleDispatchFromModal = () => {
    if (!liveAssembledPrompt) return;
    if (onQuickPrompt) {
      onQuickPrompt(liveAssembledPrompt);
    } else if (onNavigate) {
      onNavigate("agent");
    }
    handleCloseConfigurator();
  };

  // Copy Prompt to Clipboard
  const handleCopyPrompt = async () => {
    if (!liveAssembledPrompt) return;
    try {
      await navigator.clipboard.writeText(liveAssembledPrompt);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2000);
    } catch (e) {
      console.error("Clipboard copy failed:", e);
    }
  };

  // Run dev tool in Dev Utilities tab
  const handleRunDevTool = (tool: ProductivityTool) => {
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
    <div className="h-full overflow-y-auto p-4 sm:p-6 space-y-6 max-w-7xl mx-auto relative select-none">
      {/* ══════════════════════════════════════════════════════════════════
         HEADER & TOP NAVIGATION BAR
         ══════════════════════════════════════════════════════════════════ */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#202127] pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-[10px] font-mono text-[#76B900] bg-[#1a2512] px-2 py-0.5 rounded border border-[#76B900]/30 flex items-center gap-1.5 font-bold tracking-wider">
              <span className="w-1.5 h-1.5 rounded-full bg-[#76B900] animate-pulse" />
              SANCTUM LOCAL TOOL STUDIO
            </span>
            <span className="text-[11px] font-mono text-neutral-400">
              Zero Network Egress • Sandboxed Generation & Execution
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Local Tools & Generative Studio
          </h1>
          <p className="text-xs text-neutral-400 mt-0.5 max-w-2xl leading-relaxed">
            Generate publication-ready PDF reports, build PowerPoint presentations and Excel sheets, synthesize sandboxed code, or inspect low-level Model Context Protocol (MCP) primitives.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1.5 bg-[#101115] p-1 rounded-xl border border-[#23242c] shrink-0 self-start md:self-auto">
          <button
            type="button"
            onClick={() => setActiveTab("generative")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-mono transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "generative"
                ? "bg-[#76B900] text-black font-semibold shadow-md shadow-[#76B900]/20"
                : "text-neutral-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Generative Studio ({GENERATIVE_TOOLS.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("mcp")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-mono transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "mcp"
                ? "bg-[#76B900] text-black font-semibold shadow-md shadow-[#76B900]/20"
                : "text-neutral-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            MCP Primitives ({MCP_PRIMITIVES.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("utilities")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-mono transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "utilities"
                ? "bg-[#76B900] text-black font-semibold shadow-md shadow-[#76B900]/20"
                : "text-neutral-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            Dev Utilities ({PRODUCTIVITY_TOOLS.length})
          </button>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
         TAB 1: GENERATIVE STUDIO (SIGNATURE TOOLS MERGED FROM INTEGRATE)
         ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "generative" && (
        <div className="space-y-6">
          {/* Subheader & Search / Category Filters */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0d0e12]/80 backdrop-blur p-3.5 rounded-xl border border-[#202127]">
            {/* Category Pills */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {(
                [
                  { id: "all", label: "All Tools" },
                  { id: "document", label: "Document Creation" },
                  { id: "code", label: "Code & Execution" },
                  { id: "workspace", label: "Workspace & Security" },
                ] as const
              ).map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-3 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer ${
                    selectedCategory === cat.id
                      ? "bg-[#1f2b14] text-[#86e810] border border-[#76B900]/40 font-semibold"
                      : "bg-[#14151b] text-neutral-400 border border-transparent hover:border-neutral-700 hover:text-neutral-200"
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {/* Quick Search */}
            <div className="relative min-w-[220px]">
              <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tools or extensions..."
                className="w-full bg-[#14151b] text-xs text-white placeholder-neutral-500 pl-8 pr-3 py-1.5 rounded-lg border border-[#262730] focus:outline-none focus:border-[#76B900]/50 font-mono transition-all"
              />
            </div>
          </div>

          {/* Tool Launch Grid (Responsive 3-Column Layout with Elevated Styling) */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredGenerativeTools.map((tool) => {
              const Icon = tool.icon;
              const isDirectNav = Boolean(tool.targetScreen);

              return (
                <motion.div
                  key={tool.id}
                  whileHover={{ y: -3 }}
                  transition={{ duration: 0.16 }}
                  onClick={() => handleOpenConfigurator(tool)}
                  className="group relative rounded-xl bg-[#111216] border border-[#21232b] hover:border-[#76B900]/50 p-5 flex flex-col justify-between transition-all cursor-pointer shadow-lg hover:shadow-[#76B900]/5 overflow-hidden"
                >
                  {/* Subtle Top Gradient Glow */}
                  <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#76B900]/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                  <div>
                    {/* Top Meta Row */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="flex items-center gap-2.5">
                        <div
                          className={`w-9 h-9 rounded-lg flex items-center justify-center border transition-all ${tool.iconBg}`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <span className="text-[9px] font-mono tracking-widest text-neutral-500 block uppercase font-semibold">
                            {tool.index}
                          </span>
                          <span className="text-[10px] font-mono text-neutral-400">
                            {tool.categoryLabel}
                          </span>
                        </div>
                      </div>

                      {/* Output Extension Badge */}
                      <span
                        className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${tool.badgeColor}`}
                      >
                        {tool.extensionBadge}
                      </span>
                    </div>

                    {/* Title & Tagline */}
                    <h2 className="text-base font-bold text-white group-hover:text-[#86e810] transition-colors flex items-center gap-1.5">
                      {tool.title}
                    </h2>
                    <p className="text-xs text-neutral-300 font-medium mt-1 leading-snug">
                      {tool.tagline}
                    </p>
                    <p className="text-[11px] text-neutral-400 mt-1.5 leading-relaxed">
                      {tool.description}
                    </p>

                    {/* Capabilities Tags */}
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {tool.capabilities.map((cap, idx) => (
                        <span
                          key={idx}
                          className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#171820] text-neutral-400 border border-white/5"
                        >
                          • {cap}
                        </span>
                      ))}
                    </div>

                    {/* Prompt Preview Snippet */}
                    {!isDirectNav && (
                      <div className="mt-3.5 p-2 rounded-lg bg-[#0a0a0d] border border-white/5 font-mono text-[10px] text-neutral-400 truncate group-hover:border-[#76B900]/20 transition-colors">
                        <span className="text-[#76B900] mr-1.5 font-bold">&gt;</span>
                        <span className="text-neutral-300">{tool.defaultPromptTemplate}</span>
                      </div>
                    )}
                  </div>

                  {/* Bottom Action Row */}
                  <div className="flex items-center gap-2 pt-4 mt-2 border-t border-white/5">
                    {isDirectNav ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (tool.targetScreen && onNavigate) onNavigate(tool.targetScreen);
                        }}
                        className="w-full py-1.5 px-3 rounded-lg bg-[#191b22] hover:bg-[#222530] text-neutral-200 text-xs font-mono flex items-center justify-center gap-1.5 border border-white/5 transition-all cursor-pointer"
                      >
                        <span>Open {tool.title}</span>
                        <ArrowUpRight className="w-3.5 h-3.5 text-[#76B900]" />
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenConfigurator(tool);
                          }}
                          className="flex-1 py-1.5 px-3 rounded-lg bg-[#1b2513] hover:bg-[#25351a] text-[#86e810] border border-[#76B900]/40 text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all cursor-pointer shadow-sm"
                        >
                          <SlidersHorizontal className="w-3 h-3 text-[#76B900]" />
                          <span>Configure & Build</span>
                        </button>

                        <button
                          type="button"
                          onClick={(e) => handleQuickLaunchDirect(tool, e)}
                          title="Quick launch template directly in Agent"
                          className="p-1.5 rounded-lg bg-[#161820] hover:bg-[#222532] text-neutral-300 hover:text-white border border-white/5 transition-colors cursor-pointer"
                        >
                          <ArrowUpRight className="w-4 h-4 text-[#76B900]" />
                        </button>
                      </>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
         TAB 2: MCP PROTOCOL PRIMITIVES (LOW-LEVEL RPC SPECIFICATIONS)
         ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "mcp" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Tool Selection Rail */}
          <div className="space-y-2">
            <h2 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
              Registered MCP Tool Primitives ({MCP_PRIMITIVES.length})
            </h2>
            <div className="space-y-1.5">
              {MCP_PRIMITIVES.map((tool) => {
                const Icon = tool.icon;
                const isSelected = selectedMCPTool.id === tool.id;

                return (
                  <div
                    key={tool.id}
                    onClick={() => setSelectedMCPTool(tool)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                      isSelected
                        ? "bg-[#141d0f] border-[#76B900] shadow-md shadow-[#76B900]/10"
                        : "bg-[#131418] border-[#22242c] hover:border-[#333742]"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                          isSelected
                            ? "bg-[#76B900] text-black"
                            : "bg-[#1b1c24] text-neutral-400"
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="text-xs font-mono font-semibold text-white">{tool.name}</h3>
                        <span className="text-[10px] font-mono text-neutral-500">{tool.category}</span>
                      </div>
                    </div>
                    <ChevronRight className={`w-4 h-4 ${isSelected ? "text-[#76B900]" : "text-neutral-600"}`} />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected Tool Details */}
          <div className="lg:col-span-2 glass-panel rounded-xl p-6 border border-[#242630] space-y-5 bg-[#0f1014]">
            <div>
              <span className="text-[10px] font-mono text-[#86e810] bg-[#162210] px-2 py-0.5 rounded border border-[#76B900]/30 inline-block mb-2 font-bold">
                {selectedMCPTool.category.toUpperCase()} • MCP PRIMITIVE
              </span>
              <h2 className="text-xl font-bold font-mono text-white">{selectedMCPTool.name}</h2>
              <p className="text-xs text-neutral-300 mt-1 leading-relaxed">
                {selectedMCPTool.description}
              </p>
            </div>

            {/* Parameters Schema */}
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
                Input Parameters Schema
              </h3>
              <div className="rounded-lg bg-[#090a0d] border border-[#20222a] p-3.5 space-y-2">
                {Object.entries(selectedMCPTool.parameters).map(([key, type]) => (
                  <div key={key} className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs font-mono border-b border-white/5 pb-1.5 last:border-b-0 last:pb-0">
                    <span className="text-neutral-200 font-semibold">{key}</span>
                    <span className="text-[#86e810] bg-[#141a10] px-2 py-0.5 rounded text-[11px] font-normal">{type}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Sample Agent Call */}
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
                Sample Agent Tool Call (JSON-RPC)
              </h3>
              <pre className="rounded-lg bg-[#070709] border border-[#20222a] p-3 text-xs font-mono text-neutral-300 overflow-x-auto whitespace-pre-wrap">
                {selectedMCPTool.sampleInput}
              </pre>
            </div>

            {/* Sample Return Output */}
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-neutral-400 mb-2">
                Sample Return Output
              </h3>
              <pre className="rounded-lg bg-[#070709] border border-[#20222a] p-3 text-xs font-mono text-[#86e810] overflow-x-auto whitespace-pre-wrap">
                {selectedMCPTool.sampleOutput}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
         TAB 3: DEV UTILITIES (LOCAL CODE & SYSTEM AUDIT COMMANDS)
         ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "utilities" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {PRODUCTIVITY_TOOLS.map((tool) => {
              const Icon = tool.icon;
              const isRunning = runningToolId === tool.id;
              const hasRun = toolOutputs[tool.id] !== undefined;

              return (
                <div
                  key={tool.id}
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
                      onClick={() => handleRunDevTool(tool)}
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
                </div>
              );
            })}
          </div>

          {/* Console Output Drawer */}
          {activePreviewTool && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl p-5 bg-[#0f1013] border border-[#2c2d36] space-y-3 font-mono text-xs"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-[#76B900]" />
                  <span className="font-semibold text-white">{activePreviewTool.title} Output</span>
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
      )}

      {/* ══════════════════════════════════════════════════════════════════
         INTERACTIVE PROMPT CONFIGURATOR / COMPOSER MODAL
         ══════════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {activeConfigTool && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 10 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="w-full max-w-2xl bg-[#111216] border border-[#2e313d] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
            >
              {/* Modal Header */}
              <div className="p-4 sm:p-5 border-b border-[#22242e] bg-[#14161c] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center border ${activeConfigTool.iconBg}`}
                  >
                    <activeConfigTool.icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-bold text-white">
                        Configure {activeConfigTool.title}
                      </h2>
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border ${activeConfigTool.badgeColor}`}
                      >
                        {activeConfigTool.extensionBadge}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-neutral-400">
                      {activeConfigTool.tagline}
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleCloseConfigurator}
                  className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 overflow-y-auto space-y-4">
                {/* Preset Chips */}
                {activeConfigTool.presets.length > 0 && (
                  <div>
                    <label className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider block mb-1.5">
                      Quick Preset Templates:
                    </label>
                    <div className="flex items-center gap-2 flex-wrap">
                      {activeConfigTool.presets.map((preset, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            setCustomTitle(preset.title);
                            setCustomSubtitle(preset.subtitle || "");
                            setCustomDetails(preset.details);
                            if (preset.filename) setCustomFilename(preset.filename);
                          }}
                          className="px-2.5 py-1 rounded-lg text-xs font-mono bg-[#181a22] hover:bg-[#202330] text-neutral-300 hover:text-white border border-[#2b2e3c] transition-all cursor-pointer flex items-center gap-1.5"
                        >
                          <Sparkles className="w-3 h-3 text-[#76B900]" />
                          <span>{preset.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Field 1: Document / Task Title */}
                <div>
                  <label className="text-[11px] font-mono uppercase text-neutral-300 font-semibold block mb-1">
                    Document or Task Title <span className="text-[#76B900]">*</span>
                  </label>
                  <input
                    type="text"
                    value={customTitle}
                    onChange={(e) => setCustomTitle(e.target.value)}
                    placeholder={activeConfigTool.defaultTitlePlaceholder}
                    className="w-full bg-[#0b0c0f] text-xs text-white placeholder-neutral-500 px-3 py-2 rounded-lg border border-[#262833] focus:outline-none focus:border-[#76B900] font-sans transition-all"
                  />
                </div>

                {/* Field 2: Subtitle (Only for multi-page documents) */}
                {["make_pdf", "make_ppt", "make_docx"].includes(activeConfigTool.id) && (
                  <div>
                    <label className="text-[11px] font-mono uppercase text-neutral-300 font-semibold block mb-1">
                      Subtitle / Category Scope (Optional)
                    </label>
                    <input
                      type="text"
                      value={customSubtitle}
                      onChange={(e) => setCustomSubtitle(e.target.value)}
                      placeholder="e.g. Zero Network Egress & Airgap Audit"
                      className="w-full bg-[#0b0c0f] text-xs text-white placeholder-neutral-500 px-3 py-2 rounded-lg border border-[#262833] focus:outline-none focus:border-[#76B900] font-sans transition-all"
                    />
                  </div>
                )}

                {/* Field 3: Details & Focus Areas */}
                <div>
                  <label className="text-[11px] font-mono uppercase text-neutral-300 font-semibold block mb-1">
                    Prompt Details & Focus Outline
                  </label>
                  <textarea
                    rows={4}
                    value={customDetails}
                    onChange={(e) => setCustomDetails(e.target.value)}
                    placeholder={activeConfigTool.defaultDetailsPlaceholder}
                    className="w-full bg-[#0b0c0f] text-xs text-neutral-200 placeholder-neutral-500 p-3 rounded-lg border border-[#262833] focus:outline-none focus:border-[#76B900] font-sans resize-none leading-relaxed transition-all"
                  />
                </div>

                {/* Field 4: Target Filename (Optional) */}
                {activeConfigTool.defaultFilename && (
                  <div>
                    <label className="text-[11px] font-mono uppercase text-neutral-300 font-semibold block mb-1">
                      Output Workspace Filename
                    </label>
                    <input
                      type="text"
                      value={customFilename}
                      onChange={(e) => setCustomFilename(e.target.value)}
                      placeholder={activeConfigTool.defaultFilename}
                      className="w-full bg-[#0b0c0f] text-xs text-[#86e810] placeholder-neutral-600 px-3 py-1.5 rounded-lg border border-[#262833] focus:outline-none focus:border-[#76B900] font-mono transition-all"
                    />
                  </div>
                )}

                {/* Live Assembled Prompt Preview */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono uppercase text-neutral-400 font-bold">
                      Live Prompt Preview (Sent to Agent):
                    </span>
                    <button
                      type="button"
                      onClick={handleCopyPrompt}
                      className="text-[10px] font-mono text-neutral-400 hover:text-white flex items-center gap-1 cursor-pointer"
                    >
                      {copiedPrompt ? (
                        <>
                          <Check className="w-3 h-3 text-[#76B900]" />
                          <span className="text-[#76B900]">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="p-3 rounded-lg bg-[#07080a] border border-[#22242e] font-mono text-[11px] text-[#86e810] whitespace-pre-wrap max-h-36 overflow-y-auto leading-relaxed">
                    {liveAssembledPrompt}
                  </div>
                </div>
              </div>

              {/* Modal Footer Actions */}
              <div className="p-4 bg-[#14161c] border-t border-[#22242e] flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={handleCloseConfigurator}
                  className="px-4 py-2 rounded-lg text-xs font-mono text-neutral-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopyPrompt}
                    className="px-3.5 py-2 rounded-lg bg-[#1a1c24] hover:bg-[#252834] text-neutral-200 border border-white/5 text-xs font-mono flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    {copiedPrompt ? <Check className="w-3.5 h-3.5 text-[#76B900]" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedPrompt ? "Copied" : "Copy Prompt"}</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleDispatchFromModal}
                    className="px-4 py-2 rounded-lg bg-[#76B900] hover:bg-[#86d000] text-black font-semibold text-xs font-mono flex items-center gap-2 shadow-lg shadow-[#76B900]/25 transition-all cursor-pointer"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Launch in Agent Chat</span>
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
