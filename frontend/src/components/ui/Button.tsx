"use strict";

import { ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";
import { Loader2 } from "lucide-react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: "primary" | "secondary" | "ghost" | "danger";
    size?: "sm" | "md" | "lg";
    isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant = "primary", size = "md", isLoading, children, disabled, ...props }, ref) => {
        return (
            <button
                ref={ref}
                className={clsx(
                    // Base styles
                    "inline-flex items-center justify-center font-medium transition-all duration-200 focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed",
                    // Rounded corners based on spec (sm radius for standard buttons, md for lg buttons)
                    size === 'lg' ? "rounded-md" : "rounded-sm",

                    // Variants
                    variant === "primary" && "bg-accent text-white hover:opacity-90",
                    variant === "secondary" && "bg-transparent border border-border text-primary hover:bg-border-subtle",
                    variant === "ghost" && "bg-transparent text-secondary hover:bg-border-subtle hover:text-primary",
                    variant === "danger" && "bg-danger text-white hover:opacity-90",

                    // Sizes
                    size === "sm" && "h-8 px-3 text-callout",
                    size === "md" && "h-10 px-4 text-body-small",
                    size === "lg" && "h-[52px] px-6 text-body",

                    className
                )}
                disabled={isLoading || disabled}
                {...props}
            >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : children}
            </button>
        );
    }
);

Button.displayName = "Button";
