"use client";

import { TextShimmer } from "@/components/ui/shimmer-text";

export function StatusLine() {
  return (
    <TextShimmer className="font-light text-md tracking-tight">
      Agent is thinking ...
    </TextShimmer>
  );
}

export default StatusLine;
