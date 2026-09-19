"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "ghost" | "accent" | "outline";
  size?: "sm" | "md" | "lg";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "sm", children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring select-none",
          // Size
          size === "sm" && "h-7 px-2.5 text-[12px] rounded-md",
          size === "md" && "h-8 px-3 text-[13px] rounded-md",
          size === "lg" && "h-9 px-4 text-[14px] rounded-lg",
          // Variants
          variant === "ghost" && "bg-transparent text-neutral-400 hover:bg-white/10 hover:text-white active:scale-[0.98]",
          variant === "accent" && "bg-[#76B900] text-black font-semibold hover:bg-[#88d400] active:scale-[0.98] shadow-sm shadow-[#76B900]/25",
          variant === "default" && "bg-[#22242a] text-neutral-100 hover:bg-[#2b2d35] hover:text-white border border-white/10 active:scale-[0.98]",
          variant === "outline" && "border border-white/15 bg-transparent text-neutral-200 hover:bg-white/5 hover:text-white active:scale-[0.98]",
          // Disabled
          disabled && "opacity-40 cursor-not-allowed pointer-events-none active:scale-100",
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
export default Button;
