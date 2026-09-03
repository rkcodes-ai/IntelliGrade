import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface ListItemProps {
  icon?: LucideIcon;
  iconTone?: "primary" | "success" | "warning" | "danger" | "info" | "neutral";
  title: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  trailing?: ReactNode;
  onClick?: () => void;
}

const ICON_TONE_CLASSES: Record<NonNullable<ListItemProps["iconTone"]>, string> = {
  primary: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-destructive/10 text-destructive",
  info: "bg-info/10 text-info",
  neutral: "bg-secondary text-muted-foreground",
};

/** One row in a dashboard queue/feed widget (timeline, notifications, uploads, reports). */
export function ListItem({ icon: Icon, iconTone = "neutral", title, subtitle, meta, trailing, onClick }: ListItemProps) {
  const Element = onClick ? "button" : "div";
  return (
    <Element
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition-colors",
        onClick && "hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      {Icon && (
        <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", ICON_TONE_CLASSES[iconTone])}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{title}</span>
        {subtitle && <span className="mt-0.5 block truncate text-xs text-muted-foreground">{subtitle}</span>}
      </span>
      {meta && <span className="shrink-0 text-xs text-muted-foreground">{meta}</span>}
      {trailing}
    </Element>
  );
}

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="flex items-center gap-3 px-2 py-2">
          <div className="h-8 w-8 shrink-0 animate-shimmer rounded-full bg-muted" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3.5 w-3/4 animate-shimmer rounded bg-muted" />
            <div className="h-3 w-1/2 animate-shimmer rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <p className="px-2 py-6 text-center text-sm text-muted-foreground">{message}</p>;
}
