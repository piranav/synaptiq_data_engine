"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";
import { Loader2 } from "lucide-react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      isLoading,
      children,
      disabled,
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        className={clsx(
          "inline-flex items-center justify-center gap-2 rounded-md border font-medium",
          "transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/45 focus-visible:ring-offset-1 focus-visible:ring-offset-transparent",
          "disabled:opacity-60 disabled:cursor-not-allowed",

          variant === "primary" && "border-accent/40 bg-[var(--accent-soft)] text-[var(--accent)] hover:bg-[var(--hover-bg)] hover:shadow-[var(--glow-accent)]",
          variant === "secondary" && "border-border bg-surface text-primary hover:bg-[var(--hover-bg)]",
          variant === "ghost" && "border-transparent bg-transparent text-secondary hover:text-primary hover:bg-[var(--hover-bg)]",
          variant === "danger" && "border-danger/35 bg-danger/10 text-danger hover:bg-danger/16",

          size === "sm" && "h-8 px-3 text-callout",
          size === "md" && "h-10 px-4 text-body-small",
          size === "lg" && "h-[52px] px-6 text-body",

          className,
        )}
        disabled={isLoading || disabled}
        {...props}
      >
        {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : children}
      </button>
    );
  },
);

Button.displayName = "Button";
