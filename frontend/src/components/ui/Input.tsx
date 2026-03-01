"use client";

import { InputHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-2 w-full">
        {label && (
          <label htmlFor={id} className="text-sm text-secondary font-medium">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={id}
          className={clsx(
            "h-[52px] px-4 rounded-md border bg-surface text-primary text-base transition-all duration-200 w-full",
            "placeholder:text-secondary focus:outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/18",
            error
              ? "border-danger/55 focus:border-danger/55 focus:ring-danger/20"
              : "border-border hover:border-border-strong",
            className,
          )}
          {...props}
        />
        {error && <span className="text-xs text-danger">{error}</span>}
      </div>
    );
  },
);

Input.displayName = "Input";
