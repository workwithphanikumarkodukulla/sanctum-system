"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface GlideMenuProps extends React.HTMLAttributes<HTMLDivElement> {
  highlightClassName?: string;
  children: React.ReactNode;
}

export function GlideMenu({
  className,
  highlightClassName,
  children,
  ...props
}: GlideMenuProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [highlight, setHighlight] = React.useState<{
    top: number;
    height: number;
    opacity: number;
  }>({
    top: 0,
    height: 0,
    opacity: 0,
  });

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const target = (e.target as HTMLElement).closest("[data-menu-row]") as HTMLElement | null;
    if (target && containerRef.current) {
      const containerRect = containerRef.current.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      setHighlight({
        top: targetRect.top - containerRect.top,
        height: targetRect.height,
        opacity: 1,
      });
    }
  };

  const handlePointerLeave = () => {
    setHighlight((prev) => ({ ...prev, opacity: 0 }));
  };

  return (
    <div
      ref={containerRef}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      className={cn("relative", className)}
      {...props}
    >
      <div
        style={{
          transform: `translateY(${highlight.top}px)`,
          height: `${highlight.height}px`,
          opacity: highlight.opacity,
          transition: "transform 150ms cubic-bezier(0.2, 0, 0, 1), height 150ms cubic-bezier(0.2, 0, 0, 1), opacity 150ms ease-out",
        }}
        className={cn("pointer-events-none absolute left-0 right-0 z-0", highlightClassName)}
        aria-hidden="true"
      />
      {children}
    </div>
  );
}

export default GlideMenu;
