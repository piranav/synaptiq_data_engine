import clsx from "clsx";

const columnLabels = ["A", "B", "C", "D", "E", "F"] as const;
const rowLabels = ["1", "2", "3", "4", "5"] as const;

interface GridFrameProps {
  className?: string;
}

export function GridFrame({ className }: GridFrameProps) {
  return (
    <div
      aria-hidden
      className={clsx(
        "absolute inset-0 z-[1] pointer-events-none text-tertiary",
        className,
      )}
    >
      <div className="absolute top-2 left-[18px] right-[18px] flex items-center justify-between text-[11px] font-medium leading-none tracking-[0.18em] uppercase">
        {columnLabels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>

      <div className="absolute top-[18px] bottom-3 left-2 flex flex-col items-start justify-between text-[11px] font-medium leading-none tracking-[0.14em]">
        {rowLabels.map((label) => (
          <span key={`left-${label}`} className="tabular-nums">
            {label}
          </span>
        ))}
      </div>

      <div className="absolute top-[18px] bottom-3 right-2 flex flex-col items-end justify-between text-[11px] font-medium leading-none tracking-[0.14em]">
        {rowLabels.map((label) => (
          <span key={`right-${label}`} className="tabular-nums">
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
