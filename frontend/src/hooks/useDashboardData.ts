import { useQuery } from "@tanstack/react-query";

import { getAnalyticsOverview } from "@/api/analytics";
import { fetchHealthStatus } from "@/api/health";
import { listMyNotifications } from "@/api/notifications";
import { listOCRJobs } from "@/api/ocrJobs";
import { listReports } from "@/api/reports";
import { getTeacherReviewDashboard, getTeacherReviewQueue } from "@/api/teacherReviewDashboard";
import { listUploadJobs } from "@/api/uploadJobs";
import { useAppSelector } from "@/store";

const RECENT_SAMPLE_SIZE = 50;
const WIDGET_LIST_SIZE = 5;

function isToday(iso: string | null): boolean {
  if (!iso) return false;
  const date = new Date(iso);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

function average(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

/** Buckets a set of ISO timestamps into the last 7 calendar days (oldest
 * first), for the dashboard's "Daily Evaluation Trend" mini bar chart.
 * There is no server-side time-series endpoint for this — it's a real,
 * client-computed count over whatever recent sample was already fetched
 * for the timeline widget (see `RECENT_SAMPLE_SIZE`), not a full
 * historical aggregate. Documented as an approximation in the design
 * deliverables, not fabricated data. */
function bucketByDay(isoDates: string[]): Array<{ label: string; value: number }> {
  const days: Array<{ key: string; label: string }> = [];
  const today = new Date();
  for (let i = 6; i >= 0; i -= 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - i);
    days.push({
      key: date.toDateString(),
      label: date.toLocaleDateString(undefined, { weekday: "short" }),
    });
  }
  const counts = new Map(days.map((day) => [day.key, 0]));
  for (const iso of isoDates) {
    const key = new Date(iso).toDateString();
    if (counts.has(key)) {
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return days.map((day) => ({ label: day.label, value: counts.get(day.key) ?? 0 }));
}

/** Whether the current session even has an institution selected — every
 * institution-scoped query below is `enabled` on this, mirroring the
 * existing convention in `TeacherReviewDashboardPage`/`AnalyticsDashboardPage`. */
export function useCurrentInstitutionId(): string | null {
  return useAppSelector((state) => state.institution.currentInstitutionId);
}

/** Real, unauthenticated system health probe (`GET /health`). */
export function useDashboardHealth() {
  return useQuery({
    queryKey: ["dashboard-health"],
    queryFn: fetchHealthStatus,
    refetchInterval: 60_000,
  });
}

/** Teacher Review summary tiles — pending/medium/low/completed/auto-accepted counts. */
export function useDashboardTeacherReviewSummary(enabled: boolean) {
  const institutionId = useCurrentInstitutionId();
  return useQuery({
    queryKey: ["dashboard-teacher-review-summary", institutionId],
    queryFn: () => getTeacherReviewDashboard(),
    enabled: enabled && Boolean(institutionId),
  });
}

/** Most recent items in the teacher review queue — powers both the
 * "Teacher Review Queue" widget and the "AI Evaluation Timeline" widget
 * (same underlying data, ordered by recency; the timeline additionally
 * derives a computed average AI-evaluation turnaround time from it). */
export function useDashboardRecentEvaluations(enabled: boolean) {
  const institutionId = useCurrentInstitutionId();
  return useQuery({
    queryKey: ["dashboard-recent-evaluations", institutionId],
    queryFn: () =>
      getTeacherReviewQueue({}, { page: 1, page_size: RECENT_SAMPLE_SIZE, sort_by: "created_at", sort_order: "desc" }),
    enabled: enabled && Boolean(institutionId),
    select: (page) => {
      const items = page.items;
      const evaluated = items.filter((item) => item.evaluated_at);
      const turnaroundMinutes = average(
        evaluated.map(
          (item) => (new Date(item.evaluated_at as string).getTime() - new Date(item.created_at).getTime()) / 60_000,
        ),
      );
      const completedToday = items.filter((item) => isToday(item.evaluated_at)).length;
      const dailyTrend = bucketByDay(items.map((item) => item.created_at));
      return {
        recent: items.slice(0, WIDGET_LIST_SIZE),
        pending: items.filter((item) => item.review_status === "pending_review" || item.review_status === "pending_confirmation"),
        total: page.total,
        completedToday,
        avgTurnaroundMinutes: turnaroundMinutes,
        dailyTrend,
      };
    },
  });
}

/** Confidence distribution, pass/fail, override rate — institution-wide, unfiltered. */
export function useDashboardAnalytics(enabled: boolean) {
  const institutionId = useCurrentInstitutionId();
  return useQuery({
    queryKey: ["dashboard-analytics-overview", institutionId],
    queryFn: () => getAnalyticsOverview(),
    enabled: enabled && Boolean(institutionId),
  });
}

/** Recent OCR jobs — powers the "OCR Processing Status" widget and the
 * OCR Queue / OCR Success Rate / Avg OCR Time KPIs, all computed
 * client-side from this same real sample (see dashboard design notes:
 * there is no server-aggregated OCR metrics endpoint). */
export function useDashboardOcrJobs(enabled: boolean) {
  const institutionId = useCurrentInstitutionId();
  return useQuery({
    queryKey: ["dashboard-ocr-jobs", institutionId],
    queryFn: () => listOCRJobs({ page: 1, page_size: RECENT_SAMPLE_SIZE, sort_by: "created_at", sort_order: "desc" }),
    enabled: enabled && Boolean(institutionId),
    select: (page) => {
      const items = page.items;
      const queued = items.filter((job) => job.status === "queued" || job.status === "running").length;
      const completed = items.filter((job) => job.status === "completed");
      const failed = items.filter((job) => job.status === "failed").length;
      const completedToday = completed.filter((job) => isToday(job.completed_at)).length;
      const durations = completed
        .filter((job) => job.started_at && job.completed_at)
        .map((job) => (new Date(job.completed_at as string).getTime() - new Date(job.started_at as string).getTime()) / 1000);
      const successRate =
        completed.length + failed > 0 ? Math.round((completed.length / (completed.length + failed)) * 100) : null;
      return {
        recent: items.slice(0, WIDGET_LIST_SIZE),
        queued,
        completedToday,
        successRate,
        avgDurationSeconds: average(durations),
        sampleSize: items.length,
      };
    },
  });
}

/** Recent upload jobs — powers "Recent Uploads". */
export function useDashboardUploadJobs(enabled: boolean) {
  const institutionId = useCurrentInstitutionId();
  return useQuery({
    queryKey: ["dashboard-upload-jobs", institutionId],
    queryFn: () => listUploadJobs({ page: 1, page_size: WIDGET_LIST_SIZE, sort_by: "created_at", sort_order: "desc" }),
    enabled: enabled && Boolean(institutionId),
  });
}

/** Recent report jobs — powers "Recent Reports". */
export function useDashboardReports(enabled: boolean) {
  const institutionId = useCurrentInstitutionId();
  return useQuery({
    queryKey: ["dashboard-reports", institutionId],
    queryFn: () => listReports({ page: 1, page_size: WIDGET_LIST_SIZE, sort_by: "created_at", sort_order: "desc" }),
    enabled: enabled && Boolean(institutionId),
  });
}

/** Unread notifications — powers "System Notifications". Not institution-
 * gated: notifications are addressed to the signed-in user directly. */
export function useDashboardNotifications(enabled: boolean) {
  return useQuery({
    queryKey: ["dashboard-notifications"],
    queryFn: () => listMyNotifications(true),
    enabled,
  });
}
