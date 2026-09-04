# Sanctum UI Components Library

A set of modular, interactive UI components for AI Agent workflows, thinking trace visualization, streaming responses, diff inspections, and terminal command execution.

## Components Included

| Component | Description |
| :--- | :--- |
| **`AgentWorkflow`** | Multi-phase agent workflow orchestrator coordinating thinking state and message streaming. |
| **`ThinkingState`** | Collapsible reasoning and tool execution timeline with live timer and status icons. |
| **`NestedReasoningBlock`** | Interactive thought reasoning expander with line cadence and height masking. |
| **`TerminalCommand`** | Bash / CLI command viewer with exit codes, duration metrics, syntax highlighting, and copy-to-clipboard. |
| **`FileDiff`** | Code diff viewer with additions/deletions gutters, line numbers, and patch copy. |
| **`StreamingText`** | Typewriter token streamer for LLM message generation. |
| **`PixelDotsLoader`** | 3x3 pixel matrix pulsating loader. |

---

## Installation & Peer Dependencies

Ensure your project has the following packages installed:

```bash
npm install lucide-react clsx tailwind-merge
# or
pnpm add lucide-react clsx tailwind-merge
```

---

## Usage Examples

### 1. Import from Barrel

```tsx
import { 
  AgentWorkflow, 
  ThinkingState, 
  TerminalCommand, 
  FileDiff, 
  StreamingText,
  PixelDotsLoader 
} from "@/Components";
```

### 2. Multi-Phase Agent Workflow

```tsx
import { AgentWorkflow } from "@/Components";
import type { AgentPhase } from "@/Components";

const samplePhases: AgentPhase[] = [
  {
    trace: [
      {
        type: "reasoning",
        sentences: [
          "Analyzing workspace configuration and checking installed models...",
          "Located Ollama instance at 127.0.0.1:11434 with qwen2.5-coder:7b.",
        ],
        durationSeconds: 2.4,
      },
      {
        type: "terminal",
        command: "npm test -- --coverage",
        output: "✓ 14 tests passed in 1.2s",
        exitCode: 0,
        durationMs: 1200,
      },
      {
        type: "diffs",
        primary: "Edit",
        secondary: "app/agent.py",
        diffFile: "app/agent.py",
        diffRows: [
          { old: 12, cur: 12, type: "ctx", text: "def run_agent():" },
          { old: null, cur: 13, type: "add", text: "    model = Ollama(model='qwen2.5-coder:7b')" },
          { old: 13, cur: null, type: "del", text: "    model = None" },
        ],
      },
    ],
    message: "I have verified your tests and updated the model configuration.",
  },
];

export default function WorkflowPage() {
  return (
    <div className="max-w-2xl p-6">
      <AgentWorkflow phases={samplePhases} />
    </div>
  );
}
```

### 3. Individual Terminal & Diff Viewers

```tsx
import { TerminalCommand, FileDiff } from "@/Components";

export function ExecutionDemo() {
  return (
    <div className="space-y-4">
      <TerminalCommand
        command="git status"
        output="On branch main\nYour branch is up to date with 'origin/main'."
        exitCode={0}
        durationMs={45}
      />

      <FileDiff
        file="src/config.ts"
        rows={[
          { old: 1, cur: 1, type: "ctx", text: "export const PORT = 3000;" },
          { old: 2, cur: null, type: "del", text: "- const DEBUG = true;" },
          { old: null, cur: 2, type: "add", text: "+ const DEBUG = process.env.NODE_ENV !== 'production';" },
        ]}
      />
    </div>
  );
}
```
