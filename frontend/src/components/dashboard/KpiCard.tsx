import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type KpiTone = "primary" | "success" | "warning" | "danger" | "info" | "neutral";

const TONE_CLASSES: Record<KpiTone, string> = {
  primary: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-destructive/10 text-destructive",
  info: "bg-info/10 text-info",
  neutral: "bg-secondary text-muted-foreground",
};

interface KpiCardProps {
  label: string;
  value: ReactNode;
  icon: LucideIcon;
  tone?: KpiTone;
  hint?: string;
  to?: string;
  isLoading?: boolean;
}

/**
 * A single KPI tile for the AI Insight Bar. `to` makes the whole card a
 * navigable link to the relevant detail page (e.g. Pending Reviews → Teacher
 * Review). Numbers use `tabular-nums` so a live-updating value doesn't
 * reflow its neighbors.
 */
export function KpiCard({ label, value, icon: Icon, tone = "primary", hint, to, isLoading }: KpiCardProps) {
  const content = (
    <div
      className={cn(
        "group flex items-start gap-3 rounded-xl border border-border bg-card p-4 shadow-soft transition-all",
        "hover:-translate-y-0.5 hover:shadow-soft-lg",
        to && "cursor-pointer",
      )}
    >
      <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", TONE_CLASSES[tone])}>
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium leading-tight text-muted-foreground">{label}</p>
        {isLoading ? (
          <Skeleton className="mt-1.5 h-7 w-16" />
        ) : (
          <p className="mt-0.5 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
        )}
        {hint && <p className="mt-0.5 truncate text-xs text-muted-foreground">{hint}</p>}
      </div>
    </div>
  );

  if (to) {
    return (
      <Link to={to} aria-label={`${label}: ${typeof value === "string" || typeof value === "number" ? value : ""}`}>
        {content}
      </Link>
    );
  }
  return content;
}
