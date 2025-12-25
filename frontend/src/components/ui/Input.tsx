"use strict";

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
                    <label htmlFor={id} className="text-callout text-secondary font-medium">
                        {label}
                    </label>
                )}
                <input
                    ref={ref}
                    id={id}
                    className={clsx(
                        "h-[52px] px-4 rounded-md border bg-surface text-primary text-body transition-all duration-200 w-full",
                        "placeholder:text-tertiary focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/10",
                        error ? "border-danger focus:border-danger focus:ring-danger/10" : "border-border",
                        className
                    )}
                    {...props}
                />
                {error && <span className="text-callout text-danger">{error}</span>}
            </div>
        );
    }
);

Input.displayName = "Input";
