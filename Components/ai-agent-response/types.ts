import * as React from "react";

export type DiffRow = {
  old?: number | null;
  cur?: number | null;
  type: "add" | "del" | "ctx";
  text: string;
};

export interface FileDiffProps {
  file: string;
  rows: DiffRow[];
  className?: string;
}

export interface TerminalCommandProps {
  command: string;
  output?: string;
  exitCode?: number;
  durationMs?: number;
  isRunning?: boolean;
  className?: string;
}

export type TraceNodeType =
  | "reasoning"
  | "step"
  | "search"
  | "tool"
  | "terminal"
  | "diffs"
  | (string & {});

export type DetailLine = {
  text: string;
  tone?: "add" | "del" | "ctx" | "muted" | "error";
};

export interface ToolDefinition<TArgs = any, TResult = any> {
  name: string;
  label?: string | ((args: TArgs) => string);
  icon?: any;
  iconClassName?: string;
  formatChip?: (args: TArgs, result?: TResult) => string;
  monoChip?: boolean;
  renderCustomContent?: (props: {
    args?: TArgs;
    result?: TResult;
    node: TraceNode<TArgs, TResult>;
  }) => React.ReactNode;
}

export type TraceNode<TArgs = any, TResult = any> = {
  id?: string;
  type: TraceNodeType;
  toolName?: string;
  sentences?: string[];
  durationSeconds?: number;
  primary?: string;
  secondary?: string;
  mono?: boolean;
  icon?: any;
  iconClassName?: string;
  status?: "pending" | "running" | "completed" | "failed";
  args?: TArgs;
  result?: TResult;
  command?: string;
  output?: string;
  exitCode?: number;
  durationMs?: number;
  add?: number;
  del?: number;
  diffRows?: DiffRow[];
  diffFile?: string;
  codeSnippet?: string;
  details?: DetailLine[];
  sources?: { name: string; url?: string }[];
  renderContent?: () => React.ReactNode;
};

export type AgentPhase = {
  trace: TraceNode[];
  message?: string;
};

export interface StreamingTextProps extends React.HTMLAttributes<HTMLDivElement> {
  text: string;
  speed?: number;
  chunkSize?: number;
  onComplete?: () => void;
}

export interface ThinkingStateProps extends React.HTMLAttributes<HTMLDivElement> {
  nodes?: TraceNode[];
  tools?: Record<string, ToolDefinition>;
  autoPlay?: boolean;
  defaultExpanded?: boolean;
  workingLabel?: string;
  onSettled?: () => void;
}

export interface AgentWorkflowProps extends React.HTMLAttributes<HTMLDivElement> {
  phases: AgentPhase[];
  tools?: Record<string, ToolDefinition>;
  workingLabel?: string;
  onComplete?: () => void;
}
