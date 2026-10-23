import React from "react";

interface EmptyStateProps {
  title: string;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
  /** Float the message over a map canvas instead of flowing inline in a list. */
  overlay?: boolean;
}

/**
 * Rendered wherever a surface has nothing real to show. The dashboard never
 * substitutes bundled or cached figures, so an explicit message is the only
 * correct outcome for an empty or unreachable dataset.
 */
export const EmptyState: React.FC<EmptyStateProps> = ({ title, hint, icon: Icon, overlay }) => {
  const body = (
    <>
      {Icon && <Icon className="h-4 w-4 text-slate-400" />}
      <p className="text-xs font-semibold text-slate-600">{title}</p>
      {hint && <p className="text-[11px] font-medium text-slate-400">{hint}</p>}
    </>
  );

  if (overlay) {
    return (
      <div className="pointer-events-none absolute inset-0 z-[500] flex items-center justify-center p-4">
        <div className="flex max-w-xs flex-col items-center gap-1 rounded-xl border border-slate-200/90 bg-white/95 px-4 py-3 text-center shadow-card backdrop-blur">
          {body}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-1 px-4 py-10 text-center">
      {body}
    </div>
  );
};
