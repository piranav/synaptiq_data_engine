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
                    <label htmlFor={id} className="text-sm text-white/70 font-medium">
                        {label}
                    </label>
                )}
                <input
                    ref={ref}
                    id={id}
                    className={clsx(
                        "h-[52px] px-4 rounded-md border bg-white/[0.03] text-white text-base transition-all duration-200 w-full",
                        "placeholder:text-white/40 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
                        error ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500/20" : "border-white/10",
                        className
                    )}
                    {...props}
                />
                {error && <span className="text-xs text-rose-400">{error}</span>}
            </div>
        );
    }
);

Input.displayName = "Input";
