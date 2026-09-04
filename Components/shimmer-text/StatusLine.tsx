"use client";

import { TextShimmer } from "./TextShimmer";

export function StatusLine({ text = "Agent is thinking ...", className }: { text?: string; className?: string }) {
  return (
    <TextShimmer className={`font-light text-md tracking-tight ${className || ""}`}>
      {text}
    </TextShimmer>
  );
}

export default StatusLine;
