import { cn } from "@/lib/utils";

interface ProgressBarProps {
  /** 0-100. Values outside that range are clamped. */
  percent: number;
  label?: string;
  tone?: "primary" | "success" | "warning" | "danger" | "info";
  className?: string;
}

const TONE_CLASSES: Record<NonNullable<ProgressBarProps["tone"]>, string> = {
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-destructive",
  info: "bg-info",
};

/**
 * Shared progress/meter bar. Previously hand-rolled independently in
 * `UploadQueuePage` (upload %), `AnalyticsDashboardPage` (confidence
 * distribution), and `AnswerEvaluationDetailPage` (AI signal scores) with
 * the same `h-2 rounded-full bg-secondary`/`bg-primary` markup each time —
 * consolidated here so every progress indicator in the app looks and
 * animates the same way.
 */
export function ProgressBar({ percent, label, tone = "primary", className }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-secondary"
        role="progressbar"
        aria-valuenow={Math.round(clamped)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-300 ease-out", TONE_CLASSES[tone])}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {label && <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{label}</span>}
    </div>
  );
}
