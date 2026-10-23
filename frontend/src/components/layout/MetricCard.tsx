import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  hint?: string;
  badge?: {
    text: string;
    variant?: "success" | "warning" | "info" | "neutral";
  };
  icon?: React.ComponentType<{ className?: string }>;
}

const BADGE_STYLES: Record<string, string> = {
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  info: "bg-sky-50 text-sky-700 border-sky-200",
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
};

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  hint,
  badge,
  icon: Icon,
}) => {
  return (
    <div className="flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white px-3 py-2 sm:px-3.5 sm:py-2.5 shadow-subtle transition-all duration-150 hover:shadow-card">
      <div className="flex items-center justify-between gap-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {label}
        </span>
        {Icon && (
          <div className="grid h-5 w-5 place-items-center rounded bg-slate-100 text-slate-500">
            <Icon className="h-3 w-3" />
          </div>
        )}
      </div>

      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="font-mono text-lg sm:text-xl font-bold tracking-tight text-slate-900 tabular-nums">
          {value}
        </span>
        {badge && (
          <span
            className={`inline-flex items-center rounded-md border px-1.5 py-0.2 text-[9px] font-semibold ${
              BADGE_STYLES[badge.variant || "neutral"]
            }`}
          >
            {badge.text}
          </span>
        )}
      </div>

      {hint && (
        <p className="mt-0.5 truncate text-[11px] text-slate-500 font-medium">
          {hint}
        </p>
      )}
    </div>
  );
};
