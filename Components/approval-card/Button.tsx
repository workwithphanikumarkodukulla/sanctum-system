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
          variant === "ghost" && "bg-transparent text-muted-foreground hover:bg-muted/70 hover:text-foreground active:scale-[0.98]",
          variant === "accent" && "bg-foreground text-background hover:bg-foreground/90 active:scale-[0.98] shadow-xs",
          variant === "default" && "bg-primary text-primary-foreground hover:bg-primary/90 active:scale-[0.98]",
          variant === "outline" && "border border-border/80 bg-background text-foreground hover:bg-muted/50 active:scale-[0.98]",
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
