"use client";

import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

type IconTone = "neutral" | "accent" | "concept" | "relation" | "source" | "danger";

interface IconFrameProps {
  icon: LucideIcon;
  tone?: IconTone;
  size?: "sm" | "md";
  className?: string;
  iconClassName?: string;
}

const toneClassMap: Record<IconTone, string> = {
  neutral: "bg-elevated text-secondary border-border",
  accent: "bg-[var(--accent-soft)] text-[var(--accent)] border-accent/35",
  concept: "bg-node-concept/16 text-node-concept border-node-concept/35",
  relation: "bg-node-definition/16 text-node-definition border-node-definition/35",
  source: "bg-node-source/16 text-node-source border-node-source/35",
  danger: "bg-danger/16 text-danger border-danger/35",
};

const sizeClassMap = {
  sm: "w-9 h-9",
  md: "w-11 h-11",
};

const iconSizeMap = {
  sm: "w-4 h-4",
  md: "w-[18px] h-[18px]",
};

export function IconFrame({
  icon: Icon,
  tone = "neutral",
  size = "sm",
  className,
  iconClassName,
}: IconFrameProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center rounded-xl border",
        sizeClassMap[size],
        toneClassMap[tone],
        className,
      )}
    >
      <Icon className={clsx(iconSizeMap[size], iconClassName)} strokeWidth={1.75} />
    </span>
  );
}
