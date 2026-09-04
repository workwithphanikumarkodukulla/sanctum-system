"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { StreamingTextProps } from "./types";

export function StreamingText({
  text,
  speed = 18,
  chunkSize = 2,
  className,
  onComplete,
  ...props
}: StreamingTextProps) {
  const [shown, setShown] = React.useState("");
  const onCompleteRef = React.useRef(onComplete);
  onCompleteRef.current = onComplete;

  React.useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      i += chunkSize;
      const nextText = text.slice(0, i);
      setShown(nextText);
      if (i >= text.length) {
        clearInterval(id);
        onCompleteRef.current?.();
      }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed, chunkSize]);

  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className={cn(
        "font-sans text-[14.5px] leading-relaxed text-foreground/90 select-text whitespace-pre-line text-pretty",
        className
      )}
      {...props}
    >
      {shown}
    </div>
  );
}
