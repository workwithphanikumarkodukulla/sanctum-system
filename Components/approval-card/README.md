# ApprovalCard Component

A human-in-the-loop interactive question and decision flow card.

## Features
- **Vertical Stack Slide Animation**: Dynamically measures and animates card height per question.
- **Odometer Rolling Digits**: Smooth animated step counter (`1 / 3` → `2 / 3`).
- **Single & Multi-Select Support**: Radio (auto-advancing) and Checkbox (multi-select) answer modes.
- **Custom Write-In Inputs**: Interactive text input for custom user responses.
- **GlideMenu Highlight**: Fluid hover pill background tracking across menu options.
- **Resettable & Dismissible**: Built-in state callbacks and reset support.

---

## Usage Example

```tsx
import { ApprovalCard } from "@/Components/approval-card";
import type { ApprovalQuestion } from "@/Components/approval-card";

const customQuestions: ApprovalQuestion[] = [
  {
    q: "Select deployment environment target",
    type: "radio",
    options: ["Local Ollama Runtime", "Staging Cluster", "Production Edge"],
  },
  {
    q: "Select tools to authorize for this agent session",
    type: "check",
    options: ["File System Read/Write", "Terminal Command Execution", "SQL Database Access"],
  },
];

export function ApprovalWorkflow() {
  const handleSubmit = (answers: Record<number, number[]>) => {
    console.log("Approved choices:", answers);
  };

  return (
    <div className="p-6">
      <ApprovalCard
        questions={customQuestions}
        onSubmitted={handleSubmit}
      />
    </div>
  );
}
```
