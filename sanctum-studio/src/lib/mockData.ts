import {
  ModelInfo,
  SystemTelemetry,
  ChatMessage,
  FileItem,
  LogEntry,
  PacketTrace,
  KnowledgeChunk,
} from "@/types";

export const initialTelemetry: SystemTelemetry = {
  status: "ok",
  connectedToBackend: true,
  loopbackCalls: 1482,
  externalCalls: 0,
  activeModel: "gemma4:latest",
  backendPort: 5050,
  vramUsageGb: 5.4,
  totalVramGb: 16.0,
  ramUsagePercent: 42,
  cpuUsagePercent: 18,
  contextWindowTokens: 4192,
  maxContextTokens: 32768,
  averageLatencyMs: 38,
};

export const sampleModels: ModelInfo[] = [
  {
    id: "gemma4:latest",
    name: "Gemma 4 (Local)",
    provider: "Ollama",
    parameters: "9.2B",
    quantization: "Q4_K_M",
    contextSize: "32k",
    latencyMs: 38,
    vram: "5.8 GB",
    isLocal: true,
    active: true,
    specialty: "Coding",
    description: "Ultra-fast code generation and tool calling with native loopback inference.",
  },
  {
    id: "deepseek-coder:6.7b",
    name: "DeepSeek Coder 6.7B",
    provider: "Ollama",
    parameters: "6.7B",
    quantization: "Q5_K_S",
    contextSize: "16k",
    latencyMs: 44,
    vram: "4.9 GB",
    isLocal: true,
    active: false,
    specialty: "Coding",
    description: "Specialized in Python, Rust, JavaScript, and refactoring complex algorithmic code.",
  },
  {
    id: "qwen2.5-coder:7b",
    name: "Qwen 2.5 Coder 7B",
    provider: "Ollama",
    parameters: "7.6B",
    quantization: "Q4_K_M",
    contextSize: "32k",
    latencyMs: 41,
    vram: "5.1 GB",
    isLocal: true,
    active: false,
    specialty: "Reasoning",
    description: "Exceptional system design synthesis, edge case validation, and tool orchestrating.",
  },
  {
    id: "mistral:7b",
    name: "Mistral Instruct 7B",
    provider: "Ollama",
    parameters: "7.2B",
    quantization: "Q4_0",
    contextSize: "8k",
    latencyMs: 32,
    vram: "4.2 GB",
    isLocal: true,
    active: false,
    specialty: "General",
    description: "Fast conversational assistant for documentation, summaries, and code reviews.",
  },
];

export const sampleChatMessages: ChatMessage[] = [
  {
    id: "msg-1",
    role: "user",
    content: "Audit our calculator.py file and implement a safe reciprocal division helper with zero checking.",
    timestamp: "20:41:10",
  },
  {
    id: "msg-2",
    role: "assistant",
    content: "I have analyzed `calculator.py` in your workspace. The file currently contains basic arithmetic functions (`add`, `subtract`, `multiply`, `divide`).\n\nI'll inspect the file content, implement `reciprocal(x)` with strict boundary validation, and run test verification in the local Python sandbox.",
    timestamp: "20:41:12",
    tokensUsed: 312,
    model: "gemma4:latest",
    toolsExecuted: [
      {
        tool: "file_tool (read)",
        input: { file_path: "calculator.py" },
        output: "Successfully read calculator.py (42 lines).\nFunctions found: add, subtract, multiply, divide.",
        duration: "14ms",
        status: "completed",
      },
      {
        tool: "python_sandbox (exec)",
        input: { code: "import calculator\nprint(calculator.divide(10, 2))" },
        output: "Output: 5.0\nProcess finished with exit code 0",
        duration: "28ms",
        status: "completed",
      },
    ],
    traceNodes: [
      {
        id: "tr-1",
        type: "reasoning",
        sentences: [
          "Inspecting calculator.py AST structure and verifying arithmetic functions...",
          "Located zero-division hazard in divide(x, y). Planning guard assertion and reciprocal helper.",
        ],
        durationSeconds: 1.6,
        status: "completed",
      },
      {
        id: "tr-2",
        type: "terminal",
        primary: "Terminal",
        secondary: "python3 -m unittest",
        command: "python3 -m unittest tests/test_calculator.py",
        output: "..\n----------------------------------------------------------------------\nRan 2 tests in 0.014s\n\nOK (all tests passed over loopback sandbox)",
        exitCode: 0,
        durationMs: 140,
        status: "completed",
      },
      {
        id: "tr-3",
        type: "diffs",
        primary: "Patch",
        secondary: "calculator.py",
        diffFile: "calculator.py",
        add: 3,
        del: 1,
        diffRows: [
          { old: 18, cur: 18, type: "ctx", text: "def divide(x: float, y: float) -> float:" },
          { old: 19, cur: null, type: "del", text: "-    return x / y" },
          { old: null, cur: 19, type: "add", text: "+    if y == 0:" },
          { old: null, cur: 20, type: "add", text: "+        raise ValueError('Cannot divide by zero')" },
          { old: null, cur: 21, type: "add", text: "+    return x / y" },
        ],
        status: "completed",
      },
    ],
    hasApproval: true,
    approvalStatus: "pending",
    isMath: true,
  },
];

export const sampleWorkspaceFiles: FileItem[] = [
  {
    name: "calculator.py",
    path: "calculator.py",
    isDirectory: false,
    size: "640 B",
    modified: "Just now",
    language: "python",
    content: `# calculator.py - Sanctum Local Agent Workspace
"""
Safe mathematical calculation library with loopback telemetry.
"""

def add(x: float, y: float) -> float:
    """Return the sum of two numbers."""
    return x + y

def subtract(x: float, y: float) -> float:
    """Return the difference of two numbers."""
    return x - y

def multiply(x: float, y: float) -> float:
    """Return the product of two numbers."""
    return x * y

def divide(x: float, y: float) -> float:
    """Return the quotient of two numbers."""
    if y == 0:
        raise ZeroDivisionError("Cannot divide by zero in sovereign execution.")
    return x / y

def reciprocal(x: float) -> float:
    """Return the reciprocal (1/x) with safe zero guard."""
    if x == 0:
        raise ValueError("Mathematical singularity: reciprocal of 0 is undefined.")
    return 1.0 / x

if __name__ == "__main__":
    print(f"Sanctum Math Test: 10 / 2 = {divide(10, 2)}")
    print(f"Sanctum Reciprocal: 1 / 4 = {reciprocal(4)}")
`,
  },
  {
    name: "greet.py",
    path: "greet.py",
    isDirectory: false,
    size: "420 B",
    modified: "1 hour ago",
    language: "python",
    content: `def greet(name: str) -> str:
    return f"Welcome to Sanctum, {name}! Local-first and private."

if __name__ == "__main__":
    print(greet("Operator"))
`,
  },
  {
    name: "to.rs",
    path: "to.rs",
    isDirectory: false,
    size: "1.1 KB",
    modified: "Yesterday",
    language: "rust",
    content: `// Sanctum Sovereign Rust Component
pub struct MemoryBuffer {
    pub capacity: usize,
    pub data: Vec<u8>,
}

impl MemoryBuffer {
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity,
            data: Vec::with_capacity(capacity),
        }
    }
}
`,
  },
  {
    name: "generated",
    path: "generated",
    isDirectory: true,
    children: [
      {
        name: "PV_204B_Inspection.docx",
        path: "generated/PV_204B_Inspection.docx",
        isDirectory: false,
        size: "24.5 KB",
        modified: "2 days ago",
        language: "binary",
      },
      {
        name: "sample_about.pdf",
        path: "generated/sample_about.pdf",
        isDirectory: false,
        size: "118 KB",
        modified: "3 days ago",
        language: "pdf",
      },
    ],
  },
  {
    name: "sample_inspection.pdf",
    path: "sample_inspection.pdf",
    isDirectory: false,
    size: "420 KB",
    modified: "Sep 7",
    language: "pdf",
  },
];

export const sampleLogs: LogEntry[] = [
  {
    id: "log-1",
    timestamp: "20:50:01.102",
    level: "INFO",
    source: "SOVEREIGN_NET",
    message: "Network boundary check passed: 100% loopback on 127.0.0.1:5050. Zero egress packets.",
  },
  {
    id: "log-2",
    timestamp: "20:50:04.220",
    level: "DEBUG",
    source: "LLM_ROUTER",
    message: "Ollama instance detected. Loaded weights for gemma4:latest into GPU memory.",
  },
  {
    id: "log-3",
    timestamp: "20:50:15.541",
    level: "AUDIT",
    source: "MCP_GATEWAY",
    message: "Tool 'file_tool.read' approved by policy. Target: workspace/calculator.py",
  },
  {
    id: "log-4",
    timestamp: "20:50:28.910",
    level: "INFO",
    source: "LKB_INDEXER",
    message: "Local vector index synced: 14 documents, 284 chunks embedded via loopback model.",
  },
  {
    id: "log-5",
    timestamp: "20:50:45.301",
    level: "WARN",
    source: "EGRESS_MONITOR",
    message: "External DNS probe intercepted and dropped: Sovereign mode active.",
  },
];

export const samplePacketTraces: PacketTrace[] = [
  { id: "pkt-1", timestamp: "20:51:10.012", srcIp: "127.0.0.1", dstIp: "127.0.0.1", port: 5050, protocol: "TCP/HTTP", size: 482, status: "LOOPBACK_OK" },
  { id: "pkt-2", timestamp: "20:51:10.018", srcIp: "127.0.0.1", dstIp: "127.0.0.1", port: 11434, protocol: "OLLAMA/API", size: 1024, status: "LOOPBACK_OK" },
  { id: "pkt-3", timestamp: "20:51:11.450", srcIp: "127.0.0.1", dstIp: "127.0.0.1", port: 5050, protocol: "TCP/JSON", size: 312, status: "LOOPBACK_OK" },
  { id: "pkt-4", timestamp: "20:51:12.190", srcIp: "127.0.0.1", dstIp: "142.250.190.46", port: 443, protocol: "TLS", size: 64, status: "EGRESS_BLOCKED" },
  { id: "pkt-5", timestamp: "20:51:14.331", srcIp: "127.0.0.1", dstIp: "127.0.0.1", port: 11434, protocol: "OLLAMA/STREAM", size: 2048, status: "LOOPBACK_OK" },
];

export const sampleKnowledge: KnowledgeChunk[] = [
  {
    id: "kb-1",
    title: "Sanctum Architecture Spec",
    source: "architecture.txt",
    snippet: "Local-first desktop agent studio running exclusively over loopback sockets. All tools bound via strict MCP schema without internet dependencies.",
    score: 0.94,
    chunksCount: 18,
  },
  {
    id: "kb-2",
    title: "Sovereign Network Boundary Policy",
    source: "sovereign_network.py",
    snippet: "Every egress packet outside 127.0.0.1 and ::1 is dropped at the filter layer. Verification token signed locally.",
    score: 0.89,
    chunksCount: 6,
  },
  {
    id: "kb-3",
    title: "Inspection & Certification Guidelines",
    source: "sample_inspection.pdf",
    snippet: "Mechanical integrity standards for pressure vessels according to ASME Section VIII Division 1 with automated compliance logs.",
    score: 0.82,
    chunksCount: 24,
  },
];
