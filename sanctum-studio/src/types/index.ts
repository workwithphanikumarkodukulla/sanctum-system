export type ScreenType =
  | "overview"
  | "workspace"
  | "agent"
  | "models"
  | "lkb"
  | "tools"
  | "locker"
  | "security"
  | "logs";

export interface SystemTelemetry {
  status: "ok" | "warning" | "error";
  connectedToBackend: boolean;
  loopbackCalls: number;
  externalCalls: number;
  activeModel: string;
  backendPort: number;
  vramUsageGb: number;
  totalVramGb: number;
  ramUsagePercent: number;
  cpuUsagePercent: number;
  contextWindowTokens: number;
  maxContextTokens: number;
  averageLatencyMs: number;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: "Ollama" | "LM Studio" | "vLLM" | "llama.cpp";
  parameters: string;
  quantization: string;
  contextSize: string;
  latencyMs: number;
  vram: string;
  isLocal: boolean;
  active: boolean;
  specialty: "Coding" | "Reasoning" | "General" | "Vision";
  description: string;
}

export interface ToolActionStep {
  tool: string;
  input: Record<string, any>;
  output: string;
  duration: string;
  status: "completed" | "running" | "error";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  toolsExecuted?: ToolActionStep[];
  traceNodes?: any[];
  tokensUsed?: number;
  model?: string;
  durationMs?: number;
  durationS?: number;
  workflowTrace?: any;
  debugTrace?: string;
  hasApproval?: boolean;
  approvalQuestions?: any[];
  approvalStatus?: "pending" | "approved" | "skipped";
  isMath?: boolean;
}


export interface FileItem {
  name: string;
  path: string;
  isDirectory: boolean;
  size?: string;
  modified?: string;
  content?: string;
  language?: string;
  children?: FileItem[];
  isLocked?: boolean;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR" | "DEBUG" | "AUDIT";
  source: string;
  message: string;
}

export interface PacketTrace {
  id: string;
  timestamp: string;
  srcIp: string;
  dstIp: string;
  port: number;
  protocol: string;
  size: number;
  status: "LOOPBACK_OK" | "EGRESS_BLOCKED";
}

export interface KnowledgeChunk {
  id: string;
  title: string;
  source: string;
  snippet: string;
  score: number;
  chunksCount: number;
}

export interface WiresharkPacket {
  no: number;
  time: string;
  iface: string;
  src: string;
  dst: string;
  protocol: string;
  length: number;
  info: string;
  verdict: "LOOPBACK_OK" | "EGRESS_BLOCKED" | "EGRESS_DROPPED";
  dissectionTree?: DissectionNode[];
  hexDump?: string;
}

export interface DissectionNode {
  label: string;
  value?: string;
  children?: DissectionNode[];
  isOpen?: boolean;
}

export interface NetworkAudit {
  externalCalls: number;
  externalCallsBlocked: number;
  loopbackCalls: number;
  ollamaPort: { count: number; status: string };
  docEnginePort: { count: number; status: string };
  airgapIntegrityPct: number;
  recentEvents: string[];
}

export interface RoutePreviewResult {
  selectedModel: string;
  reason: string;
  scores: Record<string, number>;
}
